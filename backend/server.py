import base64
import copy
import io
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
import pypdfium2 as pdfium

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = BASE_DIR / "earve_settings.json"
FRONTEND_DIR = BASE_DIR / "frontend"

CUSTOMDB_SCHEMA_PLACEHOLDER = "{{CUSTOMDB_SCHEMA_JSON}}"
CUSTOMDB_MODE = "customdb"
XML_MODE = "xml"
DYNAMIC_MODE = "dynamic"
VALID_MODES = (CUSTOMDB_MODE, XML_MODE, DYNAMIC_MODE)
DEFAULT_CUSTOMDB_SCHEMA: Dict[str, Any] = {
    "doc_num": "",
    "doc_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD",
    "ref_num": "",
    "description": "",
    "src_path": "",
    "vat_rate": 0,
    "items_sum": 0,
    "vat_sum": 0,
    "total_sum": 0,
    "round_sum": 0,
    "buyer": {
        "name": "",
        "address": "",
    },
    "counterparty": {
        "name": "",
        "reg_num": "",
        "vat_num": "",
        "address": "",
    },
    "items": [
        {
            "title": "",
            "description": "",
            "code": "",
            "amount": 1,
            "unit": "",
            "item_price": 0,
            "item_sum": 0,
            "vat_sum": 0,
            "total_sum": 0,
        }
    ],
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "provider": "openai",
    "openAiBaseUrl": "https://api.openai.com/v1",
    "openAiKey": "",
    "openAiModel": "gpt-4o-mini",
    "lmStudioUrl": "http://localhost:1234",
    "lmStudioModel": "",
    "ocrMode": "none",
    "googleVisionKey": "",
    "ocrLmStudioModel": "",
    "xmlPrompt": "",
    "customDbPrompt": "",
    "dynamicPrompt": "",
    "ocrPrompt": "",
    "customDbSchema": DEFAULT_CUSTOMDB_SCHEMA,
    "customJsonMapping": {},
    "pipelineSettings": {
        "mode": CUSTOMDB_MODE,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_mode(mode: Optional[str]) -> str:
    if not mode:
        return CUSTOMDB_MODE
    return mode


def load_base_settings() -> Dict[str, Any]:
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            settings.update(data)
            settings.pop("updbPrompt", None)
            settings.pop("updbSchema", None)
            settings.pop("filterDuplicates", None)
    if not isinstance(settings.get("customDbSchema"), dict):
        settings["customDbSchema"] = copy.deepcopy(DEFAULT_CUSTOMDB_SCHEMA)
    if not isinstance(settings.get("customJsonMapping"), dict):
        settings["customJsonMapping"] = {}
    if not isinstance(settings.get("pipelineSettings"), dict):
        settings["pipelineSettings"] = {"mode": CUSTOMDB_MODE}
    if settings.get("provider") not in ("openai", "lmstudio"):
        settings["provider"] = "openai"
    settings["pipelineSettings"]["mode"] = normalize_mode(settings["pipelineSettings"].get("mode"))
    if settings["pipelineSettings"].get("mode") not in VALID_MODES:
        settings["pipelineSettings"]["mode"] = CUSTOMDB_MODE
    return settings


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._jobs[payload["id"]] = payload
            return copy.deepcopy(payload)

    def update(self, job_id: str, **changes: Any) -> Dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            self._jobs[job_id].update(changes)
            self._jobs[job_id]["updated_at"] = utc_now()
            return copy.deepcopy(self._jobs[job_id])

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._jobs.get(job_id)
            return copy.deepcopy(item) if item else None

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return sorted(
                [copy.deepcopy(v) for v in self._jobs.values()],
                key=lambda x: x.get("created_at", ""),
                reverse=True,
            )


store = JobStore()
executor = ThreadPoolExecutor(max_workers=3)
app = FastAPI(title="Document Converter Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_frontend_html(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _pdf_to_jpeg_bytes(raw_bytes: bytes) -> bytes:
    pdf = pdfium.PdfDocument(raw_bytes)
    if len(pdf) == 0:
        raise ValueError("PDF has no pages")
    page = pdf[0]
    bitmap = page.render(scale=2.5)
    pil_image = bitmap.to_pil()
    out = io.BytesIO()
    pil_image.save(out, format="JPEG", quality=95)
    return out.getvalue()


def _to_base64_image(upload: UploadFile, raw_bytes: bytes) -> str:
    content_type = (upload.content_type or "").lower()
    is_pdf = upload.filename.lower().endswith(".pdf") or "pdf" in content_type
    if is_pdf:
        raw_bytes = _pdf_to_jpeg_bytes(raw_bytes)
    else:
        # validate image payload is sane for model usage
        Image.open(io.BytesIO(raw_bytes)).verify()
    return base64.b64encode(raw_bytes).decode("ascii")


def _openai_chat(url: str, key: str, model: str, prompt: str, base64_image: Optional[str], doc_text: Optional[str]) -> str:
    content = [{"type": "text", "text": prompt}]
    if doc_text:
        content.append({"type": "text", "text": "\n\n--- DOC TEXT ---\n" + doc_text})
    elif base64_image:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 2048,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=240)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def _google_ocr(api_key: str, base64_image: str) -> str:
    if not api_key:
        raise ValueError("Missing Google Vision key")
    r = requests.post(
        f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
        json={
            "requests": [
                {
                    "image": {"content": base64_image},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                }
            ]
        },
        timeout=240,
    )
    r.raise_for_status()
    data = r.json()
    return data["responses"][0].get("fullTextAnnotation", {}).get("text", "")


def _render_schema_prompt(prompt: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    schema = settings.get("customDbSchema")
    if not isinstance(schema, dict):
        schema = copy.deepcopy(DEFAULT_CUSTOMDB_SCHEMA)

    schema_text = "JSON schema exactly like this:\n" + json.dumps(schema, ensure_ascii=False, indent=2)
    warnings: List[str] = []
    if CUSTOMDB_SCHEMA_PLACEHOLDER in prompt:
        rendered = prompt.replace(CUSTOMDB_SCHEMA_PLACEHOLDER, schema_text)
    else:
        base_prompt = prompt.rstrip()
        schema_start = -1
        for idx, ch in enumerate(base_prompt):
            if ch != "{":
                continue
            try:
                json.loads(base_prompt[idx:])
                schema_start = idx
                break
            except json.JSONDecodeError:
                continue
        if schema_start >= 0:
            base_prompt = base_prompt[:schema_start].rstrip()
            warnings.append("Trailing JSON schema was replaced with centralized CustomDB schema.")
        else:
            warnings.append(f"Prompt did not contain {CUSTOMDB_SCHEMA_PLACEHOLDER}; schema was appended.")
        rendered = f"{base_prompt}\n\n--- INJECTED CUSTOMDB SCHEMA ---\n{schema_text}"
    return {"prompt": rendered, "warnings": warnings}


def _require_text_setting(settings: Dict[str, Any], key: str, label: str) -> str:
    value = settings.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Setup incomplete: missing {label} in earve_settings.json")
    return value


def _extract_mode_prompt(mode: str, settings: Dict[str, Any]) -> str:
    if mode == XML_MODE:
        return _require_text_setting(settings, "xmlPrompt", "XML mode prompt")
    if mode == DYNAMIC_MODE:
        return _require_text_setting(settings, "dynamicPrompt", "arbitrary mode prompt")
    if mode == CUSTOMDB_MODE:
        prompt = _require_text_setting(settings, "customDbPrompt", "CustomDB prompt")
        return _render_schema_prompt(prompt, settings)["prompt"]
    raise ValueError("mode must be one of: customdb, xml, dynamic")


def _probe_openai_compatible_models(base_url: str, api_key: str) -> List[Dict[str, str]]:
    if not base_url or not api_key:
        return []
    url = f"{base_url.rstrip('/')}/models"
    r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    models = data.get("data", [])
    return [{"id": m.get("id", ""), "name": m.get("id", "")} for m in models if m.get("id")]


def _probe_lmstudio_models(base_url: str) -> List[Dict[str, str]]:
    if not base_url:
        return []
    url = f"{base_url.rstrip('/')}/v1/models"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()
    models = data.get("data", [])
    return [{"id": m.get("id", ""), "name": m.get("id", "")} for m in models if m.get("id")]


def _process_job(job_id: str, mode: str, base64_image: str, settings: Dict[str, Any]) -> None:
    try:
        store.update(job_id, status="processing", progress=10, stage="Preparing pipeline")
        prompt = _extract_mode_prompt(mode, settings)
        doc_text: Optional[str] = None
        raw_ocr = ""

        ocr_mode = settings.get("ocrMode", "none")
        if ocr_mode == "google":
            store.update(job_id, progress=30, stage="Running Google OCR")
            raw_ocr = _google_ocr(settings.get("googleVisionKey", ""), base64_image)
            doc_text = raw_ocr
        elif ocr_mode == "lmstudio_vlm":
            store.update(job_id, progress=30, stage="Running Local VLM OCR")
            lm_url = settings.get("lmStudioUrl", "http://localhost:1234").rstrip("/")
            raw_ocr = _openai_chat(
                f"{lm_url}/v1/chat/completions",
                "x",
                settings.get("ocrLmStudioModel", ""),
                _require_text_setting(settings, "ocrPrompt", "OCR prompt"),
                base64_image,
                None,
            )
            doc_text = raw_ocr

        store.update(job_id, progress=65, stage="Running extraction model", raw_ocr_text=raw_ocr)

        if settings.get("provider") == "openai":
            out = _openai_chat(
                f"{settings.get('openAiBaseUrl', '').rstrip('/')}/chat/completions",
                settings.get("openAiKey", ""),
                settings.get("openAiModel", ""),
                prompt,
                None if doc_text else base64_image,
                doc_text,
            )
        else:
            lm_url = settings.get("lmStudioUrl", "http://localhost:1234").rstrip("/")
            out = _openai_chat(
                f"{lm_url}/v1/chat/completions",
                "x",
                settings.get("lmStudioModel", ""),
                prompt,
                None if doc_text else base64_image,
                doc_text,
            )

        parsed: Any = out
        if mode in (XML_MODE, CUSTOMDB_MODE):
            s = out.find("{")
            e = out.rfind("}")
            if s >= 0 and e > s:
                parsed = json.loads(out[s : e + 1])

        store.update(
            job_id,
            status="completed",
            progress=100,
            stage="Completed",
            result=parsed,
            raw_response=out,
            completed_at=utc_now(),
        )
    except Exception as exc:  # noqa: BLE001
        store.update(
            job_id,
            status="failed",
            stage="Failed",
            error=str(exc),
            completed_at=utc_now(),
        )


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "time": utc_now()}


@app.get("/api/settings/default")
def get_default_settings() -> Dict[str, Any]:
    return load_base_settings()


@app.post("/api/settings/save")
def save_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    settings = payload.get("settings", payload)
    if not isinstance(settings, dict):
        raise HTTPException(400, "Settings payload must be a JSON object")

    settings.pop("updbPrompt", None)
    settings.pop("updbSchema", None)
    settings.pop("filterDuplicates", None)
    if settings.get("provider") not in ("openai", "lmstudio"):
        settings["provider"] = "openai"
    if not isinstance(settings.get("customDbSchema"), dict):
        settings["customDbSchema"] = copy.deepcopy(DEFAULT_CUSTOMDB_SCHEMA)
    if not isinstance(settings.get("customJsonMapping"), dict):
        settings["customJsonMapping"] = {}
    if not isinstance(settings.get("pipelineSettings"), dict):
        settings["pipelineSettings"] = {"mode": CUSTOMDB_MODE}
    settings["pipelineSettings"]["mode"] = normalize_mode(settings["pipelineSettings"].get("mode"))
    if settings["pipelineSettings"].get("mode") not in VALID_MODES:
        settings["pipelineSettings"]["mode"] = CUSTOMDB_MODE

    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(SETTINGS_PATH)}


@app.get("/api/bootstrap")
def bootstrap() -> Dict[str, Any]:
    return {
        "backendUrl": "http://localhost:8000",
        "settings": load_base_settings(),
    }


@app.post("/api/probe/openai")
def probe_openai(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    try:
        return _probe_openai_compatible_models(payload.get("openAiBaseUrl", ""), payload.get("openAiKey", ""))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/probe/lmstudio")
def probe_lmstudio(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    try:
        return _probe_lmstudio_models(payload.get("lmStudioUrl", ""))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/prompt/preview")
def prompt_preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = normalize_mode(payload.get("mode", CUSTOMDB_MODE))
    if mode not in VALID_MODES:
        raise HTTPException(400, "mode must be one of: customdb, xml, dynamic")
    settings = load_base_settings()
    user_settings = payload.get("settings")
    if isinstance(user_settings, dict):
        settings.update(user_settings)

    if mode != CUSTOMDB_MODE:
        try:
            return {"prompt": _extract_mode_prompt(mode, settings), "warnings": []}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    try:
        prompt = _require_text_setting(settings, "customDbPrompt", "CustomDB prompt")
        return _render_schema_prompt(prompt, settings)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/jobs")
def list_jobs() -> List[Dict[str, Any]]:
    return store.list()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    mode: Optional[str] = Form(None),
    settings_json: Optional[str] = Form(None),
) -> Dict[str, Any]:
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(400, "Empty file payload")

    base_settings = load_base_settings()
    if settings_json:
        try:
            user_settings = json.loads(settings_json)
            if isinstance(user_settings, dict):
                base_settings.update(user_settings)
                if not isinstance(base_settings.get("customDbSchema"), dict):
                    base_settings["customDbSchema"] = copy.deepcopy(DEFAULT_CUSTOMDB_SCHEMA)
                if not isinstance(base_settings.get("customJsonMapping"), dict):
                    base_settings["customJsonMapping"] = {}
                if not isinstance(base_settings.get("pipelineSettings"), dict):
                    base_settings["pipelineSettings"] = {"mode": CUSTOMDB_MODE}
        except json.JSONDecodeError as exc:
            raise HTTPException(400, f"Invalid settings_json: {exc}") from exc

    pipeline_settings = base_settings.get("pipelineSettings", {})
    if not mode:
        mode = pipeline_settings.get("mode", CUSTOMDB_MODE) if isinstance(pipeline_settings, dict) else CUSTOMDB_MODE
    mode = normalize_mode(mode)
    if mode not in VALID_MODES:
        raise HTTPException(400, "mode must be one of: customdb, xml, dynamic")

    image_b64 = _to_base64_image(file, raw_bytes)
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "source": "api",
        "file_name": file.filename,
        "mode": mode,
        "status": "queued",
        "progress": 0,
        "stage": "Queued",
        "result": None,
        "raw_response": "",
        "raw_ocr_text": "",
        "error": "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "completed_at": None,
    }
    store.create(job)
    executor.submit(_process_job, job_id, mode, image_b64, base_settings)
    return {"job_id": job_id}


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

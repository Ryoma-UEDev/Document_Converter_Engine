import argparse
import copy
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "pipelines.json"
DEFAULT_BACKEND_URL = "http://localhost:8000"
POLL_SECONDS = 2


def default_config() -> Dict[str, Any]:
    return {
        "backendUrl": DEFAULT_BACKEND_URL,
        "options": {
            "keepInputFiles": True,
            "usePipelineName": True,
            "restoreOriginalSettings": True,
        },
        "modelOptions": {
            "ocr": {"lmstudio": [], "ollama": [], "openai": []},
            "llm": {"lmstudio": [], "ollama": [], "openai": []},
        },
        "pipelines": [
            {
                "name": "Google Vision + LM Studio",
                "ocrProvider": "google",
                "ocrModel": "",
                "llmProvider": "lmstudio",
                "llmModel": "",
            }
        ],
    }


def merge_config(data: Dict[str, Any]) -> Dict[str, Any]:
    config = default_config()
    if isinstance(data, dict):
        config.update({k: v for k, v in data.items() if k in ("backendUrl", "options", "modelOptions", "pipelines")})
    if not isinstance(config.get("options"), dict):
        config["options"] = default_config()["options"]
    for key, value in default_config()["options"].items():
        config["options"].setdefault(key, value)
    if not isinstance(config.get("modelOptions"), dict):
        config["modelOptions"] = default_config()["modelOptions"]
    for role in ("ocr", "llm"):
        config["modelOptions"].setdefault(role, {})
        for provider in ("lmstudio", "ollama", "openai"):
            models = config["modelOptions"][role].get(provider)
            config["modelOptions"][role][provider] = models if isinstance(models, list) else []
    if not isinstance(config.get("pipelines"), list):
        config["pipelines"] = default_config()["pipelines"]
    return config


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return default_config()
    try:
        return merge_config(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception:
        return default_config()


def save_config(config: Dict[str, Any]) -> Dict[str, Any]:
    clean = merge_config(config)
    CONFIG_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def backend_request(backend_url: str, method: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Any:
    url = backend_url.rstrip("/") + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def safe_name(value: str) -> str:
    return (value or "").strip()


def pipeline_display_name(pipeline: Dict[str, Any]) -> str:
    name = safe_name(pipeline.get("name", ""))
    if name:
        return name
    ocr = pipeline.get("ocrProvider", "none")
    ocr_model = pipeline.get("ocrModel") or ocr
    llm = pipeline.get("llmProvider", "lmstudio")
    llm_model = pipeline.get("llmModel") or llm
    return f"OCR {ocr_model} + LLM {llm_model}"


def apply_pipeline_settings(base: Dict[str, Any], pipeline: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
    settings = copy.deepcopy(base)

    llm_provider = pipeline.get("llmProvider") or "lmstudio"
    settings["provider"] = llm_provider
    if llm_provider == "lmstudio":
        settings["lmStudioModel"] = pipeline.get("llmModel", "")
    elif llm_provider == "ollama":
        settings["ollamaModel"] = pipeline.get("llmModel", "")
    elif llm_provider == "openai":
        settings["openAiModel"] = pipeline.get("llmModel", "")

    ocr_provider = pipeline.get("ocrProvider") or "none"
    settings["ocrProvider"] = ocr_provider
    settings["ocrMode"] = ocr_provider
    if ocr_provider == "lmstudio":
        settings["ocrLmStudioModel"] = pipeline.get("ocrModel", "")
    elif ocr_provider == "ollama":
        settings["ocrOllamaModel"] = pipeline.get("ocrModel", "")
    elif ocr_provider == "openai":
        settings["ocrOpenAiModel"] = pipeline.get("ocrModel", "")

    batch = settings.get("batchSettings") if isinstance(settings.get("batchSettings"), dict) else {}
    batch["keepInputFiles"] = bool(options.get("keepInputFiles", True))
    batch["usePipelineName"] = bool(options.get("usePipelineName", True))
    settings["batchSettings"] = batch
    return settings


def probe_payload(settings: Dict[str, Any], role: str, provider: str) -> tuple[str, Dict[str, Any]]:
    if provider == "lmstudio":
        return "/api/probe/lmstudio", {
            "lmStudioUrl": settings.get("ocrLmStudioUrl") if role == "ocr" else settings.get("lmStudioUrl", "")
        }
    if provider == "ollama":
        return "/api/probe/ollama", {
            "ollamaUrl": settings.get("ocrOllamaUrl") if role == "ocr" else settings.get("ollamaUrl", "")
        }
    if provider == "openai":
        if role == "ocr":
            return "/api/probe/openai", {
                "openAiBaseUrl": settings.get("ocrOpenAiBaseUrl", ""),
                "openAiKey": settings.get("ocrOpenAiKey", ""),
            }
        return "/api/probe/openai", {
            "openAiBaseUrl": settings.get("openAiBaseUrl", ""),
            "openAiKey": settings.get("openAiKey", ""),
        }
    raise ValueError(f"Provider {provider} does not have model probing")


class Runner:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.reset_state()

    def reset_state(self) -> None:
        self.running = False
        self.started_at = ""
        self.finished_at = ""
        self.current_index = -1
        self.current_name = ""
        self.message = "Idle"
        self.error = ""
        self.results: List[Dict[str, Any]] = []
        self.log: List[str] = []

    def state(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "running": self.running,
                "startedAt": self.started_at,
                "finishedAt": self.finished_at,
                "currentIndex": self.current_index,
                "currentName": self.current_name,
                "message": self.message,
                "error": self.error,
                "results": list(self.results),
                "log": list(self.log[-300:]),
            }

    def append_log(self, message: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.lock:
            self.log.append(f"[{stamp}] {message}")
            self.log = self.log[-500:]

    def update(self, **changes: Any) -> None:
        with self.lock:
            for key, value in changes.items():
                setattr(self, key, value)

    def start(self, config: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if self.running:
                already_running = True
            else:
                already_running = False
                self.reset_state()
                self.running = True
                self.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self.message = "Starting"
                self.stop_event.clear()
                self.thread = threading.Thread(target=self._run, args=(merge_config(config),), daemon=True)
                self.thread.start()
        if already_running:
            return self.state()
        return self.state()

    def stop(self, backend_url: str) -> Dict[str, Any]:
        self.stop_event.set()
        try:
            backend_request(backend_url, "POST", "/api/batch/stop", {}, timeout=10)
        except Exception as exc:
            self.append_log(f"Stop request warning: {exc}")
        self.update(message="Stop requested")
        return self.state()

    def _run(self, config: Dict[str, Any]) -> None:
        backend_url = config.get("backendUrl") or DEFAULT_BACKEND_URL
        options = config.get("options") if isinstance(config.get("options"), dict) else {}
        pipelines = [p for p in config.get("pipelines", []) if isinstance(p, dict)]
        original_settings: Optional[Dict[str, Any]] = None
        try:
            self.append_log(f"Connecting to backend {backend_url}")
            original_settings = backend_request(backend_url, "GET", "/api/settings/default", timeout=30)
            if not pipelines:
                raise ValueError("Pipeline list is empty")

            for index, pipeline in enumerate(pipelines):
                if self.stop_event.is_set():
                    self.append_log("Stopped before next pipeline")
                    break
                name = pipeline_display_name(pipeline)
                self.update(current_index=index, current_name=name, message=f"Running {name}")
                self.append_log(f"Pipeline {index + 1}/{len(pipelines)}: {name}")

                started = time.time()
                result_item: Dict[str, Any] = {
                    "index": index,
                    "name": name,
                    "status": "running",
                    "resultDir": "",
                    "processed": 0,
                    "failed": 0,
                    "durationSeconds": 0,
                    "error": "",
                }
                with self.lock:
                    self.results.append(result_item)

                try:
                    settings = apply_pipeline_settings(original_settings, pipeline, options)
                    batch_payload = settings.get("batchSettings", {})
                    backend_request(backend_url, "POST", "/api/settings/save", {"settings": settings}, timeout=60)
                    self.append_log(f"Saved settings for {name}")
                    status = backend_request(backend_url, "POST", "/api/batch/run-once", batch_payload, timeout=30)
                    self.append_log(f"Started batch: {status.get('resultDir') or status.get('runDir') or '-'}")

                    last_status = status
                    while True:
                        if self.stop_event.is_set():
                            backend_request(backend_url, "POST", "/api/batch/stop", {}, timeout=10)
                            self.append_log("Stop requested; waiting for current backend batch to settle")
                        time.sleep(POLL_SECONDS)
                        last_status = backend_request(backend_url, "GET", "/api/batch/status", timeout=30)
                        totals = last_status.get("totals") or {}
                        self.update(
                            message=(
                                f"{name}: {last_status.get('currentFile') or 'waiting'} "
                                f"({totals.get('processed', 0)} ok, {totals.get('failed', 0)} failed)"
                            )
                        )
                        if not last_status.get("running"):
                            break

                    totals = last_status.get("totals") or {}
                    status_text = "completed" if not last_status.get("lastError") else "completed_with_errors"
                    result_item.update(
                        {
                            "status": status_text,
                            "resultDir": last_status.get("resultDir", ""),
                            "processed": totals.get("processed", 0),
                            "failed": totals.get("failed", 0),
                            "durationSeconds": round(time.time() - started, 2),
                            "error": last_status.get("lastError", ""),
                        }
                    )
                    self.append_log(
                        f"Finished {name}: {result_item['processed']} ok, "
                        f"{result_item['failed']} failed -> {result_item['resultDir'] or '-'}"
                    )
                except Exception as exc:
                    result_item.update(
                        {
                            "status": "failed",
                            "durationSeconds": round(time.time() - started, 2),
                            "error": str(exc),
                        }
                    )
                    self.append_log(f"Pipeline failed: {name}: {exc}")

                if self.stop_event.is_set():
                    break

            if original_settings and options.get("restoreOriginalSettings", True):
                backend_request(backend_url, "POST", "/api/settings/save", {"settings": original_settings}, timeout=60)
                self.append_log("Restored original backend settings")
            self.update(message="Finished")
        except Exception as exc:
            self.update(error=str(exc), message="Runner failed")
            self.append_log(f"Runner failed: {exc}")
        finally:
            self.update(running=False, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))


runner = Runner()


class PipeRunnerHandler(SimpleHTTPRequestHandler):
    def send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            self.path = "/index.html"
            return super().do_GET()
        if parsed.path == "/api/state":
            config = load_config()
            self.send_json({"config": config, "runner": runner.state()})
            return
        if parsed.path == "/api/settings":
            backend_url = params.get("backendUrl", [DEFAULT_BACKEND_URL])[0]
            try:
                self.send_json(backend_request(backend_url, "GET", "/api/settings/default", timeout=30))
            except Exception as exc:
                self.send_json({"error": str(exc)}, status=500)
            return
        return super().do_GET()

    def do_POST(self) -> None:
        try:
            if self.path == "/api/save":
                config = save_config(self.read_json())
                self.send_json({"status": "ok", "config": config})
                return
            if self.path == "/api/probe":
                payload = self.read_json()
                backend_url = payload.get("backendUrl") or DEFAULT_BACKEND_URL
                role = payload.get("role") or "llm"
                provider = payload.get("provider") or ""
                settings = backend_request(backend_url, "GET", "/api/settings/default", timeout=30)
                path, probe_data = probe_payload(settings, role, provider)
                models = backend_request(backend_url, "POST", path, probe_data, timeout=120)
                self.send_json({"models": models})
                return
            if self.path == "/api/run":
                config = save_config(self.read_json())
                self.send_json({"status": "ok", "runner": runner.start(config)})
                return
            if self.path == "/api/stop":
                payload = self.read_json()
                self.send_json({"status": "ok", "runner": runner.stop(payload.get("backendUrl") or DEFAULT_BACKEND_URL)})
                return
            self.send_json({"error": "Not found"}, status=404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Document Converter pipeline runner")
    parser.add_argument("--port", type=int, default=8060)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("", args.port), PipeRunnerHandler)
    print(f"PipeRunner serving on http://localhost:{args.port}/")
    server.serve_forever()

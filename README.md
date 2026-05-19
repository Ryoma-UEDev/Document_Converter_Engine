# Document Converter App

A local-first invoice and document extraction tool with a FastAPI backend and browser workstation. The primary workflow is CustomDB invoice extraction: upload a PDF or image, run OCR and/or a vision-capable LLM, review the structured result, map extracted fields into the target schema, and export JSON.

The backend is intended to work as a document-conversion engine even without the dedicated frontend. External tools can submit files through the API and use the app as an automation link in a larger document processing pipeline. The current frontend is a workstation and admin surface for manual review, job monitoring, prompt/schema tuning, and backend settings management.

The app has a practical focus on Estonian business documents but works with any invoice or structured document. The UI supports English, Estonian, and Russian.

It also serves as a testbed for finding the best model, OCR, and prompt combination for reliable field extraction. A benchmarking and automated testing layer is planned to report field-accuracy results visually.

---

## About This Project

This is an open portfolio project. The goals are:

- Build a genuinely useful local document extraction tool.
- Provide a backend engine that can be plugged into external automation workflows without requiring the bundled frontend.
- Treat the bundled frontend as a workstation/admin tool for review, monitoring, and settings management.
- Keep every configurable part (providers, prompts, schema, mapping) out of the code and in settings, so behaviour can be changed without code edits.
- Compare cloud and local LLM providers (OpenAI-compatible APIs, LM Studio, Ollama) on the same extraction task.
- Add automated testing to measure per-field accuracy across model and prompt combinations, and publish the results in the repo.

---

## Quick Start

**Clean Windows machine (no Python required):**

```bat
setup_requirements.bat
serverstart.bat
```

`setup_requirements.bat` downloads a standalone Python runtime into `.standalone\python` and installs backend dependencies without touching system Python.

**Developer machine with Python already installed (Windows):**

```bat
serversetup.bat
serverstart.bat
```

**Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

The app opens at:

```
http://localhost:8000/
```

Local settings are stored in `earve_settings.json`, which is gitignored because it can contain API keys. Use `earve_settings.example.json` as the starting template.

---

## Current Features

- Browser UI served by the backend from `frontend/index.html`.
- Backend API can be used directly by external automation without the bundled frontend.
- PDF and image upload with client-side preview, zoom, and pan.
- Processing modes: `customdb`, `xml`, and `dynamic`.
- Provider support: OpenAI-compatible cloud APIs, LM Studio (local), and Ollama (local).
- OCR options: none, Google Cloud Vision, LM Studio VLM, or Ollama VLM.
- In-memory job queue with status, progress, raw OCR text, raw model response, and parsed result.
- Settings UI for provider credentials, models, OCR mode, prompts, CustomDB schema, and custom JSON mapping. All configurable without code changes.
- Separate CustomDB viewer template in `frontend/customdb-viewer.html`, editable independently of the main app.
- CustomDB prompt injection using `{{CUSTOMDB_SCHEMA_JSON}}`.
- Model probing endpoints for OpenAI-compatible APIs, LM Studio, and Ollama.
- UI language switch between English, Estonian, and Russian.

---

## Settings

The backend merges built-in defaults with `earve_settings.json`. Copy `earve_settings.example.json` to get started.

Key fields:

```json
{
  "provider": "openai",
  "openAiBaseUrl": "https://api.openai.com/v1",
  "openAiKey": "",
  "openAiModel": "gpt-4o-mini",
  "lmStudioUrl": "http://localhost:1234",
  "lmStudioModel": "",
  "ollamaUrl": "http://localhost:11434",
  "ollamaModel": "",
  "ocrMode": "none",
  "googleVisionKey": "",
  "ocrLmStudioModel": "",
  "ocrOllamaModel": "",
  "xmlPrompt": "",
  "customDbPrompt": "... {{CUSTOMDB_SCHEMA_JSON}} ...",
  "dynamicPrompt": "",
  "ocrPrompt": "",
  "pipelineSettings": {
    "mode": "customdb"
  },
  "customDbSchema": {},
  "customJsonMapping": {}
}
```

**`customDbSchema`** drives the injected prompt, CustomDB viewer defaults, additional fields, and exported JSON shape. A working default schema is committed to the repo. Localisation of schema labels is being improved.

**`customJsonMapping`** maps CustomDB viewer fields to source paths from the extracted JSON:

```json
{
  "doc_num": "invoice.number",
  "counterparty.name": "seller.name",
  "items[].title": "lines[].name"
}
```

If no mapping is configured, fields map to themselves.

**Ollama** exposes an OpenAI-compatible API at `/v1`, so it reuses the same client as the OpenAI provider. Set `provider` to `ollama` and point `ollamaUrl` at your running Ollama instance.

The CustomDB viewer template lives in `frontend/customdb-viewer.html`. It renders the normalised CustomDB form after mapping has been applied. The Open Template button in the UI loads a local `.html` viewer for the current browser session.

---

## Providers

| Provider | Type | Use case |
|---|---|---|
| OpenAI-compatible | Cloud / hosted | Best accuracy, requires API key |
| LM Studio | Local | Run any GGUF model locally |
| Ollama | Local | Run any Ollama model locally |

All three providers use the same extraction pipeline. Switching provider only changes the backend HTTP target and credentials.

---

## Planned: Testing And Benchmarking

The app is designed as a testbed for finding the best extraction pipeline. A testing layer is in progress:

- Automated test runner that submits reference documents and compares extracted fields against expected values.
- Per-field accuracy tracking across model, OCR mode, and prompt combinations.
- Results stored per run so they can be compared over time.
- Visual reports: field accuracy as pie or bar charts, per-model comparison tables, published in this repo.

Sensitive prompts will not be included. Test fixtures and example prompts will be kept in a dedicated directory.

---

## API

Base URL: `http://localhost:8000`

### `GET /api/health`
Returns backend status and current UTC timestamp.

### `GET /api/bootstrap`
Returns the frontend backend URL and effective settings.

### `GET /api/settings/default`
Returns effective settings after merging backend defaults with `earve_settings.json`.

### `POST /api/settings/save`
Writes settings to `earve_settings.json`.

```json
{
  "settings": {
    "provider": "ollama",
    "pipelineSettings": { "mode": "customdb" },
    "customDbSchema": {},
    "customJsonMapping": {}
  }
}
```

### `POST /api/jobs`
Submits a document extraction job as `multipart/form-data`.

Fields:
- `file`: PDF or image.
- `mode`: optional `customdb`, `xml`, or `dynamic`.
- `settings_json`: optional JSON string with per-job settings overrides.

If `mode` is omitted the backend uses `settings.pipelineSettings.mode`. If `settings_json` is omitted the backend uses saved settings.

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "file=@invoice.pdf" \
  -F "mode=customdb" \
  -F "settings_json={\"ocrMode\":\"none\"}"
```

Minimal request using saved settings:

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "file=@invoice.pdf"
```

Response: `{ "job_id": "uuid" }`

### `GET /api/jobs`
Lists in-memory jobs, newest first.

### `GET /api/jobs/{job_id}`
Returns one job.

```json
{
  "id": "uuid",
  "source": "api",
  "file_name": "invoice.pdf",
  "mode": "customdb",
  "status": "completed",
  "progress": 100,
  "stage": "Completed",
  "result": {},
  "raw_response": "",
  "raw_ocr_text": "",
  "error": ""
}
```

### `POST /api/prompt/preview`
Previews the final prompt with `{{CUSTOMDB_SCHEMA_JSON}}` replaced by the active schema.

### `POST /api/probe/openai`
Lists models from the configured OpenAI-compatible API.

### `POST /api/probe/lmstudio`
Lists models from LM Studio.

### `POST /api/probe/ollama`
Lists models from Ollama.

---

## Notes

- Jobs are stored in memory only and disappear on backend restart.
- PDF processing currently uses page 1 only.
- The frontend polls `/api/jobs` every 2 seconds, so API-submitted jobs appear while the UI is open.
- The backend validates image payloads with Pillow and converts PDF page 1 to JPEG with `pypdfium2`.
- Localisation strings are a working baseline in the first commit. Improved translations will follow.

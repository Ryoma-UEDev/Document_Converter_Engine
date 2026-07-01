# API Reference

Base URL:

```text
http://localhost:8000
```

## Health And Settings

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

## Jobs

### `POST /api/jobs`

Submits a document extraction job as `multipart/form-data`.

Fields:

- `file`: PDF or image.
- `mode`: optional `customdb`, `xml`, or `dynamic`.
- `settings_json`: optional JSON string with per-job settings overrides.

If `mode` is omitted, the backend uses `settings.pipelineSettings.mode`. If `settings_json` is omitted, the backend uses saved settings.

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "file=@invoice.pdf" \
  -F "mode=customdb" \
  -F "settings_json={\"ocrProvider\":\"none\"}"
```

Minimal request using saved settings:

```bash
curl -X POST http://localhost:8000/api/jobs \
  -F "file=@invoice.pdf"
```

Response:

```json
{ "job_id": "uuid" }
```

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
  "raw_ocr_response": null,
  "error": ""
}
```

## Prompt Preview

### `POST /api/prompt/preview`

Previews the final prompt. In CustomDB mode, `{{CUSTOMDB_SCHEMA_JSON}}` is replaced by the active schema.

```json
{
  "mode": "customdb",
  "settings": {}
}
```

## Model Probing

### `POST /api/probe/openai`

Lists models from the configured OpenAI-compatible API.

### `POST /api/probe/lmstudio`

Lists models from LM Studio.

### `POST /api/probe/ollama`

Lists models from Ollama.

## Batch Worker

The batch worker is isolated in `backend/batch_worker.py`. It scans folders on the backend machine, converts supported documents, writes JSON output, and moves or copies source files into the run folder.

Supported input extensions:

```text
.pdf, .png, .jpg, .jpeg, .webp, .tif, .tiff
```

When a batch run starts, the backend creates a timestamped folder inside `outputDir`, for example:

```text
batch_2026-05-21_14-30-00
```

Inside that run folder it creates:

- `output` for converted JSON files, or the pipeline name when `usePipelineName` is enabled.
- `processed` for source files after processing, including failed files.
- `batch.log` for run activity.
- `errors.log` for failed files and error details.

### `GET /api/batch/status`

Returns batch worker status, active config, run folder, result folder, totals, and recent items.

### `POST /api/batch/config`

Stores batch worker configuration without starting a scan.

### `GET /api/batch/browse?path=C:\Invoices`

Browses folders on the backend machine.

### `POST /api/batch/stop`

Stops the active batch worker if one is running.

### `POST /api/batch/run-once`

Runs one folder scan.

Example payload for `config` or `run-once`:

```json
{
  "inputDir": "C:\\Invoices\\in",
  "outputDir": "C:\\Invoices\\out",
  "mode": "customdb",
  "keepInputFiles": false,
  "usePipelineName": false
}
```

If `keepInputFiles` is `true`, the worker copies each source file into the run folder's `processed` folder and leaves the source file in `inputDir`. During the same running worker session, it remembers already processed file fingerprints so kept files are not immediately processed again.

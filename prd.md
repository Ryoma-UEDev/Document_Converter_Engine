# Product Requirements Document

## Product

Document Converter App

## Purpose

The app converts invoices and related business documents into reviewable structured data. It is a local-first Python backend engine with a browser workstation, meant for manual review and API-driven automation.

The backend must be usable independently of the bundled frontend. External systems should be able to submit documents through the API and treat the app as an automation link for document conversion. The current frontend is the operator workstation and admin tool: it supports manual upload/review, job monitoring, prompt/schema tuning, and backend settings management.

The app has a practical focus on Estonian business documents but is designed to work with any invoice or structured document. The UI supports three languages: English, Estonian, and Russian.

The product has three modes:

- CustomDB mode: the main mode being actively developed now.
- XML schema mode: a planned mode where the user uploads an XML schema/template file and the app adapts extraction and export around it.
- Arbitrary mode: a general extraction mode for documents that do not need a fixed target schema.

## Goals

- Make CustomDB invoice extraction reliable, fast, and easy to review.
- Provide a backend conversion engine that can be used directly by external automation.
- Keep the bundled frontend focused as a workstation/admin surface for review, monitoring, and settings control.
- Keep provider, OCR, prompt, schema, and mapping behavior configurable without code edits.
- Let the browser UI and external API clients use the same backend pipeline.
- Let the frontend monitor jobs submitted by the UI, Postman, or automation scripts.
- Reuse one schema-driven pipeline pattern where practical, while preserving mode-specific export behavior.
- Support local and cloud LLM providers interchangeably so the best pipeline can be found through testing.
- Build an automated testing layer that benchmarks model and prompt combinations and reports results visually.

## Core Workflow

The same backend pipeline must support both frontend-driven and API-driven workflows.

1. User chooses a mode.
2. User uploads a PDF or image.
3. App previews the document.
4. Backend runs optional OCR and then an LLM extraction prompt.
5. Frontend shows progress and completed result.
6. User reviews or edits the result.
7. User exports the mode-specific output.

## Modes

### CustomDB Mode

CustomDB is the primary mode.

Requirements:

- Use `customDbSchema` as the source of truth for the LLM prompt, review form defaults, additional fields, mapping paths, and exported JSON.
- Inject the active schema into the CustomDB prompt with `{{CUSTOMDB_SCHEMA_JSON}}`.
- Preserve the invoice-like editor for known invoice fields.
- Show additional root, nested, and item fields from the schema without code changes.
- Apply simple inbound `customJsonMapping` from extracted source paths into CustomDB target paths.
- Export reviewed JSON pruned to the active CustomDB schema.

### XML Schema Mode

XML schema mode is the second major mode after CustomDB.

The idea is similar to CustomDB prompt injection: the uploaded XML schema/template becomes the structure the model must extract toward. The important difference is export. CustomDB ends as JSON, but XML schema mode must export XML matching the uploaded schema/template.

Requirements:

- Allow the user to upload or select an XML schema/template file, referred to as XMSC in the product notes.
- Parse the XML schema/template into an internal structured representation that can be injected into the extraction prompt.
- Ask the LLM for structured data that can be validated and rendered back into the XML target.
- Provide a review view generated from the parsed XML schema/template where practical.
- Export XML that follows the uploaded schema/template structure.
- Keep the original uploaded schema/template available for the job so export can preserve required structure, tags, and ordering.

Design note:

- CustomDB and XML schema mode can share the same extraction pattern: source document plus injected target structure goes to the LLM, and the model returns structured data.
- They should not be treated as identical products, because XML mode has a stronger export contract: it must produce XML, not only a JSON object shaped like the target.

### Arbitrary Mode

Arbitrary mode is for flexible extraction when the user does not have a fixed schema.

Requirements:

- Use a general-purpose extraction prompt.
- Return all meaningful labels and values the model can identify.
- Do not require a schema editor or target mapping.
- Export plain text or a simple structured result suitable for inspection.

## Localisation Requirements

- The UI must support English, Estonian, and Russian.
- All user-visible strings must come from a localisation file or map, not be hardcoded in the frontend.
- The active language must be selectable at runtime without a page reload.
- The default committed localisation strings are a working baseline. Improved translations will be refined in subsequent commits.
- Backend error messages and API responses do not need to be localised in the first version.

## Settings Requirements

- The backend must merge built-in defaults with `earve_settings.json`.
- The frontend must load settings through `/api/bootstrap`.
- Users must be able to save backend settings through `/api/settings/save`.
- Settings must include:
  - provider: `openai`, `lmstudio`, or `ollama`
  - OpenAI-compatible base URL, API key, and model
  - LM Studio base URL and model
  - Ollama base URL and model
  - OCR mode: `none`, `google`, `lmstudio_vlm`, or `ollama_vlm`
  - Google Vision key
  - local OCR/VLM model
  - prompts for CustomDB, XML schema mode, arbitrary mode, and OCR
  - default pipeline mode in `pipelineSettings.mode`
  - `customDbSchema`
  - `customJsonMapping`
- `earve_settings.json` must remain ignored because it may contain secrets.
- Only curated, non-sensitive example prompts are committed to the repository. Operational prompts stay in `earve_settings.json`.

## Document Intake Requirements

- Accept PDF and image uploads from the frontend and API.
- Preview uploads in the frontend with zoom and pan.
- Send the original uploaded file to the backend.
- Validate image payloads before processing.
- Convert PDF input to an image for model processing.
- Support multi-page PDF extraction later, but keep the first workflow simple.

## OCR And LLM Requirements

- The frontend must not call OCR or LLM providers directly.
- The backend must support an OpenAI-compatible provider for cloud or hosted APIs.
- The backend must support LM Studio as a local provider.
- The backend must support Ollama as a local provider. Ollama exposes an OpenAI-compatible API at `/v1`, so it reuses the same client with a configured base URL.
- OCR modes:
  - `none`: send the document image directly to the extraction model.
  - `google`: run Google Vision OCR, then send OCR text to the extraction model.
  - `lmstudio_vlm`: run local VLM OCR through LM Studio, then send OCR text to the extraction model.
  - `ollama_vlm`: run local VLM OCR through Ollama, then send OCR text to the extraction model.
- Provider/model errors must be visible on the job record and in the frontend.

## Job And Monitoring Requirements

- API and UI submissions must create jobs in the same queue.
- Job records must include id, source, file name, mode, status, progress, stage, result, raw model response, raw OCR text, error, and timestamps.
- The frontend must poll jobs so external submissions appear while the UI is open.
- Completed jobs must be loadable into the matching mode tab.

## Testing And Benchmarking Requirements

The app is also a testbed for finding the best model and prompt combinations for invoice extraction. The testing layer is planned for a later milestone.

Requirements:

- Provide an automated test runner that submits a set of reference documents and compares extracted fields against expected values.
- Track per-field accuracy across runs, models, OCR modes, and prompt variants.
- Store test run results so they can be compared over time.
- Produce visual reports: field accuracy as pie or bar charts, per-model comparison tables.
- Keep test fixtures and expected outputs in a dedicated directory not containing sensitive prompts.
- Test runner must be runnable from the command line independently of the browser UI.

## Platform And Setup Requirements

- Clean Windows machine: `setup_requirements.bat` downloads a standalone Python runtime into `.standalone\python` and installs dependencies without requiring system Python. `serverstart.bat` starts the app.
- Developer Windows machine with Python: `serversetup.bat` creates a virtual environment, then `serverstart.bat` starts the app.
- Linux machine: equivalent shell scripts or a `Makefile` target creates a virtual environment, installs dependencies from `requirements.txt`, and starts the app with `uvicorn`. No OS-specific dependencies should be required.
- The app must run correctly on both Windows and Linux without code changes.

## API Requirements

- `GET /api/health`
- `GET /api/bootstrap`
- `GET /api/settings/default`
- `POST /api/settings/save`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/prompt/preview`
- `POST /api/probe/openai`
- `POST /api/probe/lmstudio`
- `POST /api/probe/ollama`

Future XML schema endpoints may include:

- `POST /api/xml-schema/preview`
- `POST /api/xml-schema/validate`
- `POST /api/xml-schema/export`

## Acceptance Criteria

- Clean Windows setup can install standalone Python and run the app without system Python.
- Developer setup on Windows or Linux can create a virtual environment and run the app.
- User can upload a supported document, preview it, run extraction, and see job progress.
- CustomDB extraction renders into the invoice-like editor.
- CustomDB additional schema fields appear without frontend code changes.
- CustomDB prompt preview shows the injected schema.
- API jobs without explicit settings use saved defaults.
- UI polling shows jobs submitted through external API clients.
- Arbitrary mode can extract general document data without a target schema.
- OpenAI-compatible settings and model probing use generic provider naming.
- Ollama can be configured as a provider and used for extraction and VLM OCR.
- UI language can be switched between English, Estonian, and Russian at runtime.
- XML schema mode has a clear planned path: upload schema/template, inject target structure, review extracted data, and export matching XML.
- Automated tests can be run from the command line and produce a field-accuracy report.

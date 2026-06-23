# PipeRunner

PipeRunner is a small local automation tool for running several converter pipelines one after another.

It is meant for benchmark work where you want to compare combinations such as:

- Google Vision OCR + Qwen extraction
- LM Studio VLM OCR + Gemma extraction
- Ollama OCR + Ollama extraction

The tool talks to the main Document Converter backend API. It does not replace the main app and does not perform conversion itself.

## What It Uses From The Main App

PipeRunner loads the current saved settings from:

```text
GET http://localhost:8000/api/settings/default
```

For each pipeline row it only changes:

- OCR provider
- OCR model, when the selected OCR provider needs a model
- LLM provider
- LLM model
- batch `keepInputFiles`
- batch `usePipelineName`

Everything else stays from the saved converter settings:

- prompts
- CustomDB schema
- mapping
- API keys
- model base URLs
- token limits
- timeout
- batch input/output folders
- batch conversion mode

## Start

Start the main converter backend first:

```bat
Win\serverstart.bat
```

Then start PipeRunner:

```bat
Tools\PipeRunner\PipeRunner_Start.bat
```

It opens:

```text
http://localhost:8060/
```

## Basic Workflow

1. Confirm the backend URL.
2. Check that the loaded batch input/output folders are correct.
3. Keep `Keep input files` enabled for benchmark runs.
4. Keep `Use pipeline name` enabled for benchmark runs.
5. Add pipeline rows with `+ Add pipeline`.
6. Select OCR provider/model on the left side of each row.
7. Select LLM provider/model on the right side of each row.
8. Use `Probe` buttons to populate model dropdowns.
9. Click `Save list`.
10. Click `Run pipelines`.

PipeRunner waits for the current batch run to finish before starting the next one. If one pipeline fails, the runner logs it and continues with the next pipeline.

## Output Folders

The main batch worker writes output under a timestamped batch folder:

```text
OutputRoot/
  batch_2026-06-16_14-30-00/
    OCR_GoogleVision_LLM_qwen3-27b/
    processed/
    batch.log
    errors.log
  batch_2026-06-16_15-05-12/
    OCR_LMStudioModel_LLM_qwen3-27b/
    processed/
    batch.log
    errors.log
```

The exact result folder path is shown in the PipeRunner report.

## Saved Presets

Pipeline rows and probed model lists are saved in:

```text
Tools/PipeRunner/pipelines.json
```

This file is intended to be edited or committed only if the model names are public-safe for your repo.

## Notes

- This tool is local-only and intended for development/benchmarking.
- It can run long jobs because it keeps the orchestration in Python instead of a browser tab.
- Stop requests stop after the current in-flight model call finishes. The converter backend cannot interrupt a running model HTTP request immediately.

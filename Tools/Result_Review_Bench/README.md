# Result Review Bench

Small local review tool for checking document conversion results side by side.

Current purpose:
- Browse an input document set and matching JSON outputs.
- Preview the source document next to the extracted result.
- Quickly inspect whether a conversion result looks correct before using it as test/reference data.

Planned purpose:
- Compare results from different OCR/LLM pipelines.
- Show larger test reports across models, providers, prompts, and schemas.
- Help build and maintain ground-truth datasets for converter testing.

Start with `RRB_Start.bat` on Windows. The tool runs a small local Python server and opens the browser UI.

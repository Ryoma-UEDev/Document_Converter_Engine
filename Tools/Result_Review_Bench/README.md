# Result Review Bench

Small local tool for comparing converted JSON results against ground-truth JSON.

## Folder Layout

Use three folders:

- `input`: source PDFs/images.
- `ground_truth`: expected JSON files.
- `outputs`: one subfolder per pipeline or test run.

```text
Dataset/
  input/
    document_001.pdf
    document_002.pdf

  ground_truth/
    document_001.json
    document_002.json

  outputs/
    pipeline_a/
      document_001.json
      document_002.json

    pipeline_b/
      document_001.json
      document_002.json
```

The bench matches files by filename stem.

## Features

- Scan output folders.
- Generate simple comparison reports.
- Inspect per-document scores.
- Open a document in review mode with the PDF/image on the left.
- Switch between ground truth and selected output JSON.
- Edit and save either JSON file.
- Highlight failed fields.

## Scoring Rules

The evaluator intentionally starts simple:

- `exact`: default rule for dates, numbers, IDs, totals, item amounts, units, prices, and sums.
- `normalized`: names and addresses, using lowercase/collapsed spacing.
- `prefix`: `items[].title`, using the configured first-character count.
- `ignored`: `description`, `src_path`, and `items[].description`.

`Scan Dataset` only discovers documents and pipeline folders. Use `Generate Report` separately when you want to run or refresh scoring.

Start with `RRB_Start.bat` on Windows. The tool runs a small local Python server and opens the browser UI.

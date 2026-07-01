# Tests

This folder contains smoke, UI, and opt-in integration tests for the Document Converter app.

The tests assume the backend is already running:

```bat
Win\serverstart.bat
```

Then open or test:

```text
http://localhost:8000/
```

## Folder Layout

```text
Tests/
  TestDocument.pdf  (optional local integration-test document, ignored by git)
  Postman/
    document_converter.postman_collection.json
    local.postman_environment.json
  playwright/
    helpers/
      ui-integration.js
    package.json
    playwright.config.js
    run-playwright-ui.bat
    specs/
      standalone/
        api-smoke.spec.js
        ui-smoke.spec.js
        settings-save.spec.js
        prompt-schema-inject.spec.js
        language-switch.spec.js
      integration/
        provider-probe.spec.js
        document-job.spec.js
```

## Postman

Use Postman when you want quick manual API checks.

1. Open Postman.
2. Import `Tests/Postman/document_converter.postman_collection.json`.
3. Import `Tests/Postman/local.postman_environment.json`.
4. Select the `Document Converter Local` environment.
5. Run the collection or run individual requests.

The default requests are safe and should not call any LLM:

- `GET /api/health`
- `GET /api/bootstrap`
- `GET /api/settings/default`
- `POST /api/prompt/preview`
- `GET /api/jobs`
- `GET /api/batch/status`

There are also two manual job requests:

```text
Manual - Submit document job
Manual - Get last submitted job
```

They are skipped by default unless the required environment values are present. To use them:

1. Open the environment.
2. Set `runUploadJob` to `true`.
3. Set `sampleFilePath` to a local PDF or image path.
4. Run `Manual - Submit document job`.
5. Run `Manual - Get last submitted job` after the submit request stores `jobId`.

The submit request may call OCR/LLM providers depending on your saved settings, so treat it as a real pipeline run.

## Playwright

Use Playwright when you want browser smoke tests.

From the repo root:

```bat
cd Tests\playwright
npm install
npx playwright install
npm test
```

Or run from the repo root with:

```bat
npx playwright test -c Tests\playwright\playwright.config.js
```

The Playwright tests are split into standalone and integration categories.

Standalone tests do not run real document conversion jobs and should not call model providers.

`standalone/api-smoke.spec.js` checks:

- backend API health
- settings/default response
- prompt preview response
- batch status response

`standalone/ui-smoke.spec.js` checks:

- frontend page loads
- settings modal can be opened
- no browser console errors are thrown during the basic load flow

`standalone/settings-save.spec.js` checks:

- settings modal save flow opens the backend overwrite confirmation
- the save request is sent successfully
- the request is intercepted so the real `earve_settings.json` is not overwritten

`standalone/prompt-schema-inject.spec.js` checks:

- CustomDB base prompt edits appear in the injected preview
- removing the temporary edit removes it from the injected preview again

`standalone/language-switch.spec.js` checks:

- EN, ET, and RU buttons update visible UI title text

Integration tests are opt-in because they probe real providers and can run real document jobs.
They are skipped unless `RUN_INTEGRATION=true` is set.

`integration/provider-probe.spec.js` checks:

- the settings UI opens
- the provider selector is changed through the UI
- the Probe button is clicked through the UI
- the first provider that fills the model dropdown is accepted

`integration/document-job.spec.js` checks:

- the settings UI probes providers and selects the first available model
- the test document is uploaded through the frontend
- Extract Data is clicked through the frontend
- the UI reaches a completed job state

Run everything:

```bat
npm.cmd test
```

Run only standalone tests:

```bat
npm.cmd run test:standalone
```

Run only backend API smoke tests:

```bat
npm.cmd run test:api
```

Run only frontend UI smoke tests:

```bat
npm.cmd run test:ui
```

Open Playwright UI mode with a prompt for integration tests:

```bat
Tests\playwright\run-playwright-ui.bat
```

Choose `N` for normal standalone/UI work. Choose `Y` when you want the UI to include real provider probes and the document job test.

Run all integration tests:

```bat
set RUN_INTEGRATION=true
npm.cmd run test:integration
```

The document-job integration test additionally needs a readable test document.
By default, it looks for a local ignored file:

```text
Tests/TestDocument.pdf
```

PowerShell uses `$env:` instead of `set`:

```powershell
$env:RUN_INTEGRATION = "true"
npm.cmd run test:integration
```

To test a different file, set `TEST_DOCUMENT` before running integration:

```powershell
$env:RUN_INTEGRATION = "true"
$env:TEST_DOCUMENT = "C:\Path\To\other-test-document.pdf"
npm.cmd run test:integration
```

### Playwright Results

Console output gives the quick pass/fail result.

The HTML report is written to:

```text
Tests/playwright/playwright-report/index.html
```

Open it with:

```bat
cd Tests\playwright
npm run report
```

JSON results and failure traces/screenshots are written under:

```text
Tests/playwright/test-results/
```

These generated result folders are ignored by git.

## Notes

- These are smoke tests, not model-quality tests.
- They do not verify invoice extraction accuracy.
- The manual Postman job requests are intentionally disabled by default so you do not accidentally spend API credits or start a slow local model job.
- Playwright integration tests are also disabled by default. Enable them only when you intentionally want to probe providers or run a real document job.
- Later, the Result Review Bench can become the accuracy layer for comparing pipeline output folders against ground truth JSON.

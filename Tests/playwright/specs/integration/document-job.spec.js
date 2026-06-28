const { test, expect } = require('@playwright/test');
const path = require('path');
const {
  disableOcrInUi,
  findFirstAvailableProviderInUi,
  hasReadableTestDocument,
  integrationEnabled,
  openSettings,
  testDocumentPath
} = require('../../helpers/ui-integration');

test.describe('Integration document job UI tests', () => {
  test('uploads a document in the UI and runs it with the first available provider', async ({ page }) => {
    test.skip(!integrationEnabled(), 'Set RUN_INTEGRATION=true to run real document jobs.');
    test.skip(!hasReadableTestDocument(), 'Set TEST_DOCUMENT to a readable PDF or image file.');
    test.setTimeout(Number(process.env.TEST_JOB_TIMEOUT_MS || 600000) + 60000);

    // This test drives the same UI flow a user would use: settings -> probe
    // provider -> pick model -> upload document -> click Extract Data.
    const modal = await openSettings(page);
    const provider = await findFirstAvailableProviderInUi(page);
    test.skip(!provider, 'No provider filled the UI model list.');

    // Keep the real-job test focused on the selected LLM/VLM provider. The app
    // sends these UI settings with the job request without saving them to disk.
    await disableOcrInUi(modal);
    await modal.getByRole('button', { name: /^Ready$/i }).click();

    await page.getByRole('button', { name: /CustomDB/i }).first().click();

    const filePath = testDocumentPath();
    const fileName = path.basename(filePath);
    await page.locator('input[type="file"][accept*="application/pdf"]').setInputFiles(filePath);
    await expect(page.locator('span.font-medium.truncate').filter({ hasText: fileName }).first()).toBeVisible();

    const jobResponse = page.waitForResponse(
      (response) => response.url().includes('/api/jobs') && response.request().method() === 'POST',
      { timeout: 30000 }
    );
    await page.getByRole('button', { name: /Extract Data/i }).click();
    const createJobResponse = await jobResponse;
    expect(createJobResponse.ok()).toBeTruthy();
    const { job_id: jobId } = await createJobResponse.json();
    expect(jobId).toBeTruthy();

    const finalState = await waitForDocumentJobUi(page, jobId);
    expect(finalState).toBe('completed');
  });
});

async function waitForDocumentJobUi(page, jobId) {
  const timeoutMs = Number(process.env.TEST_JOB_TIMEOUT_MS || 600000);
  const currentJobHeader = page.getByText(new RegExp(`Current Job:\\s*${escapeRegExp(jobId)}`));
  await expect(currentJobHeader).toBeVisible({ timeout: 10000 });
  const completed = await page.waitForFunction((id) => {
    const panels = Array.from(document.querySelectorAll('div.mt-3.border.rounded.bg-white.p-2'));
    const currentPanel = panels.find((panel) => panel.innerText.includes(`Current Job: ${id}`));
    if (!currentPanel) return false;

    const text = currentPanel.innerText;
    if (/Failed/i.test(text)) return { status: 'failed', text };
    if (/Completed\s*\(100%\)/i.test(text)) return { status: 'completed', text };
    return false;
  }, jobId, { timeout: timeoutMs }).catch(async () => {
    const bodyText = await page.locator('body').innerText().catch(() => '');
    throw new Error(`Timed out waiting for document job ${jobId} to complete in the current-job UI panel.\n${bodyText.slice(0, 2000)}`);
  });

  const result = await completed.jsonValue();
  if (result.status === 'failed') {
    const lastErrorText = await page.locator('.border-red-300.bg-red-50').innerText().catch(() => '');
    throw new Error(`Document job ${jobId} failed in UI:\n${(lastErrorText || result.text || '').slice(0, 2000)}`);
  }
  return result.status;
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

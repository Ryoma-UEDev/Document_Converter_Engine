const { test, expect } = require('@playwright/test');

test.describe('Standalone UI smoke tests', () => {
  test.beforeEach(async ({ page }) => {
    // Force English labels so selectors stay stable even if a previous manual
    // run saved another UI language in localStorage.
    await page.addInitScript(() => localStorage.setItem('ui_lang', 'en'));
  });

  test('main page loads and settings dialog opens without console errors', async ({ page }) => {
    const consoleErrors = [];

    // Collect browser-side errors while the page loads and while we click the
    // first basic UI control. A smoke test should fail loudly if Vue crashes.
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    // Open the app through the running FastAPI backend.
    await page.goto('/');
    await expect(page).toHaveTitle(/Document Converter/i);

    // Wait for visible app text. If CDN scripts fail to load, this usually
    // times out because Vue never mounts the UI.
    await expect(page.locator('body')).toContainText(/Document Converter|CustomDB|XML|Batch/i);

    // The settings button uses an aria-label translated from the UI text map.
    const settingsButton = page.getByRole('button', { name: /configure ai/i });
    await expect(settingsButton).toBeVisible();
    await settingsButton.click();

    // The modal should expose AI/OCR/prompt/schema settings text.
    await expect(page.locator('body')).toContainText(/AI|OCR|Prompt|CustomDB/i);

    expect(consoleErrors).toEqual([]);
  });
});

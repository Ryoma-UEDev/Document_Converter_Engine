const { test, expect } = require('@playwright/test');

test.describe('Standalone settings save tests', () => {
  test.beforeEach(async ({ page }) => {
    // Keep selectors predictable regardless of the language used during manual
    // testing before this run.
    await page.addInitScript(() => localStorage.setItem('ui_lang', 'en'));
  });

  test('settings save sends a backend save request and handles success', async ({ page }) => {
    let savedPayload = null;

    // Intercept the save request so this test proves the frontend behavior
    // without overwriting the real private earve_settings.json file.
    await page.route('**/api/settings/save', async (route) => {
      savedPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'saved' })
      });
    });

    await page.goto('/');
    await page.getByRole('button', { name: /configure ai/i }).click();
    await page.getByRole('button', { name: /^save$/i }).click();

    // The app asks for confirmation before it writes backend settings.
    await expect(page.getByText(/Override the backend settings/i)).toBeVisible();
    await page.getByRole('button', { name: /^override$/i }).click();

    await expect(page.getByText(/Backend settings saved/i)).toBeVisible();
    expect(savedPayload).toBeTruthy();
    expect(savedPayload.settings).toBeTruthy();
    expect(savedPayload.settings).toHaveProperty('provider');
    expect(savedPayload.settings).not.toHaveProperty('filterDuplicates');
  });
});

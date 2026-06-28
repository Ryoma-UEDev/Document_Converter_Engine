const { test, expect } = require('@playwright/test');
const {
  findFirstAvailableProviderInUi,
  integrationEnabled,
  openSettings
} = require('../../helpers/ui-integration');

test.describe('Integration provider probe UI tests', () => {
  test('probes providers through the settings UI and fills the model list', async ({ page }) => {
    test.skip(!integrationEnabled(), 'Set RUN_INTEGRATION=true to probe real model providers.');
    test.setTimeout(90000);

    // This is intentionally a UI test: it opens settings, changes the provider
    // selector, clicks Probe, and verifies the model picker receives options.
    await openSettings(page);
    const provider = await findFirstAvailableProviderInUi(page);

    expect(provider, 'No provider filled the UI model list.').toBeTruthy();
    await expect(page.locator('.fixed').filter({ hasText: /AI Settings & Prompts/i }).first()).toContainText(provider.label);
  });
});

const { test, expect } = require('@playwright/test');

test.describe('Standalone CustomDB schema injection tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('ui_lang', 'en'));
  });

  test('editing the CustomDB base prompt updates and restores the injected preview', async ({ page }) => {
    const marker = 'PLAYWRIGHT_TEST_PROMPT_MARKER';

    await page.goto('/');
    await page.getByRole('button', { name: /configure ai/i }).click();
    await page.getByRole('button', { name: /CustomDB setup/i }).click();

    // In the schema tab the visible textareas are: schema JSON, base prompt,
    // and read-only injected preview.
    const schemaModal = page.locator('.fixed').filter({ hasText: /AI Settings & Prompts/i }).first();
    const textareas = schemaModal.locator('textarea');
    const basePrompt = textareas.nth(1);
    const injectedPreview = textareas.nth(2);
    const originalPrompt = await basePrompt.inputValue();

    // Add a temporary word, apply the schema injection, and confirm that the
    // final rendered prompt includes the temporary word.
    await basePrompt.fill(`${marker}\n${originalPrompt}`);
    await page.getByRole('button', { name: /Apply Schema/i }).click();
    await page.getByRole('button', { name: /^OK$/i }).click();
    await expect(injectedPreview).toHaveValue(new RegExp(marker));

    // Remove the temporary word and run the same injection cycle. This proves
    // the base prompt can be restored without leaving test text in the preview.
    await basePrompt.fill(originalPrompt);
    await page.getByRole('button', { name: /Apply Schema/i }).click();
    await page.getByRole('button', { name: /^OK$/i }).click();
    await expect(injectedPreview).not.toHaveValue(new RegExp(marker));
  });
});

const { test, expect } = require('@playwright/test');

test.describe('Standalone language switch tests', () => {
  test('language buttons update the visible UI text', async ({ page }) => {
    // Start from a known language, then switch through the other available UI
    // translations and verify the title text changes each time.
    await page.addInitScript(() => localStorage.setItem('ui_lang', 'en'));
    await page.goto('/');

    await expect(page.locator('h1')).toContainText('Document Converter');

    await page.getByRole('button', { name: 'ET' }).click();
    await expect(page.locator('h1')).toContainText('Dokumendi konverter');

    await page.getByRole('button', { name: 'RU' }).click();
    await expect(page.locator('h1')).toContainText('Конвертер документов');

    await page.getByRole('button', { name: 'EN' }).click();
    await expect(page.locator('h1')).toContainText('Document Converter');
  });
});

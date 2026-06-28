const fs = require('fs');
const path = require('path');
const { expect } = require('@playwright/test');

const PROVIDERS = {
  openai: {
    label: 'OpenAI-compatible',
    optionLabel: /OpenAI-Compatible API/i
  },
  lmstudio: {
    label: 'LM Studio',
    optionLabel: /LM Studio/i
  },
  ollama: {
    label: 'Ollama',
    optionLabel: /Ollama/i
  }
};

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function integrationEnabled() {
  return String(process.env.RUN_INTEGRATION || '').toLowerCase() === 'true';
}

function providerOrder() {
  // TEST_PROVIDER_ORDER lets a local run prefer a provider without changing app
  // settings. Example: TEST_PROVIDER_ORDER=lmstudio,ollama,openai
  if (process.env.TEST_PROVIDER_ORDER) {
    return unique(process.env.TEST_PROVIDER_ORDER.split(',').map((item) => item.trim()));
  }
  return ['openai', 'lmstudio', 'ollama'];
}

function testDocumentPath() {
  // Use the default test document if the caller does not provide a custom path.
  return process.env.TEST_DOCUMENT ||
    process.env.TEST_DOCUMENT_PATH ||
    path.resolve(__dirname, '..', '..', 'TestDocument.pdf');
}

function hasReadableTestDocument() {
  const filePath = testDocumentPath();
  return Boolean(filePath && fs.existsSync(filePath));
}

async function openSettings(page) {
  await page.addInitScript(() => localStorage.setItem('ui_lang', 'en'));
  await page.goto('/');
  await expect(page.locator('h1')).toContainText('Document Converter');
  await page.getByRole('button', { name: /configure ai/i }).click();
  return settingsModal(page);
}

function settingsModal(page) {
  return page.locator('.fixed').filter({ hasText: /AI Settings & Prompts/i }).first();
}

function providerSelect(modal) {
  return modal.locator('select').first();
}

function modelSelect(modal) {
  // In the AI tab the visible selects are provider, model picker, then OCR
  // provider. The second select is the model picker for the selected provider.
  return modal.locator('select').nth(1);
}

function ocrProviderSelect(modal) {
  return modal.locator('select').nth(2);
}

async function setProvider(modal, providerName) {
  await providerSelect(modal).selectOption(providerName);
  await expect(providerSelect(modal)).toHaveValue(providerName);
}

async function probeProviderFromUi(page, providerName) {
  const modal = settingsModal(page);
  await setProvider(modal, providerName);

  // Click the visible LLM provider Probe button and wait for the model picker
  // to receive at least one real option after "Select probed model".
  const probeButton = modal.locator('button').filter({ hasText: /^Probe$/i }).first();
  await expect(probeButton).toBeVisible();
  await probeButton.scrollIntoViewIfNeeded();
  await probeButton.click();

  const picker = modelSelect(modal);
  try {
    await expect.poll(async () => picker.locator('option').count(), {
      timeout: Number(process.env.TEST_PROVIDER_PROBE_TIMEOUT_MS || 30000)
    }).toBeGreaterThan(1);
  } catch (error) {
    return null;
  }

  const firstModel = await picker.locator('option').nth(1).getAttribute('value');
  if (!firstModel) return null;

  // Selecting a model in the picker also copies it into the provider model
  // input through the app's normal change handler.
  await picker.selectOption(firstModel);

  return {
    name: providerName,
    label: PROVIDERS[providerName].label,
    model: firstModel
  };
}

async function findFirstAvailableProviderInUi(page) {
  const modal = settingsModal(page);
  const selectedProvider = await providerSelect(modal).inputValue();
  for (const providerName of unique([selectedProvider, ...providerOrder()])) {
    const provider = await probeProviderFromUi(page, providerName);
    if (provider) return provider;
  }
  return null;
}

async function disableOcrInUi(modal) {
  await ocrProviderSelect(modal).selectOption('none');
}

module.exports = {
  disableOcrInUi,
  findFirstAvailableProviderInUi,
  hasReadableTestDocument,
  integrationEnabled,
  openSettings,
  testDocumentPath
};

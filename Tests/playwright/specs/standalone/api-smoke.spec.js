const { test, expect } = require('@playwright/test');

test.describe('Standalone API smoke tests', () => {
  test('core read-only endpoints respond with the expected shape', async ({ request }) => {
    // Health is the smallest possible backend check: if this fails, the server
    // is probably not running or BASE_URL points at the wrong place.
    const health = await request.get('/api/health');
    expect(health.ok()).toBeTruthy();
    const healthData = await health.json();
    expect(healthData.status).toBe('ok');

    // Bootstrap is what the frontend calls on startup. It should return the
    // active backend URL and effective settings.
    const bootstrap = await request.get('/api/bootstrap');
    expect(bootstrap.ok()).toBeTruthy();
    const bootstrapData = await bootstrap.json();
    expect(bootstrapData.settings).toBeTruthy();
    expect(typeof bootstrapData.backendUrl).toBe('string');

    // Settings/default should include the schema and batch config that the UI
    // depends on. This does not call any model provider.
    const settings = await request.get('/api/settings/default');
    expect(settings.ok()).toBeTruthy();
    const settingsData = await settings.json();
    expect(settingsData.customDbSchema).toBeTruthy();
    expect(settingsData.batchSettings).toBeTruthy();

    // Jobs are in-memory. A fresh backend usually returns an empty array.
    const jobs = await request.get('/api/jobs');
    expect(jobs.ok()).toBeTruthy();
    expect(Array.isArray(await jobs.json())).toBeTruthy();

    // Batch status is safe to query and should always expose a running flag.
    const batch = await request.get('/api/batch/status');
    expect(batch.ok()).toBeTruthy();
    const batchData = await batch.json();
    expect(batchData).toHaveProperty('running');
  });

  test('CustomDB prompt preview injects the active schema', async ({ request }) => {
    // This tests prompt rendering only. It does not submit a document and does
    // not call OpenAI, LM Studio, Ollama, or Google Vision.
    const response = await request.post('/api/prompt/preview', {
      data: {
        mode: 'customdb',
        settings: {}
      }
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(typeof data.prompt).toBe('string');
    expect(data.prompt).toContain('JSON schema exactly like this');
    expect(Array.isArray(data.warnings)).toBeTruthy();
  });
});

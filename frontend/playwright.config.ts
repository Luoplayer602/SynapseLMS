import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0, timeout: 90_000,
  expect: { timeout: 15_000 },
  use: { baseURL: 'http://127.0.0.1:5180', browserName: 'chromium', trace: 'retain-on-failure' },
  webServer: [
    { command: process.env.SYNAPSE_E2E_PYTHON
      ? `"${process.env.SYNAPSE_E2E_PYTHON}" ../backend/tests/e2e_server.py`
      : 'uv run --project ../backend python ../backend/tests/e2e_server.py',
      url: 'http://127.0.0.1:8011/api/v1/health', reuseExistingServer: false, timeout: 60_000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5180 --strictPort', url: 'http://127.0.0.1:5180', reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8011/api/v1' } },
  ],
})

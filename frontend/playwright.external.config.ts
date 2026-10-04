import { defineConfig } from '@playwright/test'

// Start backend/tests/e2e_server.py and Vite on 5180 separately on Windows.
// The test API uses a temporary SQLite database and never touches Docker data.
export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0, timeout: 90_000,
  expect: { timeout: 15_000 },
  use: { baseURL: 'http://127.0.0.1:5180', browserName: 'chromium', trace: 'retain-on-failure' },
  outputDir: './test-results/external-qa',
})

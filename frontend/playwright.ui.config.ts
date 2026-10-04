import { defineConfig } from '@playwright/test'

// Start Vite on 5182 separately. These UI checks mock APIs and need no test DB.
export default defineConfig({
  testDir: './e2e', testMatch: 'dashboard.spec.ts', workers: 1, retries: 0, timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:5182', browserName: 'chromium', trace: 'retain-on-failure' },
  outputDir: './test-results/dashboard-qa',
})

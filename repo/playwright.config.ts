import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for public/task tests.
 *
 * These tests run against a live Langflow instance (e.g. the Docker container
 * exposed on port 9090).  No webServer is started here — the server is assumed
 * to already be running.
 *
 * The base URL can be overridden via the PLAYWRIGHT_BASE_URL environment
 * variable (e.g. PLAYWRIGHT_BASE_URL=http://localhost:9090).
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60 * 1000, // 60 seconds per test
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:9090",
    trace: "on-first-retry",
    extraHTTPHeaders: {
      Accept: "application/json",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

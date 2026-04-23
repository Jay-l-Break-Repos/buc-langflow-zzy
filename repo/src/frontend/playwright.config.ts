import { defineConfig, devices } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { PORT } from "./src/customization/config-constants";

dotenv.config();
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
/**
 * See https://playwright.dev/docs/test-configuration.
 */

// The API port for the running Langflow backend.
// In the evaluation environment the Docker container runs on 9090.
// In local dev the backend runs on 7860 (proxied via frontend on 3000).
const API_BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.API_BASE_URL ||
  `http://localhost:${PORT || 3000}/`;

export default defineConfig({
  testDir: "./tests",
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 3,
  /* Opt out of parallel tests on CI. */
  workers: 2,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  timeout: 5 * 60 * 1000, // 5 minutes
  // reporter: [
  //   ["html", { open: "never", outputFolder: "playwright-report/test-results" }],
  // ],
  reporter: process.env.CI ? "blob" : "html",
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: `http://localhost:${PORT || 3000}/`,

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: "on-first-retry",
  },

  globalTeardown: require.resolve("./tests/globalTeardown.ts"),

  /* Configure projects for major browsers */
  projects: [
    {
      // ----------------------------------------------------------------
      // "api" project: runs tests/public/** directly against the backend.
      // No webServer is needed — the server is assumed to be running.
      // Used by the evaluation system which starts the Docker container
      // on port 9090 and runs: npx playwright test --project=api
      // ----------------------------------------------------------------
      name: "api",
      testMatch: "**/public/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: API_BASE_URL,
      },
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          // headless: false,
        },
        contextOptions: {
          // chromium-specific permissions
          permissions: ["clipboard-read", "clipboard-write"],
        },
      },
    },
    // {
    //   name: "firefox",
    //   use: {
    //     ...devices["Desktop Firefox"],
    //     launchOptions: {
    //       // headless: false,
    //       firefoxUserPrefs: {
    //         "dom.events.asyncClipboard.readText": true,
    //         "dom.events.testing.asyncClipboard": true,
    //       },
    //     },
    //   },
    // },
    // {
    //   name: "safari",
    //   use: {
    //     ...devices["Desktop Safari"],
    //     launchOptions: {
    //       // headless: false,
    //     },
    //   },
    // },
    // {
    //   name: "arc",
    //   use: {
    //     ...devices["Desktop Arc"],
    //     launchOptions: {
    //       // headless: false,
    //     },
    //   },
    // },
    // {
    //   name: "firefox",
    //   use: {
    //     ...devices["Desktop Firefox"],
    //     launchOptions: {
    //       headless: false,
    //       firefoxUserPrefs: {
    //         "dom.events.asyncClipboard.readText": true,
    //         "dom.events.testing.asyncClipboard": true,
    //       },
    //     },
    //   },
    // },
  ],
  webServer: [
    {
      command:
        "uv run uvicorn --factory langflow.main:create_app --host localhost --port 7860 --loop asyncio",
      port: 7860,
      env: {
        LANGFLOW_DATABASE_URL: "sqlite:///./temp",
        LANGFLOW_AUTO_LOGIN: "true",
      },
      stdout: "ignore",

      reuseExistingServer: true,
      timeout: 120 * 750,
    },
    {
      command: "npm start",
      port: PORT || 3000,
      env: {
        VITE_PROXY_TARGET: "http://localhost:7860",
      },
      reuseExistingServer: true,
    },
  ],
});

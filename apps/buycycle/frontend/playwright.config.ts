import { defineConfig, devices } from "@playwright/test";
const baseURL = process.env.BUYCYCLE_E2E_URL ?? "http://127.0.0.1:4178";
const target = new URL(baseURL);
if (!["127.0.0.1", "localhost", "[::1]"].includes(target.hostname))
  throw new Error("Buycycle browser tests require a local synthetic server.");
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.BUYCYCLE_E2E_URL
    ? undefined
    : {
        command:
          "npm run build -w @f0rge/buycycle-frontend && npm exec -w @f0rge/buycycle-frontend -- vite preview --host 127.0.0.1 --port 4178",
        cwd: new URL("../../../", import.meta.url).pathname,
        url: baseURL,
        reuseExistingServer: false,
        timeout: 120000,
      },
});

import { defineConfig, devices } from "@playwright/test";

/** e2e 配置：跑 dev 服务（http://localhost:3011），不自动起服务（手动起更可控）。 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // 改后端 state 的测试串行最稳
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3011",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});

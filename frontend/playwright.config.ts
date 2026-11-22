import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", timeout: 60000, expect: { timeout: 15000 }, fullyParallel: false,
  use: { baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3103", trace: "retain-on-failure",
    launchOptions: process.env.E2E_CHROME_PATH ? { executablePath: process.env.E2E_CHROME_PATH } : {} },
  projects: [{name:"desktop",use:{...devices["Desktop Chrome"]}},
    {name:"mobile",use:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}}],
  webServer: {command:"npm run dev:e2e",url:"http://127.0.0.1:3103/login",reuseExistingServer:process.env.E2E_REUSE_SERVER === "1" || !process.env.CI,timeout:120000},
});

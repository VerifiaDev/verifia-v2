// Frontend-backend entegrasyon testi.
//
// İki gerçek sunucu açılır:
//   backend : backend_v2/tests/fake_server.py  (gerçek FastAPI uygulaması: yollar, CORS, ara katmanlar,
//             pipeline; yalnızca Groq ve Tavily yerine sahte servisler, anahtar ve kota gerekmez)
//   frontend: yayın derlemesi (`next start`), NEXT_PUBLIC_API_BASE_URL bu backend'i gösterir
//
// Frontend önceden şu ortamla derlenmiş olmalıdır (CI bunu yapar):
//   NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8799 npm run build
//
// Çalıştırma (depo kökünden):
//   cd e2e && npm ci && npx playwright install chromium && npm test
import { defineConfig, devices } from "@playwright/test";

const BACKEND_PORT = process.env.E2E_BACKEND_PORT ?? "8799";
const FRONTEND_PORT = process.env.E2E_FRONTEND_PORT ?? "3000";
const PYTHON = process.env.PYTHON ?? "python3";

export const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    // localhost: backend'in CORS listesindeki köken (http://localhost:3000)
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "masaustu", use: { ...devices["Desktop Chrome"] } },
    { name: "telefon", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `${PYTHON} tests/fake_server.py`,
      cwd: "../backend_v2",
      url: `${BACKEND_URL}/health`,
      env: { PORT: BACKEND_PORT, FAKE_DELAY: "0.3" },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: "pipe",
    },
    {
      command: `npx next start -p ${FRONTEND_PORT}`,
      cwd: "..",
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});

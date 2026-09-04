import { defineConfig } from "@playwright/test";

// The backend (Django/Channels) must already be running separately on
// :8000 — see README for `python manage.py runserver`. Playwright only
// manages the frontend dev server here.
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://localhost:5173",
  },
  webServer: {
    command: "npm run dev -- --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
});

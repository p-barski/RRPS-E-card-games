import { expect, test, type Page } from "@playwright/test";

// Whole-system smoke tests: drive the real running frontend against the
// real running backend (see README for how to start both) through a full
// bot game for each title. Exhaustive rule correctness lives in the
// backend's unit/integration suites — this only checks the golden path
// renders and completes without errors. Rounds now play out through a
// ~2s reveal/result/discard animation before the hand re-enables, so we
// poll for an enabled button rather than clicking on a fixed cadence.
async function playUntilResult(page: Page, maxMs: number) {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    if (await page.locator(".result").count()) return;
    const button = page.locator(".hand button:not([disabled])").first();
    if (await button.count()) {
      await button.click();
      await page.waitForTimeout(150);
    } else {
      await page.waitForTimeout(300);
    }
  }
}

test("RPS: play a full game against the bot", async ({ page }) => {
  test.setTimeout(90000);
  const consoleErrors: string[] = [];
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/");
  await page.getByText("Restricted Rock Paper Scissors").click();
  await page.getByRole("button", { name: "Play vs Bot" }).click();
  await page.waitForURL(/\/rps\//);
  await expect(page.locator(".hand")).toBeVisible();

  await playUntilResult(page, 70000);

  await expect(page.locator(".result")).toBeVisible({ timeout: 15000 });
  expect(consoleErrors).toEqual([]);
});

test("E-card: play a full 12-match game against the bot", async ({ page }) => {
  test.setTimeout(300000);
  const consoleErrors: string[] = [];
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto("/");
  await page.getByText("E-card", { exact: true }).click();
  await page.getByRole("button", { name: "Play vs Bot" }).click();
  await page.waitForURL(/\/ecard\//);

  await playUntilResult(page, 270000);

  await expect(page.locator(".result")).toBeVisible({ timeout: 20000 });
  expect(consoleErrors).toEqual([]);
});

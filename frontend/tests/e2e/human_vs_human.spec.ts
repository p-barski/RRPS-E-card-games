import { expect, test } from "@playwright/test";

// Two separate browser contexts = two separate anonymous player cookies,
// exercising the create-room / join-by-code / websocket-sync path end to
// end (not just the vs-bot path the other smoke test covers).
test("RPS: two players can create, join, and finish a room together", async ({ browser }) => {
  test.setTimeout(90000);
  const hostCtx = await browser.newContext();
  const guestCtx = await browser.newContext();
  const host = await hostCtx.newPage();
  const guest = await guestCtx.newPage();

  await host.goto("/");
  await host.getByText("Restricted Rock Paper Scissors").click();
  await host.getByRole("button", { name: "Create Room" }).click();
  await host.waitForURL(/\/rps\//);
  const code = host.url().split("/").pop()!;
  expect(code).toMatch(/^[A-Z0-9]{6}$/);

  await guest.goto("/");
  await guest.getByPlaceholder("Room code").fill(code);
  await guest.getByRole("button", { name: "Join Room" }).click();
  await guest.waitForURL(/\/rps\//);

  await expect(host.locator(".hand")).toBeVisible();
  await expect(guest.locator(".hand")).toBeVisible();

  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    if (await host.locator(".result").count()) break;
    const hostBtn = host.locator(".hand button:not([disabled])").first();
    const guestBtn = guest.locator(".hand button:not([disabled])").first();
    if (await hostBtn.count()) await hostBtn.click();
    if (await guestBtn.count()) await guestBtn.click();
    await host.waitForTimeout(300);
  }

  await expect(host.locator(".result")).toBeVisible({ timeout: 15000 });
  await expect(guest.locator(".result")).toBeVisible({ timeout: 15000 });

  await hostCtx.close();
  await guestCtx.close();
});

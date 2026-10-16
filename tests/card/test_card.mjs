// Browser test of raykube-lock-card with a mocked hass object.
// Run: node tests/card/test_card.mjs [screenshot_dir]   (needs playwright + chromium)
import { chromium } from "playwright";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const shots = process.argv[2];
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
});
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("file://" + path.join(here, "harness.html"));

const calls = () => page.evaluate(() => window.calls.splice(0));
const card = page.locator("raykube-lock-card ha-card");

// Compact tile
await assert.doesNotReject(card.waitFor());
assert.equal(await page.locator("raykube-lock-card .name").textContent(), "Drzwi wejściowe");
assert.match(await page.locator("raykube-lock-card .secondary").textContent(), /^Zamknięty · 15 minut temu$/);
if (shots) await page.locator("#host").screenshot({ path: path.join(shots, "1-tile.png") });

// Tap locks
const box = await card.boundingBox();
await page.mouse.click(box.x + 60, box.y + box.height / 2);
assert.deepEqual(await calls(), [["lock", "lock", { entity_id: "lock.raykube_a1_ultra_d9f494_zamek" }]]);

// Long press opens the panel (and the following click does not close it)
await page.mouse.move(box.x + 60, box.y + box.height / 2);
await page.mouse.down();
await page.waitForTimeout(700);
await page.mouse.up();
await page.mouse.click(10, 10); // click right after the hold, on the backdrop
const panel = page.locator("raykube-lock-panel");
await panel.waitFor();
await page.waitForTimeout(300);
assert.equal(await panel.locator(".hero .state").textContent(), "Zamknięty");
assert.match(await panel.locator(".hero .when").textContent(), /Zmiana: 15 minut temu · na zamku/);
const chips = await panel.locator(".chip").allTextContents();
assert.equal(chips.length, 3);
assert.match(chips.join("|"), /Bateria.*Wysoki/s);
assert.match(chips.join("|"), /Auto-zamykanie.*30 s/s);
assert.match(chips.join("|"), /Tryb uzbrojenia.*Wył/s);
const events = await panel.locator(".event").allTextContents();
assert.equal(events.length, 4);
assert.match(events[0], /Zamknięty.*na zamku/s);
assert.match(events[2], /Zamknięty.*automatyzacja/s);
assert.match(events[3], /Otwarty.*z Home Assistant/s);
const logbook = (await calls()).filter((c) => c[0] === "ws");
assert.deepEqual(logbook, [["ws", "logbook/get_events", ["lock.raykube_a1_ultra_d9f494_zamek"]]]);
if (shots) await page.screenshot({ path: path.join(shots, "2-panel.png"), fullPage: false });

// Unlock needs a second tap
const unlock = panel.locator('[data-act="unlock"]');
await unlock.click();
assert.equal(await unlock.locator("span").textContent(), "Potwierdź otwarcie");
assert.deepEqual(await calls(), []);
if (shots) await page.screenshot({ path: path.join(shots, "3-confirm-unlock.png") });
await unlock.click();
assert.deepEqual(await calls(), [["lock", "unlock", { entity_id: "lock.raykube_a1_ultra_d9f494_zamek" }]]);

// Settings
await panel.locator('[data-act="auto_lock"]').click();
await panel.locator('[data-act="mute"]').click();
await panel.locator('[data-act="arming"]').click();
await panel.locator('[data-act="refresh"]').click();
assert.deepEqual(await calls(), [
  ["switch", "turn_off", { entity_id: "switch.auto" }],
  ["switch", "turn_off", { entity_id: "switch.mute" }],
  ["input_boolean", "turn_on", { entity_id: "input_boolean.zamek_uzbrojony" }],
  ["button", "press", { entity_id: "button.refresh" }],
]);
await panel.locator('[data-act="auto_lock_time"]').fill("45");
await panel.locator('[data-act="auto_lock_time"]').press("Enter");
await panel.locator(".hero").click();
assert.deepEqual(await calls(), [["number", "set_value", { entity_id: "number.czas", value: 45 }]]);
const calibrate = panel.locator('[data-act="calibrate"]');
await calibrate.click();
assert.deepEqual(await calls(), []);
await calibrate.click();
assert.deepEqual(await calls(), [["button", "press", { entity_id: "button.calibrate" }]]);

// State update while open, from the lock itself
await page.evaluate(() => {
  const hass = window.makeHass();
  hass.states["lock.raykube_a1_ultra_d9f494_zamek"] = {
    ...hass.states["lock.raykube_a1_ultra_d9f494_zamek"], state: "unlocked",
    last_changed: new Date().toISOString(), context: { id: "c2", user_id: null, parent_id: null } };
  window.card.hass = hass;
});
assert.equal(await panel.locator(".hero .state").textContent(), "Otwarty");
assert.match(await panel.locator(".hero .when").textContent(), /przed chwilą · na zamku/);
assert.match(await page.locator("raykube-lock-card .secondary").textContent(), /^Otwarty · przed chwilą$/);
if (shots) await page.screenshot({ path: path.join(shots, "4-panel-unlocked.png") });

// Close with the X
await panel.locator('[data-act="close"]').click();
assert.equal(await page.locator("raykube-lock-panel").count(), 0);
if (shots) await page.locator("#host").screenshot({ path: path.join(shots, "5-tile-unlocked.png") });

// Bad config is rejected
const err = await page.evaluate(() => {
  try { document.createElement("raykube-lock-card").setConfig({ entity: "switch.x" }); return null; }
  catch (e) { return e.message; }
});
assert.match(err, /lock\./);

assert.deepEqual(errors, []);
await browser.close();
console.log("card tests passed");

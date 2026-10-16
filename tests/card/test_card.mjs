// Browser test of raykube-lock-card with a mocked hass object.
// Run: node tests/card/test_card.mjs [screenshot_dir]   (needs playwright + chromium)
import { chromium } from "playwright";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const shots = process.argv[2];
const LOCK = "lock.raykube_a1_ultra_d9f494_zamek";
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto("file://" + path.join(here, "harness.html"));

// Service calls only; logbook reloads (ws) on every state change are expected.
const calls = () => page.evaluate(() => window.calls.splice(0).filter((c) => c[0] !== "ws"));
const setLock = (state) => page.evaluate(([id, s]) => {
  const hass = window.makeHass();
  hass.states[id] = { ...hass.states[id], state: s, last_changed: new Date().toISOString(),
    context: { id: String(Math.random()), user_id: null, parent_id: null } };
  window.states = hass.states;
  window.card.hass = hass;
}, [LOCK, state]);
const tile = page.locator("raykube-lock-card ha-card");
const action = page.locator("raykube-lock-card .action");
const tapTile = async () => {
  const box = await tile.boundingBox();
  await page.mouse.click(box.x + 60, box.y + box.height / 2);
};

// Compact tile, locked: the action offers "Otwórz"
await tile.waitFor();
assert.equal(await page.locator("raykube-lock-card .name").textContent(), "Drzwi wejściowe");
assert.equal(await page.locator("raykube-lock-card .meta .state").textContent(), "Zamknięty");
assert.match(await page.locator("raykube-lock-card .meta").textContent(), /·15 min/);
assert.equal((await action.textContent()).trim(), "Otwórz");
if (shots) await page.locator("#host").screenshot({ path: path.join(shots, "1-tile-locked.png") });

// Battery icon on the tile only when low
assert.equal(await page.locator("raykube-lock-card .battery").isHidden(), true);
await page.evaluate(() => {
  const hass = window.makeHass();
  hass.states["sensor.bateria"] = { state: "low", attributes: {} };
  window.card.hass = hass;
});
assert.equal(await page.locator("raykube-lock-card .battery").isVisible(), true);
if (shots) await page.locator("#host").screenshot({ path: path.join(shots, "1b-tile-low-battery.png") });
await page.evaluate(() => {
  const hass = window.makeHass();
  hass.states["sensor.bateria"] = { state: "high", attributes: {} };
  window.card.hass = hass;
});

// Tap on a locked lock unlocks it, shows progress until the lock reports
await tapTile();
assert.deepEqual(await calls(), [["lock", "unlock", { entity_id: LOCK }]]);
assert.equal(await page.locator("raykube-lock-card .meta .state").textContent(), "Otwieranie…");
assert.equal(await action.isDisabled(), true);
if (shots) await page.locator("#host").screenshot({ path: path.join(shots, "2-tile-pending.png") });
await tapTile(); // ignored while pending
assert.deepEqual(await calls(), []);
await setLock("unlocked");
assert.equal(await page.locator("raykube-lock-card .meta .state").textContent(), "Otwarty");
assert.equal((await action.textContent()).trim(), "Zamknij");
await page.waitForTimeout(300);
if (shots) await page.locator("#host").screenshot({ path: path.join(shots, "3-tile-unlocked.png") });

// Tap on an unlocked lock locks it; tapping the action button works too
await action.click({ force: true });
assert.deepEqual(await calls(), [["lock", "lock", { entity_id: LOCK }]]);
await setLock("locked");

// Long press opens the panel (and the click right after does not close it)
const box = await tile.boundingBox();
await page.mouse.move(box.x + 60, box.y + box.height / 2);
await page.mouse.down();
await page.waitForTimeout(700);
await page.mouse.up();
await page.mouse.click(10, 10);
assert.deepEqual(await calls().then((c) => c.filter((x) => x[0] === "lock")), []);
const panel = page.locator("raykube-lock-panel");
await panel.waitFor();
await page.waitForTimeout(300);
assert.equal(await panel.locator(".status .state").textContent(), "Zamknięty");
assert.match(await panel.locator(".badge").textContent(), /na zamku · przed chwilą/);
const stats = await panel.locator(".stat").allTextContents();
assert.equal(stats.length, 3);
assert.match(stats.join("|"), /Bateria\s*Wysoki/);
assert.match(stats.join("|"), /Zamykanie\s*30 s/);
assert.match(stats.join("|"), /Uzbrojenie\s*Wył/);
const events = await panel.locator(".event").allTextContents();
assert.equal(events.length, 4);
assert.match(events[0], /Zamknięty\s*na zamku/);
assert.match(events[2], /Zamknięty\s*automatyzacja/);
assert.match(events[3], /Otwarty\s*z Home Assistant/);
if (shots) await page.screenshot({ path: path.join(shots, "4-panel.png") });

// Panel buttons: the next action is the primary one
assert.match(await panel.locator('[data-act="unlock"]').getAttribute("class"), /btn-default/);
assert.match(await panel.locator('[data-act="lock"]').getAttribute("class"), /btn-outline/);
await panel.locator('[data-act="unlock"]').click();
assert.deepEqual(await calls(), [["lock", "unlock", { entity_id: LOCK }]]);
assert.equal(await panel.locator(".status .state").textContent(), "Otwieranie…");
await setLock("unlocked");
assert.equal(await panel.locator(".status .state").textContent(), "Otwarty");
assert.match(await panel.locator('[data-act="lock"]').getAttribute("class"), /btn-default/);
await page.waitForTimeout(300); // button transitions
if (shots) await page.screenshot({ path: path.join(shots, "5-panel-unlocked.png") });

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
await panel.locator(".status").click();
assert.deepEqual(await calls(), [["number", "set_value", { entity_id: "number.czas", value: 45 }]]);
const calibrate = panel.locator('[data-act="calibrate"]');
await calibrate.click();
assert.deepEqual(await calls(), []);
assert.equal((await calibrate.textContent()).trim(), "Potwierdź");
await calibrate.click();
assert.deepEqual(await calls(), [["button", "press", { entity_id: "button.calibrate" }]]);

// Close with the X
await panel.locator('[data-act="close"]').click();
assert.equal(await page.locator("raykube-lock-panel").count(), 0);

// confirm_unlock: first tap arms, second tap unlocks
await setLock("locked");
await page.evaluate(() => {
  window.card.setConfig({ entity: "lock.raykube_a1_ultra_d9f494_zamek", name: "Drzwi wejściowe", confirm_unlock: true });
  window.card.hass = window.makeHass();
});
await setLock("locked");
await tapTile();
assert.deepEqual(await calls(), []);
assert.equal((await action.textContent()).trim(), "Potwierdź otwarcie");
if (shots) await page.locator("#host").screenshot({ path: path.join(shots, "6-tile-confirm.png") });
await tapTile();
assert.deepEqual(await calls(), [["lock", "unlock", { entity_id: LOCK }]]);

// After an HA restart nothing is known yet: tap locks (never unlocks), the
// panel says "unknown" instead of pretending the settings are off.
await setLock("unlocked"); // settles the unlock sent above
await page.evaluate((id) => {
  const hass = window.makeHass();
  for (const e of [id, "switch.auto", "number.czas", "switch.mute"]) {
    hass.states[e] = { ...hass.states[e], state: "unknown" };
  }
  window.card.hass = hass;
}, LOCK);
assert.equal(await page.locator("raykube-lock-card .meta .state").textContent(), "Stan nieznany");
assert.equal((await action.textContent()).trim(), "Zamknij");
await tapTile();
assert.deepEqual(await calls(), [["lock", "lock", { entity_id: LOCK }]]);
await page.locator("raykube-lock-card .more").click();
const unknownPanel = page.locator("raykube-lock-panel");
await unknownPanel.locator(".stats").waitFor();
assert.match((await unknownPanel.locator(".stat").allTextContents()).join("|"), /Zamykanie\s*Nieznany/);
assert.equal(await unknownPanel.locator('[data-act="auto_lock"]').getAttribute("aria-checked"), "mixed");
assert.equal(await unknownPanel.locator('[data-act="mute"]').getAttribute("aria-checked"), "mixed");
assert.equal(await unknownPanel.locator('[data-act="auto_lock_time"]').inputValue(), "");
assert.match(await unknownPanel.locator(".row.hint").textContent(), /Naciśnij Odśwież/);
await page.waitForTimeout(300);
if (shots) await page.screenshot({ path: path.join(shots, "7-panel-unknown.png") });
await unknownPanel.locator('[data-act="close"]').click();

// Bad config is rejected
const err = await page.evaluate(() => {
  try { document.createElement("raykube-lock-card").setConfig({ entity: "switch.x" }); return null; }
  catch (e) { return e.message; }
});
assert.match(err, /lock\./);

assert.deepEqual(errors, []);
await browser.close();
console.log("card tests passed");

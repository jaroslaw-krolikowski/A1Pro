/*
 * Raykube Lock card, shipped with the tuya_local_ble integration.
 *
 * Tile: tap locks the door, long press (or the chevron) opens a panel with
 * lock/unlock (unlock needs a second tap to confirm), battery, last change
 * and its source, settings, calibration and recent history.
 *
 *   type: custom:raykube-lock-card
 *   entity: lock.raykube_a1_ultra_d9f494_zamek
 *   name: Drzwi wejściowe        # optional
 *   arming_entity: input_boolean.zamek_uzbrojony   # optional
 *
 * Related entities of the same device are found by translation key; any of
 * them can be overridden with battery_entity, auto_lock_entity,
 * auto_lock_time_entity, mute_entity, refresh_entity, calibrate_entity,
 * signal_entity.
 */

const CARD_VERSION = "1.0.0";
const HOLD_MS = 500;
const CONFIRM_MS = 4000;

const STRINGS = {
  pl: {
    locked: "Zamknięty",
    unlocked: "Otwarty",
    locking: "Zamykanie…",
    unlocking: "Otwieranie…",
    jammed: "Zablokowany mechanizm",
    open: "Otwarty",
    opening: "Otwieranie…",
    unavailable: "Niedostępny",
    unknown: "Stan nieznany",
    lock: "Zamknij",
    unlock: "Otwórz",
    confirm_unlock: "Potwierdź otwarcie",
    tap_hint: "Dotknij, aby zamknąć · przytrzymaj, aby zobaczyć więcej",
    battery: "Bateria",
    battery_high: "Wysoki",
    battery_normal: "Średni",
    battery_medium: "Średni",
    battery_low: "Niski",
    battery_poweroff: "Wyczerpana",
    signal: "Sygnał",
    auto_lock: "Automatyczne zamykanie",
    auto_lock_after: "Zamknij po",
    seconds: "s",
    mute: "Wyciszenie",
    arming: "Tryb uzbrojenia",
    refresh: "Stan zamka",
    refresh_action: "Odśwież",
    calibrate: "Kalibracja",
    calibrate_action: "Uruchom",
    auto_lock_short: "Auto-zamykanie",
    confirm_calibrate: "Potwierdź",
    settings: "Ustawienia",
    history: "Ostatnie zdarzenia",
    no_history: "Brak zdarzeń z ostatnich 48 h",
    source_ha: "z Home Assistant",
    source_automation: "automatyzacja",
    source_device: "na zamku",
    changed: "Zmiana",
    on: "Wł.",
    off: "Wył.",
    close: "Zamknij panel",
    more: "Więcej",
    just_now: "przed chwilą",
  },
  en: {
    locked: "Locked",
    unlocked: "Unlocked",
    locking: "Locking…",
    unlocking: "Unlocking…",
    jammed: "Jammed",
    open: "Open",
    opening: "Opening…",
    unavailable: "Unavailable",
    unknown: "Unknown",
    lock: "Lock",
    unlock: "Unlock",
    confirm_unlock: "Confirm unlock",
    tap_hint: "Tap to lock · hold for more",
    battery: "Battery",
    battery_high: "High",
    battery_normal: "Medium",
    battery_medium: "Medium",
    battery_low: "Low",
    battery_poweroff: "Empty",
    signal: "Signal",
    auto_lock: "Auto lock",
    auto_lock_after: "Lock after",
    seconds: "s",
    mute: "Mute",
    arming: "Arming mode",
    refresh: "Lock status",
    refresh_action: "Refresh",
    calibrate: "Calibration",
    calibrate_action: "Start",
    auto_lock_short: "Auto lock",
    confirm_calibrate: "Confirm",
    settings: "Settings",
    history: "Recent events",
    no_history: "No events in the last 48 h",
    source_ha: "from Home Assistant",
    source_automation: "automation",
    source_device: "at the lock",
    changed: "Changed",
    on: "On",
    off: "Off",
    close: "Close panel",
    more: "More",
    just_now: "just now",
  },
};

// Translation keys of the integration's entities (entity description keys).
const RELATED_KEYS = {
  battery: "battery_state",
  auto_lock: "automatic_lock",
  auto_lock_time: "auto_lock_time",
  mute: "mute",
  refresh: "refresh_status",
  calibrate: "calibrate",
  signal: "signal_strength",
};

const ICONS = {
  lock: "mdi:lock",
  unlock: "mdi:lock-open-variant",
  jammed: "mdi:lock-alert",
  pending: "mdi:lock-clock",
  unknown: "mdi:lock-question",
  battery_high: "mdi:battery",
  battery_normal: "mdi:battery-50",
  battery_medium: "mdi:battery-50",
  battery_low: "mdi:battery-alert",
  battery_poweroff: "mdi:battery-off-outline",
};

function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

function strings(hass) {
  const lang = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return STRINGS[lang] || STRINGS.en;
}

function relativeTime(hass, iso) {
  if (!iso) return "";
  const seconds = Math.round((Date.parse(iso) - Date.now()) / 1000);
  if (Math.abs(seconds) < 45) return strings(hass).just_now;
  const lang = (hass?.locale?.language || "en").split("-")[0];
  const units = [
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size || unit === "minute") {
      return rtf.format(Math.round(seconds / size), unit);
    }
  }
  return "";
}

function clockTime(hass, when) {
  const lang = hass?.locale?.language || "en";
  const date = new Date(when);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return date.toLocaleString(lang, sameDay
    ? { hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Where a change came from, from a state context or a logbook entry. */
function changeSource(t, userId, parentId, eventType, domain) {
  if (eventType === "automation_triggered" || domain === "automation" || domain === "script") {
    return t.source_automation;
  }
  if (userId) return t.source_ha;
  if (parentId) return t.source_automation;
  return t.source_device;
}

function lockVisual(state) {
  switch (state) {
    case "locked":
      return { icon: ICONS.lock, tone: "locked" };
    case "unlocked":
    case "open":
      return { icon: ICONS.unlock, tone: "unlocked" };
    case "locking":
    case "unlocking":
    case "opening":
      return { icon: ICONS.pending, tone: "pending" };
    case "jammed":
      return { icon: ICONS.jammed, tone: "alert" };
    default:
      return { icon: ICONS.unknown, tone: "unknown" };
  }
}

const SHARED_STYLE = `
  :host {
    --rk-locked: var(--state-lock-locked-color, var(--success-color, #43a047));
    --rk-unlocked: var(--state-lock-unlocked-color, var(--error-color, #db4437));
    --rk-pending: var(--state-lock-pending-color, var(--warning-color, #ffa600));
    --rk-alert: var(--state-lock-jammed-color, var(--error-color, #db4437));
    --rk-unknown: var(--state-unavailable-color, var(--disabled-text-color, #9e9e9e));
  }
  .tone-locked { --rk-tone: var(--rk-locked); }
  .tone-unlocked { --rk-tone: var(--rk-unlocked); }
  .tone-pending { --rk-tone: var(--rk-pending); }
  .tone-alert { --rk-tone: var(--rk-alert); }
  .tone-unknown { --rk-tone: var(--rk-unknown); }
  .badge {
    display: flex; align-items: center; justify-content: center;
    width: 44px; height: 44px; flex: none; border-radius: 50%;
    color: var(--rk-tone);
    background: color-mix(in srgb, var(--rk-tone) 20%, transparent);
  }
  .badge ha-icon { --mdc-icon-size: 24px; }
  .pending ha-icon { animation: rk-pulse 1s ease-in-out infinite; }
  @keyframes rk-pulse { 50% { opacity: .35; } }
  button { font: inherit; color: inherit; }
`;

class RaykubeLockCard extends HTMLElement {
  static getStubConfig(hass) {
    const lock = Object.values(hass.entities || {}).find(
      (e) => e.platform === "tuya_local_ble" && e.entity_id.startsWith("lock.")
    );
    return { entity: lock ? lock.entity_id : "" };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { domain: "lock" } } },
        { name: "name", selector: { text: {} } },
        { name: "arming_entity", selector: { entity: { domain: "input_boolean" } } },
      ],
    };
  }

  setConfig(config) {
    if (!config || !config.entity || !String(config.entity).startsWith("lock.")) {
      throw new Error("Podaj encję zamka: entity: lock.…");
    }
    this._config = { ...config };
    this._rendered = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    this._render();
    if (this._panel) this._panel.update(hass, this._related(), this._config);
  }

  get hass() {
    return this._hass;
  }

  getCardSize() {
    return 1;
  }

  getGridOptions() {
    return { columns: 12, rows: 1, min_rows: 1 };
  }

  connectedCallback() {
    if (this._hass && this._config) this._render();
  }

  disconnectedCallback() {
    this._closePanel();
  }

  /** Entity ids of the lock's device, by role. */
  _related() {
    const config = this._config;
    const registry = this._hass?.entities || {};
    const deviceId = registry[config.entity]?.device_id;
    const byKey = {};
    if (deviceId) {
      for (const entry of Object.values(registry)) {
        if (entry.device_id === deviceId && entry.translation_key) {
          byKey[entry.translation_key] = entry.entity_id;
        }
      }
    }
    const related = { lock: config.entity, arming: config.arming_entity };
    for (const [role, key] of Object.entries(RELATED_KEYS)) {
      related[role] = config[`${role}_entity`] || byKey[key];
    }
    return related;
  }

  _render() {
    const hass = this._hass;
    const t = strings(hass);
    const stateObj = hass.states[this._config.entity];
    if (!this._rendered) {
      this._rendered = true;
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `
        <style>
          ${SHARED_STYLE}
          ha-card {
            display: flex; align-items: center; gap: 12px;
            padding: 6px 8px 6px 10px; cursor: pointer;
            user-select: none; -webkit-user-select: none;
            -webkit-touch-callout: none; touch-action: manipulation;
            transition: transform .12s ease;
          }
          ha-card.pressed { transform: scale(.98); }
          .text { flex: 1; min-width: 0; }
          .name {
            font-weight: 500; font-size: 15px; line-height: 20px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          }
          .secondary {
            font-size: 13px; line-height: 18px; color: var(--secondary-text-color);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          }
          .battery { display: flex; align-items: center; color: var(--secondary-text-color); }
          .battery ha-icon { --mdc-icon-size: 20px; }
          .battery.low { color: var(--rk-alert); }
          .more {
            display: flex; align-items: center; justify-content: center;
            width: 40px; height: 40px; border: none; border-radius: 50%;
            background: none; cursor: pointer; color: var(--secondary-text-color);
          }
          .more:hover { background: var(--secondary-background-color); }
        </style>
        <ha-card tabindex="0" role="button">
          <div class="badge"><ha-icon></ha-icon></div>
          <div class="text">
            <div class="name"></div>
            <div class="secondary"></div>
          </div>
          <div class="battery"><ha-icon></ha-icon></div>
          <button class="more"><ha-icon icon="mdi:chevron-up"></ha-icon></button>
        </ha-card>`;
      this._bindGestures();
    }

    const root = this.shadowRoot;
    const card = root.querySelector("ha-card");
    const name = this._config.name || stateObj?.attributes?.friendly_name || this._config.entity;
    const state = stateObj ? stateObj.state : "unavailable";
    const visual = lockVisual(state);
    card.className = `tone-${visual.tone}`;
    card.setAttribute("aria-label", `${name}: ${t[state] || state}. ${t.tap_hint}`);
    const badge = root.querySelector(".badge");
    badge.classList.toggle("pending", visual.tone === "pending");
    badge.querySelector("ha-icon").setAttribute("icon", visual.icon);
    root.querySelector(".name").textContent = name;
    const when = stateObj ? relativeTime(hass, stateObj.last_changed) : "";
    root.querySelector(".secondary").textContent = [t[state] || state, when].filter(Boolean).join(" · ");
    root.querySelector(".more").setAttribute("aria-label", t.more);
    root.querySelector(".more").title = t.more;

    const batteryId = this._related().battery;
    const battery = batteryId ? hass.states[batteryId] : undefined;
    const batteryEl = root.querySelector(".battery");
    if (battery && ICONS[`battery_${battery.state}`]) {
      batteryEl.hidden = false;
      batteryEl.classList.toggle("low", battery.state === "low" || battery.state === "poweroff");
      batteryEl.title = `${t.battery}: ${t[`battery_${battery.state}`] || battery.state}`;
      batteryEl.querySelector("ha-icon").setAttribute("icon", ICONS[`battery_${battery.state}`]);
    } else {
      batteryEl.hidden = true;
    }
  }

  _bindGestures() {
    const card = this.shadowRoot.querySelector("ha-card");
    const more = this.shadowRoot.querySelector(".more");
    let timer = null;
    let held = false;
    let start = null;

    const cancel = () => {
      clearTimeout(timer);
      timer = null;
      card.classList.remove("pressed");
    };

    card.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0 || ev.composedPath().includes(more)) return;
      held = false;
      start = { x: ev.clientX, y: ev.clientY };
      card.classList.add("pressed");
      timer = setTimeout(() => {
        held = true;
        card.classList.remove("pressed");
        this._haptic("medium");
        this._openPanel();
      }, HOLD_MS);
    });
    card.addEventListener("pointermove", (ev) => {
      if (start && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > 10) {
        cancel();
        start = null;
      }
    });
    card.addEventListener("pointerup", (ev) => {
      if (!start || ev.composedPath().includes(more)) return;
      const wasHeld = held;
      cancel();
      start = null;
      if (!wasHeld) this._tapLock();
    });
    card.addEventListener("pointercancel", () => {
      cancel();
      start = null;
    });
    card.addEventListener("contextmenu", (ev) => ev.preventDefault());
    card.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        this._tapLock();
      }
    });
    more.addEventListener("click", (ev) => {
      ev.stopPropagation();
      this._openPanel();
    });
  }

  _tapLock() {
    this._haptic("light");
    this._hass.callService("lock", "lock", { entity_id: this._config.entity });
  }

  _haptic(type) {
    this.dispatchEvent(new CustomEvent("haptic", { detail: type, bubbles: true, composed: true }));
  }

  _openPanel() {
    if (this._panel) return;
    this._panel = document.createElement("raykube-lock-panel");
    this._panel.addEventListener("raykube-close", () => this._closePanel());
    document.body.appendChild(this._panel);
    this._panel.update(this._hass, this._related(), this._config);
  }

  _closePanel() {
    if (!this._panel) return;
    this._panel.remove();
    this._panel = null;
  }
}

class RaykubeLockPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._confirm = {};
    this._history = null;
    this._historyFor = null;
    this._onKey = (ev) => {
      if (ev.key === "Escape") this._close();
    };
  }

  connectedCallback() {
    this._openedAt = Date.now();
    document.addEventListener("keydown", this._onKey);
  }

  disconnectedCallback() {
    document.removeEventListener("keydown", this._onKey);
    Object.values(this._confirm).forEach(clearTimeout);
  }

  update(hass, related, config) {
    this._hass = hass;
    this._related = related;
    this._config = config;
    if (!this._built) this._build();
    this._refresh();
    const lock = hass.states[related.lock];
    const key = lock ? lock.last_changed : null;
    if (key !== this._historyFor) {
      this._historyFor = key;
      this._loadHistory();
    }
  }

  _close() {
    this.dispatchEvent(new CustomEvent("raykube-close"));
  }

  _build() {
    this._built = true;
    const t = strings(this._hass);
    this.shadowRoot.innerHTML = `
      <style>
        ${SHARED_STYLE}
        :host {
          position: fixed; inset: 0; z-index: 1000;
          display: flex; align-items: flex-end; justify-content: center;
          font-family: var(--paper-font-body1_-_font-family, var(--ha-font-family-body, Roboto, sans-serif));
          color: var(--primary-text-color);
        }
        .backdrop {
          position: absolute; inset: 0; background: rgba(0, 0, 0, .55);
          animation: rk-fade .18s ease-out;
        }
        .sheet {
          position: relative; width: 100%; max-width: 480px; max-height: 92vh;
          overflow-y: auto; box-sizing: border-box;
          padding: 8px 16px calc(20px + env(safe-area-inset-bottom));
          background: var(--ha-card-background, var(--card-background-color, #1c1c1c));
          border-radius: 24px 24px 0 0;
          animation: rk-slide .22s ease-out;
        }
        @media (min-width: 600px) {
          :host { align-items: center; }
          .sheet { border-radius: 24px; }
        }
        @keyframes rk-fade { from { opacity: 0; } }
        @keyframes rk-slide { from { transform: translateY(40px); opacity: 0; } }
        .grab {
          width: 40px; height: 4px; margin: 4px auto 8px; border-radius: 2px;
          background: var(--divider-color, rgba(255,255,255,.2));
        }
        .top { display: flex; align-items: center; gap: 12px; }
        .top .title { flex: 1; min-width: 0; }
        .title .name { font-size: 18px; font-weight: 500; }
        .title .sub { font-size: 13px; color: var(--secondary-text-color); }
        .icon-btn {
          display: flex; align-items: center; justify-content: center;
          width: 40px; height: 40px; border: none; border-radius: 50%;
          background: none; cursor: pointer; color: var(--secondary-text-color);
        }
        .hero { text-align: center; padding: 16px 0 8px; }
        .hero .badge { width: 88px; height: 88px; margin: 0 auto 10px; }
        .hero .badge ha-icon { --mdc-icon-size: 44px; }
        .hero .state { font-size: 26px; font-weight: 500; }
        .hero .when { font-size: 14px; color: var(--secondary-text-color); margin-top: 2px; }
        .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 16px 0; }
        .action {
          display: flex; align-items: center; justify-content: center; gap: 8px;
          min-height: 56px; border-radius: 16px; border: none; cursor: pointer;
          font-size: 16px; font-weight: 500;
          background: var(--secondary-background-color, rgba(255,255,255,.06));
        }
        .action.lock { color: var(--rk-locked); }
        .action.unlock { color: var(--rk-unlocked); }
        .action.armed {
          color: var(--text-primary-color, #fff); background: var(--rk-unlocked);
        }
        .action:disabled { opacity: .4; cursor: default; }
        .chips { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 8px; }
        .chip {
          padding: 10px 12px; border-radius: 14px;
          background: var(--secondary-background-color, rgba(255,255,255,.06));
        }
        .chip .label { font-size: 12px; color: var(--secondary-text-color); }
        .chip .value { display: flex; align-items: center; gap: 4px; font-size: 15px; font-weight: 500; margin-top: 2px; }
        .chip ha-icon { --mdc-icon-size: 18px; }
        h3 {
          margin: 20px 4px 6px; font-size: 13px; font-weight: 500; letter-spacing: .4px;
          text-transform: uppercase; color: var(--secondary-text-color);
        }
        .rows { border-radius: 16px; overflow: hidden; background: var(--secondary-background-color, rgba(255,255,255,.06)); }
        .row {
          display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 0 14px;
          border-bottom: 1px solid var(--divider-color, rgba(255,255,255,.08));
        }
        .row:last-child { border-bottom: none; }
        .row .label { flex: 1; }
        .row ha-icon { color: var(--secondary-text-color); }
        .row button.link {
          border: none; background: none; cursor: pointer; padding: 8px 0;
          color: var(--primary-color); font-weight: 500;
        }
        .row button.link.armed { color: var(--rk-unlocked); }
        .row input[type=number] {
          width: 72px; padding: 6px 8px; border-radius: 8px; text-align: right;
          border: 1px solid var(--divider-color, rgba(255,255,255,.2));
          background: transparent; color: inherit; font: inherit;
        }
        .switch {
          position: relative; width: 44px; height: 26px; flex: none; border-radius: 13px;
          border: none; cursor: pointer; background: var(--disabled-text-color, #666); transition: background .15s;
        }
        .switch::after {
          content: ""; position: absolute; top: 3px; left: 3px; width: 20px; height: 20px;
          border-radius: 50%; background: #fff; transition: transform .15s;
        }
        .switch[aria-checked=true] { background: var(--primary-color); }
        .switch[aria-checked=true]::after { transform: translateX(18px); }
        .event { display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 0 14px;
          border-bottom: 1px solid var(--divider-color, rgba(255,255,255,.08)); }
        .event:last-child { border-bottom: none; }
        .event .what { flex: 1; }
        .event .src { font-size: 12px; color: var(--secondary-text-color); }
        .event .time { font-size: 13px; color: var(--secondary-text-color); }
        .empty { padding: 14px; color: var(--secondary-text-color); font-size: 14px; }
      </style>
      <div class="backdrop"></div>
      <div class="sheet" role="dialog" aria-modal="true">
        <div class="grab"></div>
        <div class="top">
          <div class="title"><div class="name"></div><div class="sub"></div></div>
          <button class="icon-btn" data-act="close" aria-label="${esc(t.close)}" title="${esc(t.close)}">
            <ha-icon icon="mdi:close"></ha-icon></button>
        </div>
        <div class="hero">
          <div class="badge"><ha-icon></ha-icon></div>
          <div class="state"></div>
          <div class="when"></div>
        </div>
        <div class="actions">
          <button class="action lock" data-act="lock"><ha-icon icon="${ICONS.lock}"></ha-icon><span>${esc(t.lock)}</span></button>
          <button class="action unlock" data-act="unlock"><ha-icon icon="${ICONS.unlock}"></ha-icon><span>${esc(t.unlock)}</span></button>
        </div>
        <div class="chips"></div>
        <h3>${esc(t.settings)}</h3>
        <div class="rows settings"></div>
        <h3>${esc(t.history)}</h3>
        <div class="rows history"><div class="empty">…</div></div>
      </div>`;

    const root = this.shadowRoot;
    root.querySelector(".backdrop").addEventListener("click", () => {
      // The click that follows the long press lands on the backdrop.
      if (Date.now() - this._openedAt > 400) this._close();
    });
    root.addEventListener("click", (ev) => {
      const el = ev.composedPath().find((n) => n.dataset && n.dataset.act);
      if (el) this._act(el.dataset.act, el);
    });
    root.addEventListener("change", (ev) => {
      const el = ev.composedPath()[0];
      if (el.dataset && el.dataset.act === "auto_lock_time") {
        const value = Number(el.value);
        if (!Number.isNaN(value)) {
          this._call("number", "set_value", this._related.auto_lock_time, { value });
        }
      }
    });
  }

  _call(domain, service, entityId, data = {}) {
    if (!entityId) return;
    this._hass.callService(domain, service, { entity_id: entityId, ...data });
  }

  /** Second tap within CONFIRM_MS confirms a risky action. */
  _confirmed(key, render) {
    if (this._confirm[key]) {
      clearTimeout(this._confirm[key]);
      delete this._confirm[key];
      render();
      return true;
    }
    this._confirm[key] = setTimeout(() => {
      delete this._confirm[key];
      render();
    }, CONFIRM_MS);
    render();
    return false;
  }

  _act(action) {
    const r = this._related;
    const s = this._hass.states;
    switch (action) {
      case "close":
        this._close();
        break;
      case "lock":
        this._haptic("light");
        this._call("lock", "lock", r.lock);
        break;
      case "unlock":
        if (this._confirmed("unlock", () => this._refresh())) {
          this._haptic("success");
          this._call("lock", "unlock", r.lock);
        }
        break;
      case "auto_lock":
        this._call("switch", s[r.auto_lock]?.state === "on" ? "turn_off" : "turn_on", r.auto_lock);
        break;
      case "mute":
        this._call("switch", s[r.mute]?.state === "on" ? "turn_off" : "turn_on", r.mute);
        break;
      case "arming":
        this._call("input_boolean", s[r.arming]?.state === "on" ? "turn_off" : "turn_on", r.arming);
        break;
      case "refresh":
        this._call("button", "press", r.refresh);
        break;
      case "calibrate":
        if (this._confirmed("calibrate", () => this._refresh())) {
          this._call("button", "press", r.calibrate);
        }
        break;
      default:
        break;
    }
  }

  _haptic(type) {
    this.dispatchEvent(new CustomEvent("haptic", { detail: type, bubbles: true, composed: true }));
  }

  _refresh() {
    const hass = this._hass;
    const t = strings(hass);
    const r = this._related;
    const root = this.shadowRoot;
    const lock = hass.states[r.lock];
    const state = lock ? lock.state : "unavailable";
    const visual = lockVisual(state);
    const name = this._config.name || lock?.attributes?.friendly_name || r.lock;

    root.querySelector(".sheet").className = `sheet tone-${visual.tone}`;
    root.querySelector(".top .name").textContent = name;
    root.querySelector(".top .sub").textContent = lock?.attributes?.friendly_name !== name
      ? lock?.attributes?.friendly_name || "" : "";
    const badge = root.querySelector(".hero .badge");
    badge.classList.toggle("pending", visual.tone === "pending");
    badge.querySelector("ha-icon").setAttribute("icon", visual.icon);
    root.querySelector(".hero .state").textContent = t[state] || state;
    if (lock) {
      const ctx = lock.context || {};
      const source = changeSource(t, ctx.user_id, ctx.parent_id);
      root.querySelector(".hero .when").textContent =
        `${t.changed}: ${relativeTime(hass, lock.last_changed)} · ${source}`;
    } else {
      root.querySelector(".hero .when").textContent = "";
    }

    const unavailable = !lock || state === "unavailable";
    const lockBtn = root.querySelector('[data-act="lock"]');
    const unlockBtn = root.querySelector('[data-act="unlock"]');
    lockBtn.disabled = unavailable;
    unlockBtn.disabled = unavailable;
    const confirming = Boolean(this._confirm.unlock);
    unlockBtn.classList.toggle("armed", confirming);
    unlockBtn.querySelector("span").textContent = confirming ? t.confirm_unlock : t.unlock;

    // Status chips
    const chips = [];
    const battery = r.battery && hass.states[r.battery];
    if (battery) {
      chips.push([t.battery, ICONS[`battery_${battery.state}`] || "mdi:battery-unknown",
        t[`battery_${battery.state}`] || battery.state]);
    }
    const autoLock = r.auto_lock && hass.states[r.auto_lock];
    const autoTime = r.auto_lock_time && hass.states[r.auto_lock_time];
    if (autoLock) {
      const value = autoLock.state === "on"
        ? (autoTime ? `${autoTime.state} ${t.seconds}` : t.on) : t.off;
      chips.push([t.auto_lock_short, "mdi:lock-clock", value]);
    }
    const signal = r.signal && hass.states[r.signal];
    if (signal && !Number.isNaN(Number(signal.state))) {
      chips.push([t.signal, "mdi:bluetooth", `${signal.state} dBm`]);
    }
    const arming = r.arming && hass.states[r.arming];
    if (arming) {
      chips.push([t.arming, arming.state === "on" ? "mdi:shield-lock" : "mdi:shield-off-outline",
        arming.state === "on" ? t.on : t.off]);
    }
    root.querySelector(".chips").innerHTML = chips.map(([label, icon, value]) => `
      <div class="chip"><div class="label">${esc(label)}</div>
      <div class="value"><ha-icon icon="${esc(icon)}"></ha-icon>${esc(value)}</div></div>`).join("");

    // Settings
    const rows = [];
    const toggle = (act, icon, label, entity) => {
      if (!entity) return;
      const on = entity.state === "on";
      rows.push(`<div class="row"><ha-icon icon="${icon}"></ha-icon><span class="label">${esc(label)}</span>
        <button class="switch" role="switch" aria-checked="${on}" aria-label="${esc(label)}" data-act="${act}"></button></div>`);
    };
    toggle("arming", "mdi:shield-lock", t.arming, arming);
    toggle("auto_lock", "mdi:lock-clock", t.auto_lock, autoLock);
    if (autoTime) {
      const a = autoTime.attributes || {};
      const focused = this.shadowRoot.activeElement?.dataset?.act === "auto_lock_time";
      const existing = root.querySelector('[data-act="auto_lock_time"]');
      const value = focused && existing ? existing.value : autoTime.state;
      rows.push(`<div class="row"><ha-icon icon="mdi:timer-lock"></ha-icon><span class="label">${esc(t.auto_lock_after)}</span>
        <input type="number" inputmode="numeric" data-act="auto_lock_time" min="${esc(a.min ?? 1)}" max="${esc(a.max ?? 1800)}"
          step="${esc(a.step ?? 1)}" value="${esc(value)}"> ${esc(t.seconds)}</div>`);
    }
    toggle("mute", "mdi:volume-off", t.mute, r.mute && hass.states[r.mute]);
    if (r.refresh) {
      rows.push(`<div class="row"><ha-icon icon="mdi:refresh"></ha-icon><span class="label">${esc(t.refresh)}</span>
        <button class="link" data-act="refresh">${esc(t.refresh_action)}</button></div>`);
    }
    if (r.calibrate) {
      const armed = Boolean(this._confirm.calibrate);
      rows.push(`<div class="row"><ha-icon icon="mdi:tune-vertical"></ha-icon><span class="label">${esc(t.calibrate)}</span>
        <button class="link ${armed ? "armed" : ""}" data-act="calibrate">${esc(armed ? t.confirm_calibrate : t.calibrate_action)}</button></div>`);
    }
    const settings = root.querySelector(".settings");
    const html = rows.join("");
    if (settings._html !== html) {
      const focused = this.shadowRoot.activeElement?.dataset?.act === "auto_lock_time";
      if (!focused) {
        settings.innerHTML = html;
        settings._html = html;
      }
    }
    settings.hidden = rows.length === 0;
    settings.previousElementSibling.hidden = rows.length === 0;

    this._renderHistory();
  }

  async _loadHistory() {
    const hass = this._hass;
    const lockId = this._related.lock;
    if (!hass.callWS) return;
    const end = new Date();
    const start = new Date(end.getTime() - 48 * 3600 * 1000);
    try {
      const events = await hass.callWS({
        type: "logbook/get_events",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: [lockId],
      });
      this._history = (events || []).filter((e) => e.state).slice(-12).reverse();
    } catch (err) {
      this._history = [];
    }
    this._renderHistory();
  }

  _renderHistory() {
    const t = strings(this._hass);
    const box = this.shadowRoot.querySelector(".history");
    if (this._history === null) return;
    if (!this._history.length) {
      box.innerHTML = `<div class="empty">${esc(t.no_history)}</div>`;
      return;
    }
    box.innerHTML = this._history.map((e) => {
      const visual = lockVisual(e.state);
      const source = changeSource(t, e.context_user_id, null, e.context_event_type, e.context_domain);
      return `<div class="event tone-${visual.tone}">
        <div class="badge" style="width:32px;height:32px"><ha-icon icon="${visual.icon}" style="--mdc-icon-size:18px"></ha-icon></div>
        <div class="what"><div>${esc(t[e.state] || e.state)}</div><div class="src">${esc(source)}</div></div>
        <div class="time">${esc(clockTime(this._hass, e.when * 1000))}</div></div>`;
    }).join("");
  }
}

if (!customElements.get("raykube-lock-panel")) {
  customElements.define("raykube-lock-panel", RaykubeLockPanel);
}
if (!customElements.get("raykube-lock-card")) {
  customElements.define("raykube-lock-card", RaykubeLockCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "raykube-lock-card",
    name: "Raykube Lock",
    description: "Dotknij, aby zamknąć; przytrzymaj, aby zobaczyć szczegóły i ustawienia zamka.",
    preview: true,
    documentationURL: "https://github.com/jaroslaw-krolikowski/A1Pro/blob/master/docs/raykube-a1-pro.md",
  });
  console.info(`%c RAYKUBE-LOCK-CARD %c ${CARD_VERSION} `,
    "color:#fff;background:#43a047;font-weight:700", "color:#43a047");
}

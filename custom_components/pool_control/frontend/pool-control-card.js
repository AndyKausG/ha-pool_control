/*
 * Pool Control card for Home Assistant.
 *
 * Shows a schematic of the pool equipment with live states, the validated
 * readings with their set points, daily progress, problems and the most
 * important actions. Entities are discovered from the Pool Control device.
 */

const DOMAIN = "pool_control";
const VERSION = "1.0.0";

const STRINGS = {
  en: {
    pump: "Filter pump",
    chlorinator: "Chlorinator",
    ph_pump: "pH minus",
    solar: "Solar",
    set_point: "Set point",
    runtime: "Filtration today",
    tank: "pH minus tank",
    dosed: "Dosed today",
    problems: "Problems",
    maintenance: "Maintenance due",
    no_device: "No Pool Control device found.",
    boost: "Extra circulation",
    shock: "Shock",
    refilled: "Tank refilled",
    pulse: "pH pulse",
    confirm_refilled: "Mark the pH minus tank as refilled?",
    confirm_pulse: "Start a manual pH dosing pulse?",
    device: "Device",
    title: "Title",
    dry_run: "Dry run",
    codes: {
      no_flow: "No flow", sensor_stuck: "Sensor stuck", sensor_deviation: "Sensors disagree",
      water_quality: "Water quality", ph_too_low: "pH too low", ph_dosing_locked: "pH dosing locked",
      ph_daily_limit: "pH daily limit", ph_tank_low: "pH tank low", ph_tank_empty: "pH tank empty",
      chlorinator_no_effect: "Chlorinator without effect",
      chlorinator_daily_limit: "Chlorinator daily limit", salt_low: "Salt low", salt_high: "Salt high",
      outdoor_temperature_unavailable: "No outdoor temperature",
      ph_calibration: "pH calibration", orp_calibration: "ORP calibration",
      backwash: "Backwash", cell_cleaning: "Cell cleaning",
    },
  },
  de: {
    pump: "Filterpumpe",
    chlorinator: "Chlorgenerator",
    ph_pump: "pH-Minus",
    solar: "Solar",
    set_point: "Soll",
    runtime: "Filterung heute",
    tank: "pH-Minus-Kanister",
    dosed: "Heute dosiert",
    problems: "Probleme",
    maintenance: "Wartung fällig",
    no_device: "Kein Pool-Control-Gerät gefunden.",
    boost: "Nachumwälzen",
    shock: "Schock",
    refilled: "Kanister befüllt",
    pulse: "pH-Puls",
    confirm_refilled: "pH-Minus-Kanister als befüllt markieren?",
    confirm_pulse: "Manuellen pH-Dosierpuls starten?",
    device: "Gerät",
    title: "Titel",
    dry_run: "Simulation",
    codes: {
      no_flow: "Kein Durchfluss", sensor_stuck: "Sensor hängt", sensor_deviation: "Sonden weichen ab",
      water_quality: "Wasserqualität", ph_too_low: "pH zu niedrig",
      ph_dosing_locked: "pH-Dosierung gesperrt", ph_daily_limit: "pH-Tageslimit",
      ph_tank_low: "Kanister fast leer", ph_tank_empty: "Kanister leer",
      chlorinator_no_effect: "Chlorgenerator ohne Wirkung",
      chlorinator_daily_limit: "Chlor-Tageslimit", salt_low: "Salz zu niedrig",
      salt_high: "Salz zu hoch", outdoor_temperature_unavailable: "Keine Außentemperatur",
      ph_calibration: "pH-Kalibrierung", orp_calibration: "Redox-Kalibrierung",
      backwash: "Rückspülung", cell_cleaning: "Zellenreinigung",
    },
  },
};

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; }
  .header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
  .title { font-size: 20px; font-weight: 500; flex: 1; min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip { border-radius: 16px; padding: 4px 12px; font-size: 13px;
    background: var(--secondary-background-color); white-space: nowrap; cursor: pointer; }
  .chip.warn { background: var(--warning-color); color: #fff; }
  select { font: inherit; padding: 4px 8px; border-radius: 8px;
    border: 1px solid var(--divider-color); background: var(--card-background-color);
    color: var(--primary-text-color); }
  svg { width: 100%; height: auto; display: block; }
  .pipe { fill: none; stroke: var(--disabled-color, #bdbdbd); stroke-width: 6;
    stroke-linecap: round; }
  .pipe.on { stroke: #29a8f0; stroke-dasharray: 10 8; animation: flow 1s linear infinite; }
  @keyframes flow { to { stroke-dashoffset: -18; } }
  .device { fill: var(--card-background-color, #fff); stroke: var(--disabled-color, #bdbdbd);
    stroke-width: 2; cursor: pointer; }
  .device.on { stroke: #0b5cad; stroke-width: 2.5; }
  .label { font-size: 11px; fill: var(--secondary-text-color); text-anchor: middle; }
  .pool-temp { font-size: 22px; font-weight: 600; fill: #fff; text-anchor: middle; cursor: pointer; }
  .values { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
    gap: 8px; margin: 12px 0; }
  .value { background: var(--secondary-background-color); border-radius: 12px;
    padding: 8px; text-align: center; cursor: pointer; }
  .value .v { font-size: 20px; font-weight: 600; }
  .value .v.text { font-size: 15px; line-height: 24px; }
  .value .n, .value .s { font-size: 12px; color: var(--secondary-text-color); }
  .value.bad .v { color: var(--error-color); }
  .bar { margin: 8px 0; cursor: pointer; }
  .bar .row { display: flex; justify-content: space-between; font-size: 13px; }
  .bar .track { height: 8px; border-radius: 4px; background: var(--secondary-background-color);
    overflow: hidden; margin-top: 4px; }
  .bar .fill { height: 100%; background: #29a8f0; }
  .bar .fill.low { background: var(--warning-color); }
  .notice { border-left: 4px solid var(--warning-color); padding: 4px 8px; margin: 8px 0;
    font-size: 13px; }
  .notice.error { border-color: var(--error-color); }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  button { font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 16px;
    border: 1px solid var(--divider-color); background: var(--card-background-color);
    color: var(--primary-text-color); cursor: pointer; }
  button:hover { background: var(--secondary-background-color); }
`;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

class PoolControlCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._signature = undefined;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement("pool-control-card-editor");
  }

  static getStubConfig(hass) {
    const entry = Object.values(hass.entities || {}).find((e) => e.platform === DOMAIN);
    return { device_id: entry ? entry.device_id : undefined };
  }

  _t(key) {
    const lang = (this._hass?.language || "en").split("-")[0];
    return (STRINGS[lang] || STRINGS.en)[key] || STRINGS.en[key] || key;
  }

  _code(code) {
    const lang = (this._hass?.language || "en").split("-")[0];
    return (STRINGS[lang] || STRINGS.en).codes[code] || code;
  }

  _entities() {
    const all = Object.values(this._hass.entities || {}).filter((e) => e.platform === DOMAIN);
    const deviceId = this._config.device_id || (all[0] && all[0].device_id);
    const map = {};
    for (const entry of all) {
      if (entry.device_id === deviceId && entry.translation_key) {
        map[entry.translation_key] = entry.entity_id;
      }
    }
    return { deviceId, map };
  }

  _state(entityId) {
    return entityId ? this._hass.states[entityId] : undefined;
  }

  _format(entityId) {
    const state = this._state(entityId);
    if (!state || ["unknown", "unavailable"].includes(state.state)) return "–";
    return this._hass.formatEntityState ? this._hass.formatEntityState(state) : state.state;
  }

  _number(entityId) {
    const value = parseFloat(this._state(entityId)?.state);
    return Number.isFinite(value) ? value : undefined;
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });

    const { deviceId, map } = this._entities();
    const status = this._state(map.status);
    const actuators = status?.attributes?.actuators || {};
    const tracked = [...Object.values(map), ...Object.values(actuators)];
    const signature = JSON.stringify([
      deviceId,
      this._hass.language,
      tracked.map((id) => {
        const s = this._hass.states[id];
        return s ? [s.state, s.last_updated] : null;
      }),
    ]);
    if (signature === this._signature) return;
    this._signature = signature;

    if (!deviceId || !status) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div>${this._t("no_device")}</div></ha-card>`;
      return;
    }

    const isOn = (key) => this._state(actuators[key])?.state === "on";
    const device = this._hass.devices?.[deviceId];
    const title = this._config.title || device?.name_by_user || device?.name || "Pool";
    const mode = this._state(map.mode);
    const problems = this._state(map.problem)?.attributes?.problems || [];
    const maintenance = this._state(map.maintenance_due)?.attributes?.tasks || [];
    const dryRun = this._state(map.dry_run)?.state === "on";

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="header">
          <div class="title">${esc(title)}</div>
          ${dryRun ? `<span class="chip warn" data-more="${map.dry_run}">${this._t("dry_run")}</span>` : ""}
          <span class="chip" data-more="${map.status}">${esc(this._format(map.status))}</span>
          ${mode ? this._modeSelect(mode) : ""}
        </div>
        ${this._schematic(map, actuators, isOn)}
        ${this._values(map)}
        ${this._bars(map)}
        ${problems.length ? `<div class="notice error">${this._t("problems")}: ${problems.map((c) => esc(this._code(c))).join(", ")}</div>` : ""}
        ${maintenance.length ? `<div class="notice">${this._t("maintenance")}: ${maintenance.map((c) => esc(this._code(c))).join(", ")}</div>` : ""}
        ${this._actions(map)}
      </ha-card>`;
    this._bind(map);
  }

  _modeSelect(mode) {
    const options = mode.attributes.options || [];
    const label = (option) =>
      this._hass.formatEntityState ? this._hass.formatEntityState(mode, option) : option;
    return `<select id="mode">${options
      .map((o) => `<option value="${esc(o)}" ${o === mode.state ? "selected" : ""}>${esc(label(o))}</option>`)
      .join("")}</select>`;
  }

  _schematic(map, actuators, isOn) {
    const pump = isOn("pump");
    const chlor = isOn("chlorinator");
    const ph = isOn("ph_pump");
    const solar = isOn("solar_pump") || this._state(map.solar_heating)?.state === "on";
    const has = (key) => Boolean(actuators[key]);
    const temp = this._format(map.water_temperature);
    const dev = (key, x, y, label, on, shape) => `
      <g data-more="${esc(actuators[key] || "")}">
        ${shape(x, y, on)}
        <text class="label" x="${x}" y="${y + 34}">${esc(label)}</text>
      </g>`;
    const circle = (x, y, on) => `<circle class="device ${on ? "on" : ""}" cx="${x}" cy="${y}" r="18"/>
      <path d="M${x - 7} ${y - 9} L${x + 9} ${y} L${x - 7} ${y + 9} Z" fill="${on ? "#0b5cad" : "#9e9e9e"}"/>`;
    const box = (x, y, on) => `<rect class="device ${on ? "on" : ""}" x="${x - 18}" y="${y - 16}" width="36" height="32" rx="6"/>
      <text x="${x}" y="${y + 5}" text-anchor="middle" font-size="12" font-weight="700" fill="${on ? "#0b5cad" : "#9e9e9e"}">Cl</text>`;
    const tank = (x, y, on) => `<path class="device ${on ? "on" : ""}" d="M${x - 14} ${y - 18} h28 v30 a6 6 0 0 1 -6 6 h-16 a6 6 0 0 1 -6 -6 z"/>
      <text x="${x}" y="${y + 4}" text-anchor="middle" font-size="11" font-weight="700" fill="${on ? "#0b5cad" : "#9e9e9e"}">pH</text>`;
    const panel = (x, y, on) => `<rect class="device ${on ? "on" : ""}" x="${x - 22}" y="${y - 14}" width="44" height="28" rx="3"/>
      <path d="M${x - 22} ${y} h44 M${x - 7} ${y - 14} v28 M${x + 7} ${y - 14} v28" stroke="${on ? "#0b5cad" : "#9e9e9e"}" stroke-width="1.5"/>`;

    return `
      <svg viewBox="0 0 360 170" role="img">
        <defs>
          <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#5fd3f3"/><stop offset="1" stop-color="#0b5cad"/>
          </linearGradient>
        </defs>
        ${has("solar_pump") ? `<path class="pipe ${solar ? "on" : ""}" d="M45 42 H230"/>` : ""}
        <path class="pipe ${pump ? "on" : ""}" d="M45 122 H230"/>
        ${has("ph_pump") ? `<path class="pipe ${ph ? "on" : ""}" d="M190 60 V122"/>` : ""}
        <rect x="230" y="20" width="118" height="128" rx="14" fill="url(#water)"/>
        <path d="M236 62 q14 -10 28 0 t28 0 t28 0 t22 0" stroke="#fff" stroke-opacity="0.7" stroke-width="4" fill="none"/>
        <text class="pool-temp" x="289" y="108" data-more="${map.water_temperature || ""}">${esc(temp)}</text>
        ${dev("pump", 45, 122, this._t("pump"), pump, circle)}
        ${has("chlorinator") ? dev("chlorinator", 135, 122, this._t("chlorinator"), chlor, box) : ""}
        ${has("ph_pump") ? dev("ph_pump", 190, 42, this._t("ph_pump"), ph, tank) : ""}
        ${has("solar_pump") ? dev("solar_pump", 45, 42, this._t("solar"), solar, panel) : ""}
      </svg>`;
  }

  _values(map) {
    const item = (key, name, sub, bad) => {
      if (!map[key]) return "";
      return `<div class="value ${bad ? "bad" : ""}" data-more="${map[key]}">
        <div class="v ${Number.isFinite(parseFloat(this._state(map[key])?.state)) ? "" : "text"}">${esc(this._format(map[key]))}</div>
        <div class="n">${esc(name)}</div>
        ${sub ? `<div class="s">${esc(sub)}</div>` : ""}
      </div>`;
    };
    const name = (key, fallback) =>
      this._state(map[key])?.attributes?.friendly_name?.replace(/^.*? /, "") || fallback;
    const ph = this._number(map.ph);
    const phTarget = this._number(map.ph_target);
    const orp = this._number(map.orp);
    const orpTarget = this._number(map.orp_target);
    const swim = this._state(map.swimming_allowed)?.state;
    return `<div class="values">
      ${item("ph", "pH", phTarget !== undefined ? `${this._t("set_point")} ${phTarget}` : "", ph !== undefined && (ph < 6.8 || ph > 8.2))}
      ${item("orp", "ORP", orpTarget !== undefined ? `${this._t("set_point")} ${Math.round(orpTarget)} mV` : "", orp !== undefined && orp < 500)}
      ${item("swimming_status", name("swimming_status", "Swimming"), "", swim === "off")}
      ${item("saturation_index", "LSI", "", false)}
    </div>`;
  }

  _bars(map) {
    const bar = (key, label, value, max, text, low) => {
      if (!map[key] || value === undefined) return "";
      const percent = Math.max(0, Math.min(100, max ? (value / max) * 100 : value));
      return `<div class="bar" data-more="${map[key]}">
        <div class="row"><span>${esc(label)}</span><span>${esc(text)}</span></div>
        <div class="track"><div class="fill ${low ? "low" : ""}" style="width:${percent}%"></div></div>
      </div>`;
    };
    const runtime = this._number(map.pump_runtime_today);
    const target = this._number(map.filtration_target);
    const tank = this._number(map.ph_tank_level_percent);
    return [
      bar("pump_runtime_today", this._t("runtime"), runtime, target,
        `${runtime?.toFixed(1) ?? "–"} / ${target?.toFixed(1) ?? "–"} h`, false),
      bar("ph_tank_level_percent", this._t("tank"), tank, 100,
        `${this._format(map.ph_tank_level)} · ${this._t("dosed")} ${this._format(map.ph_dosed_today)}`,
        tank !== undefined && tank < 15),
    ].join("");
  }

  _actions(map) {
    const button = (key, label, confirmKey) =>
      map[key] ? `<button data-press="${map[key]}" ${confirmKey ? `data-confirm="${confirmKey}"` : ""}>${esc(label)}</button>` : "";
    return `<div class="actions">
      ${button("start_boost", this._t("boost"))}
      ${button("start_shock", this._t("shock"))}
      ${button("ph_manual_pulse", this._t("pulse"), "confirm_pulse")}
      ${button("ph_tank_refilled", this._t("refilled"), "confirm_refilled")}
    </div>`;
  }

  _bind(map) {
    const root = this.shadowRoot;
    root.querySelectorAll("[data-more]").forEach((el) => {
      const entityId = el.getAttribute("data-more");
      if (!entityId) return;
      el.addEventListener("click", () => {
        this.dispatchEvent(new CustomEvent("hass-more-info", {
          detail: { entityId }, bubbles: true, composed: true,
        }));
      });
    });
    root.querySelectorAll("[data-press]").forEach((el) => {
      el.addEventListener("click", () => {
        const confirmKey = el.getAttribute("data-confirm");
        if (confirmKey && !window.confirm(this._t(confirmKey))) return;
        this._hass.callService("button", "press", { entity_id: el.getAttribute("data-press") });
      });
    });
    const select = root.getElementById("mode");
    if (select) {
      select.addEventListener("change", (ev) => {
        this._hass.callService("select", "select_option", {
          entity_id: map.mode, option: ev.target.value,
        });
      });
    }
  }
}

class PoolControlCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", {
          detail: { config: this._config }, bubbles: true, composed: true,
        }));
      });
      this.appendChild(this._form);
    }
    const lang = (this._hass.language || "en").split("-")[0];
    const t = STRINGS[lang] || STRINGS.en;
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      { name: "device_id", selector: { device: { integration: DOMAIN } } },
      { name: "title", selector: { text: {} } },
    ];
    this._form.computeLabel = (schema) => (schema.name === "device_id" ? t.device : t.title);
  }
}

if (!customElements.get("pool-control-card")) {
  customElements.define("pool-control-card", PoolControlCard);
  customElements.define("pool-control-card-editor", PoolControlCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "pool-control-card",
    name: "Pool Control",
    description: "Schematic, readings and actions of a Pool Control device.",
    preview: true,
    documentationURL: "https://github.com/AndyKausG/ha-pool_control/blob/main/docs/dashboard.md",
  });
  console.info(`%c POOL-CONTROL-CARD %c ${VERSION} `, "background:#0b5cad;color:#fff", "");
}

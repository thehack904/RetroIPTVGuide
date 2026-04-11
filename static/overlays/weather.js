/* Weather overlay renderer (v4)
 * Renders the full retro TV weather broadcast layout into the virtual channel
 * overlay, matching the /weather standalone page design.
 * Compact: base font-size is set proportional to the container width in JS so
 * every em-based value scales together, making the overlay legible even in a
 * small player without needing to expand it.
 * Endpoint: GET /api/weather
 */
(function () {
  'use strict';
  const TYPE      = 'weather';
  const STYLE_ID  = 'vc-weather-overlay-styles-v4';
  const SVG_ID    = 'vc-weather-overlay-svgs';

  // ── CSS: all sizes in em so they scale with the container-width-driven
  //         font-size injected by render() onto .vc-wx-frame ─────────────────
  const CSS = `
    .vc-wx-frame {
      position: absolute;
      inset: 0;
      /* font-size set dynamically in JS proportional to container width */
      background: linear-gradient(160deg, #1030c8 0%, #0a1a80 40%, #081060 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    .vc-wx-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.06) 3px, rgba(0,0,0,0.06) 4px);
      pointer-events: none;
      z-index: 10;
    }
    .vc-wx-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1640d4 50%, #0d2aaa 100%);
      border-bottom: 2px solid #4a70ff;
      padding: 0.28em 0.8em;
      display: flex;
      align-items: center;
      gap: 0.6em;
      flex-shrink: 0;
    }
    .vc-wx-header-title {
      font-size: 1.35em;
      font-weight: 900;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.25em;
    }
    .vc-wx-header-subtitle {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #fff;
      margin-left: auto;
    }
    .vc-wx-updated {
      font-size: 0.75em;
      font-weight: 700;
      color: #ffd700;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.15em 0.8em 0;
      flex-shrink: 0;
    }
    .vc-wx-body {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 2.2fr;
      grid-template-rows: 1fr auto;
      gap: 0.3em;
      padding: 0.3em 0.45em 0.2em;
      min-height: 0;
      overflow: hidden;
    }
    .vc-wx-box {
      background: rgba(10,40,170,0.75);
      border: 1px solid #3058d8;
      border-radius: 3px;
      padding: 0.28em 0.45em;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 6px rgba(0,0,0,0.4);
      display: flex;
      flex-direction: column;
    }
    .vc-wx-box-title {
      font-size: 0.76em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #c8d8ff;
      border-bottom: 1px solid #3058d8;
      padding-bottom: 0.2em;
      margin-bottom: 0.25em;
      white-space: nowrap;
    }
    .vc-wx-current { grid-column: 1; grid-row: 1; }
    .vc-wx-current-icon {
      line-height: 1;
      text-align: center;
      margin: 0.05em 0;
    }
    .vc-wx-current-temp {
      font-size: 2.5em;
      font-weight: 900;
      text-align: center;
      line-height: 1;
      margin: 0.05em 0;
    }
    .vc-wx-current-cond {
      font-size: 0.85em;
      font-weight: 700;
      text-align: center;
      margin-bottom: 0.2em;
    }
    .vc-wx-current-details {
      font-size: 0.72em;
      line-height: 1.5;
      color: #d0e0ff;
      margin-top: auto;
    }
    .vc-wx-today { grid-column: 2; grid-row: 1; }
    .vc-wx-today-cols {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      flex: 1;
      gap: 0;
      height: 100%;
    }
    .vc-wx-period {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.1em 0.25em;
    }
    .vc-wx-period + .vc-wx-period { border-left: 1px solid #3058d8; }
    .vc-wx-period-label {
      font-size: 0.72em;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #c8d8ff;
      margin-bottom: 0.1em;
    }
    .vc-wx-period-icon {
      line-height: 1;
      margin: 0.08em 0;
    }
    .vc-wx-period-temp {
      font-size: 1.9em;
      font-weight: 900;
      line-height: 1;
    }
    .vc-wx-period-cond {
      font-size: 0.68em;
      font-weight: 700;
      text-align: center;
      margin-top: 0.1em;
      color: #d0e0ff;
    }
    .vc-wx-extended { grid-column: 1 / -1; grid-row: 2; }
    .vc-wx-extended .vc-wx-box-title { color: #40c0ff; }
    .vc-wx-ext-cols {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
    }
    .vc-wx-ext-day {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.1em 0.25em;
    }
    .vc-wx-ext-day + .vc-wx-ext-day { border-left: 1px solid #3058d8; }
    .vc-wx-ext-dow {
      font-size: 0.76em;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #c8d8ff;
    }
    .vc-wx-ext-icon {
      line-height: 1;
      margin: 0.06em 0;
    }
    .vc-wx-ext-temps {
      font-size: 0.9em;
      font-weight: 900;
    }
    .vc-wx-ext-cond {
      font-size: 0.65em;
      font-weight: 700;
      color: #d0e0ff;
      text-align: center;
    }
    .vc-wx-ticker-bar {
      background: #0a0e2a;
      border-top: 1px solid #4a70ff;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.7em;
    }
    .vc-wx-ticker-label {
      background: #ffd700;
      color: #0a0e2a;
      font-size: 0.75em;
      font-weight: 900;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      padding: 0 0.55em;
      white-space: nowrap;
      height: 100%;
      display: flex;
      align-items: center;
      flex-shrink: 0;
    }
    .vc-wx-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-wx-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.72em;
      font-weight: 700;
      color: #ffd700;
      animation: vc-wx-scroll 28s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-wx-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
    .vc-wx-svg { display: inline-block; vertical-align: middle; }
    .vc-wx-ext-lo { opacity: 0.7; }
    .vc-wx-no-data { color: #90a8f0; padding: 0.4em; }

    /* ── Segment: 5-Day Forecast ─────────────────────────────────── */
    .vc-wx-seg-forecast {
      flex: 1;
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 0.3em;
      padding: 0.3em 0.45em 0.2em;
      min-height: 0;
      overflow: hidden;
    }
    .vc-wx-fc-day {
      background: rgba(10,40,170,0.75);
      border: 1px solid #3058d8;
      border-radius: 3px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 6px rgba(0,0,0,0.4);
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 0.3em 0.2em;
      overflow: hidden;
    }
    .vc-wx-fc-today {
      border-color: #40c0ff;
      background: rgba(10,60,190,0.85);
    }
    .vc-wx-fc-dow {
      font-size: 0.82em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #c8d8ff;
      margin-bottom: 0.1em;
    }
    .vc-wx-fc-today .vc-wx-fc-dow { color: #40c0ff; }
    .vc-wx-fc-icon { line-height: 1; margin: 0.15em 0; }
    .vc-wx-fc-hi {
      font-size: 1.9em;
      font-weight: 900;
      line-height: 1;
      margin-top: 0.05em;
    }
    .vc-wx-fc-lo {
      font-size: 1.1em;
      font-weight: 700;
      opacity: 0.6;
      line-height: 1;
      margin-bottom: 0.1em;
    }
    .vc-wx-fc-cond {
      font-size: 0.64em;
      font-weight: 700;
      text-align: center;
      color: #d0e0ff;
      margin-top: auto;
      padding: 0 0.1em;
    }

    /* ── Segment: Regional Radar ─────────────────────────────────── */
    .vc-wx-seg-radar {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 0.3em 0.45em 0.15em;
      min-height: 0;
      overflow: hidden;
      gap: 0.2em;
    }
    .vc-wx-radar-img-wrap {
      flex: 1;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      background: #000818;
      border: 1px solid #3058d8;
      border-radius: 3px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.5);
      min-height: 0;
      position: relative;
    }
    .vc-wx-radar-img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      display: block;
    }
    .vc-wx-radar-err {
      color: #7090c0;
      font-size: 0.8em;
      font-weight: 700;
      text-align: center;
      padding: 1em;
      display: none;
    }
    .vc-wx-radar-caption {
      font-size: 0.68em;
      font-weight: 700;
      color: #8098c0;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      align-self: flex-end;
    }

    /* ── Segment: Severe Weather Alerts ──────────────────────────── */
    .vc-wx-seg-alerts {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 0.35em 0.45em 0.2em;
      gap: 0.3em;
      min-height: 0;
      overflow: hidden;
    }
    .vc-wx-alert-item {
      background: rgba(140,20,20,0.7);
      border: 1px solid #cc4444;
      border-radius: 3px;
      padding: 0.5em 0.7em;
      display: flex;
      align-items: center;
      gap: 0.5em;
      box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    }
    .vc-wx-alert-icon {
      font-size: 1.6em;
      flex-shrink: 0;
    }
    .vc-wx-alert-text {
      font-size: 0.88em;
      font-weight: 900;
      letter-spacing: 0.03em;
      color: #ffdddd;
    }
    .vc-wx-no-alerts {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.4em;
    }
    .vc-wx-no-alerts-icon { font-size: 3.5em; line-height: 1; }
    .vc-wx-no-alerts-title {
      font-size: 1em;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #60d060;
    }
    .vc-wx-no-alerts-sub {
      font-size: 0.72em;
      color: #70a870;
    }
  `;

  // ── SVG icon defs (same symbols as weather.html) ─────────────────────────
  const SVG_DEFS = `
    <svg id="${SVG_ID}" width="0" height="0" style="position:absolute;overflow:hidden">
      <defs>
        <symbol id="vc-icon-sunny" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="13" fill="#ffd700" stroke="#ffb300" stroke-width="1.5"/>
          <g stroke="#ffd700" stroke-width="2.5" stroke-linecap="round">
            <line x1="32" y1="4"  x2="32" y2="11"/>
            <line x1="32" y1="53" x2="32" y2="60"/>
            <line x1="4"  y1="32" x2="11" y2="32"/>
            <line x1="53" y1="32" x2="60" y2="32"/>
            <line x1="12" y1="12" x2="17" y2="17"/>
            <line x1="47" y1="47" x2="52" y2="52"/>
            <line x1="52" y1="12" x2="47" y2="17"/>
            <line x1="17" y1="47" x2="12" y2="52"/>
          </g>
        </symbol>
        <symbol id="vc-icon-partly_cloudy" viewBox="0 0 64 64">
          <circle cx="24" cy="22" r="11" fill="#ffd700" stroke="#ffb300" stroke-width="1.5"/>
          <g stroke="#ffd700" stroke-width="2" stroke-linecap="round">
            <line x1="24" y1="4"  x2="24" y2="9"/>
            <line x1="24" y1="35" x2="24" y2="38"/>
            <line x1="6"  y1="22" x2="11" y2="22"/>
            <line x1="37" y1="22" x2="42" y2="22"/>
            <line x1="10" y1="10" x2="14" y2="14"/>
            <line x1="34" y1="30" x2="38" y2="34"/>
            <line x1="38" y1="10" x2="34" y2="14"/>
            <line x1="14" y1="30" x2="10" y2="34"/>
          </g>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#d0deff"/>
          <rect x="22" y="28" width="24" height="14" rx="7" fill="#e8eeff"/>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#c0d0f0"/>
        </symbol>
        <symbol id="vc-icon-cloudy" viewBox="0 0 64 64">
          <rect x="8"  y="32" width="48" height="18" rx="9" fill="#c0d0f0"/>
          <rect x="16" y="22" width="32" height="18" rx="9" fill="#d8e4ff"/>
          <rect x="8"  y="32" width="48" height="18" rx="9" fill="#b0c4e8"/>
        </symbol>
        <symbol id="vc-icon-partly_cloudy_night" viewBox="0 0 64 64">
          <path d="M34 8 C24 10 18 20 22 30 C26 40 38 42 46 36 C40 40 28 38 24 28 C20 18 28 8 34 8Z" fill="#c8b44a" stroke="#a89030" stroke-width="1"/>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#d0deff"/>
          <rect x="22" y="28" width="24" height="14" rx="7" fill="#e8eeff"/>
          <rect x="14" y="36" width="36" height="14" rx="7" fill="#c0d0f0"/>
        </symbol>
        <symbol id="vc-icon-cloudy_night" viewBox="0 0 64 64">
          <path d="M28 6 C18 8 12 18 16 28 C20 38 32 40 40 34 C34 38 22 36 18 26 C14 16 22 6 28 6Z" fill="#c8b44a" stroke="#a89030" stroke-width="1"/>
          <rect x="8"  y="32" width="48" height="18" rx="9" fill="#b0c4e8"/>
          <rect x="16" y="22" width="32" height="18" rx="9" fill="#c8d8f8"/>
        </symbol>
        <symbol id="vc-icon-rain" viewBox="0 0 64 64">
          <rect x="8"  y="18" width="48" height="16" rx="8" fill="#b0c4e8"/>
          <rect x="16" y="10" width="32" height="16" rx="8" fill="#c8d8f8"/>
          <g stroke="#4488cc" stroke-width="2.5" stroke-linecap="round">
            <line x1="20" y1="40" x2="18" y2="52"/>
            <line x1="32" y1="40" x2="30" y2="52"/>
            <line x1="44" y1="40" x2="42" y2="52"/>
          </g>
        </symbol>
        <symbol id="vc-icon-showers" viewBox="0 0 64 64">
          <circle cx="24" cy="16" r="9"  fill="#ffd700" stroke="#ffb300" stroke-width="1.5"/>
          <rect x="18" y="24" width="32" height="14" rx="7" fill="#b0c4e8"/>
          <rect x="26" y="16" width="20" height="12" rx="6" fill="#c8d8f8"/>
          <g stroke="#4488cc" stroke-width="2.5" stroke-linecap="round">
            <line x1="24" y1="44" x2="22" y2="56"/>
            <line x1="36" y1="44" x2="34" y2="56"/>
            <line x1="48" y1="44" x2="46" y2="56"/>
          </g>
        </symbol>
        <symbol id="vc-icon-thunderstorm" viewBox="0 0 64 64">
          <rect x="8"  y="12" width="48" height="16" rx="8" fill="#8090b0"/>
          <rect x="16" y="6"  width="32" height="14" rx="7" fill="#a0b0c8"/>
          <polygon points="34,28 26,44 32,44 28,58 42,38 36,38" fill="#ffd700"/>
        </symbol>
        <symbol id="vc-icon-drizzle" viewBox="0 0 64 64">
          <rect x="8"  y="18" width="48" height="16" rx="8" fill="#b0c4e8"/>
          <rect x="16" y="10" width="32" height="16" rx="8" fill="#c8d8f8"/>
          <g stroke="#88aadd" stroke-width="2" stroke-linecap="round">
            <line x1="20" y1="40" x2="19" y2="48"/>
            <line x1="28" y1="42" x2="27" y2="50"/>
            <line x1="36" y1="40" x2="35" y2="48"/>
            <line x1="44" y1="42" x2="43" y2="50"/>
          </g>
        </symbol>
        <symbol id="vc-icon-snow" viewBox="0 0 64 64">
          <rect x="8"  y="14" width="48" height="16" rx="8" fill="#b0c4e8"/>
          <rect x="16" y="6"  width="32" height="16" rx="8" fill="#c8d8f8"/>
          <g fill="#d0e8ff">
            <circle cx="20" cy="46" r="3"/>
            <circle cx="32" cy="44" r="3"/>
            <circle cx="44" cy="46" r="3"/>
            <circle cx="26" cy="54" r="2.5"/>
            <circle cx="38" cy="54" r="2.5"/>
          </g>
        </symbol>
        <symbol id="vc-icon-foggy" viewBox="0 0 64 64">
          <rect x="8"  y="12" width="48" height="10" rx="5" fill="#b0bcd0" opacity="0.8"/>
          <rect x="12" y="26" width="40" height="8"  rx="4" fill="#a8b8cc" opacity="0.8"/>
          <rect x="8"  y="38" width="48" height="8"  rx="4" fill="#98a8bc" opacity="0.7"/>
          <rect x="14" y="50" width="36" height="8"  rx="4" fill="#8898ac" opacity="0.6"/>
        </symbol>
      </defs>
    </svg>`;

  const ICON_MAP = {
    sunny:               'vc-icon-sunny',
    partly_cloudy:       'vc-icon-partly_cloudy',
    partly_cloudy_night: 'vc-icon-partly_cloudy_night',
    cloudy:              'vc-icon-cloudy',
    cloudy_night:        'vc-icon-cloudy_night',
    rain:                'vc-icon-rain',
    showers:             'vc-icon-showers',
    thunderstorm:        'vc-icon-thunderstorm',
    drizzle:             'vc-icon-drizzle',
    snow:                'vc-icon-snow',
    foggy:               'vc-icon-foggy',
  };

  function ensureAssets() {
    if (!document.getElementById(STYLE_ID)) {
      const s = document.createElement('style');
      s.id = STYLE_ID;
      s.textContent = CSS;
      document.head.appendChild(s);
    }
    if (!document.getElementById(SVG_ID)) {
      const tmp = document.createElement('div');
      tmp.innerHTML = SVG_DEFS.trim();
      document.body.insertBefore(tmp.firstChild, document.body.firstChild);
    }
  }

  // Font-size scaling: base px = container_width / FONT_SCALE_DIVISOR, clamped
  // to [FONT_MIN_PX, FONT_MAX_PX].  All em values in CSS scale together.
  const FONT_SCALE_DIVISOR = 48;
  const FONT_MIN_PX        = 9;
  const FONT_MAX_PX        = 13;

  // Icon sizes as multiples of the base font (px)
  const ICON_RATIO_LG  = 3.2;   // current conditions
  const ICON_RATIO_MD  = 2.4;   // today periods
  const ICON_RATIO_SM  = 1.9;   // extended days
  const ICON_RATIO_HDR = 1.4;   // header icon

  function iconSvg(key, size) {
    const sym = ICON_MAP[key] || 'vc-icon-cloudy';
    return `<svg class="vc-wx-svg" width="${size}" height="${size}"><use href="#${sym}"/></svg>`;
  }

  function tempStr(t) {
    return (t != null) ? `${t}°` : '--°';
  }

  function formatLocalTime(isoStr) {
    try {
      return new Date(isoStr).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch (e) { return isoStr; }
  }

  // ── Shared header / ticker helpers ─────────────────────────────────────────

  function headerHtml(subtitle, iconHdr) {
    return `
      <div class="vc-wx-header">
        <div class="vc-wx-header-title">
          <span>RetroIPTV</span>
          ${iconSvg('partly_cloudy', iconHdr)}
          <span>Weather</span>
        </div>
        <div class="vc-wx-header-subtitle">${subtitle}</div>
      </div>`;
  }

  function updatedBarHtml(location, updatedIso) {
    return `<div class="vc-wx-updated">
      <span>${location || ''}</span>
      <span>UPDATED: ${updatedIso ? formatLocalTime(updatedIso) : ''}</span>
    </div>`;
  }

  function tickerHtml(ticks) {
    const tickText = (ticks && ticks.length)
      ? ticks.join(' \u2022 ') + ' \u2022 '
      : 'No active weather alerts \u2022 ';
    return `
      <div class="vc-wx-ticker-bar">
        <div class="vc-wx-ticker-label">Weather Alert:</div>
        <div class="vc-wx-ticker-scroll">
          <span class="vc-wx-ticker-track">${tickText.repeat(3)}</span>
        </div>
      </div>`;
  }

  // ── Segment 0: Current Conditions ─────────────────────────────────────────

  function renderCurrent(data, frame, bp) {
    const now   = data?.now   || {};
    const today = Array.isArray(data?.today)    ? data.today    : [];
    const ext   = Array.isArray(data?.extended) ? data.extended : [];
    const ticks = Array.isArray(data?.ticker)   ? data.ticker   : [];

    const iconLg  = Math.round(bp * ICON_RATIO_LG);
    const iconMd  = Math.round(bp * ICON_RATIO_MD);
    const iconSm  = Math.round(bp * ICON_RATIO_SM);
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);

    const periodCols = today.map(p => `
      <div class="vc-wx-period">
        <div class="vc-wx-period-label">${p.label || ''}</div>
        <div class="vc-wx-period-icon">${iconSvg(p.icon, iconMd)}</div>
        <div class="vc-wx-period-temp">${tempStr(p.temp)}</div>
        <div class="vc-wx-period-cond">${p.condition || ''}</div>
      </div>`).join('');

    const extCols = ext.map(d => `
      <div class="vc-wx-ext-day">
        <div class="vc-wx-ext-dow">${d.dow || ''}</div>
        <div class="vc-wx-ext-icon">${iconSvg(d.icon, iconSm)}</div>
        <div class="vc-wx-ext-temps">${tempStr(d.hi)} <span class="vc-wx-ext-lo">${tempStr(d.lo)}</span></div>
        <div class="vc-wx-ext-cond">${d.condition || ''}</div>
      </div>`).join('');

    const details = [];
    if (now.humidity != null)  details.push(`Humid: ${now.humidity}%`);
    if (now.wind)               details.push(`Wind: ${now.wind}`);
    if (now.feels_like != null) details.push(`Feels Like: ${now.feels_like}°`);

    frame.innerHTML =
      headerHtml('Current Conditions', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      `<div class="vc-wx-body">
        <div class="vc-wx-box vc-wx-current">
          <div class="vc-wx-box-title">Current Conditions</div>
          <div class="vc-wx-current-icon">${iconSvg(now.icon || 'cloudy', iconLg)}</div>
          <div class="vc-wx-current-temp">${tempStr(now.temp)}</div>
          <div class="vc-wx-current-cond">${now.condition || ''}</div>
          <div class="vc-wx-current-details">${details.join('<br>')}</div>
        </div>
        <div class="vc-wx-box vc-wx-today">
          <div class="vc-wx-box-title">Today's Forecast</div>
          <div class="vc-wx-today-cols">${periodCols}</div>
        </div>
        <div class="vc-wx-box vc-wx-extended">
          <div class="vc-wx-box-title">Extended Outlook</div>
          <div class="vc-wx-ext-cols">${extCols || '<div class="vc-wx-no-data">No extended forecast available.</div>'}</div>
        </div>
      </div>` +
      tickerHtml(ticks);
  }

  // ── Segment 1: 5-Day Forecast ──────────────────────────────────────────────

  function renderForecast(data, frame, bp) {
    const five = Array.isArray(data?.five_day) ? data.five_day : [];
    const ticks = Array.isArray(data?.ticker) ? data.ticker : [];
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);
    const iconLg  = Math.round(bp * ICON_RATIO_LG);

    const dayCols = five.map((d, i) => `
      <div class="vc-wx-fc-day${i === 0 ? ' vc-wx-fc-today' : ''}">
        <div class="vc-wx-fc-dow">${d.dow || ''}</div>
        <div class="vc-wx-fc-icon">${iconSvg(d.icon, iconLg)}</div>
        <div class="vc-wx-fc-hi">${tempStr(d.hi)}</div>
        <div class="vc-wx-fc-lo">${tempStr(d.lo)}</div>
        <div class="vc-wx-fc-cond">${d.condition || ''}</div>
      </div>`).join('');

    frame.innerHTML =
      headerHtml('5-Day Forecast', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      `<div class="vc-wx-seg-forecast">
        ${dayCols || '<div class="vc-wx-no-data" style="grid-column:1/-1">No forecast data available.</div>'}
      </div>` +
      tickerHtml(ticks);
  }

  // ── Segment 2: Regional Radar ──────────────────────────────────────────────

  function renderRadar(data, frame, bp) {
    const ticks   = Array.isArray(data?.ticker) ? data.ticker : [];
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);
    const radarUrl = data?.radar_url || '';

    frame.innerHTML =
      headerHtml('Regional Radar', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      `<div class="vc-wx-seg-radar">
        <div class="vc-wx-radar-img-wrap" id="vc-wx-radar-wrap">
          ${radarUrl
            ? `<img class="vc-wx-radar-img" id="vc-wx-radar-img"
                    src="${radarUrl}" alt="Regional Radar"
                    onerror="document.getElementById('vc-wx-radar-img').style.display='none';
                             document.getElementById('vc-wx-radar-err').style.display='block';">
               <div class="vc-wx-radar-err" id="vc-wx-radar-err">Radar Unavailable</div>`
            : `<div class="vc-wx-radar-err" style="display:block">Radar Unavailable &mdash; No location configured</div>`}
        </div>
        <div class="vc-wx-radar-caption">Source: NOAA/NWS</div>
      </div>` +
      tickerHtml(ticks);
  }

  // ── Segment 3: Severe Weather Alerts ──────────────────────────────────────

  function renderAlerts(data, frame, bp) {
    const ticks   = Array.isArray(data?.ticker) ? data.ticker : [];
    const iconHdr = Math.round(bp * ICON_RATIO_HDR);
    const iconLg  = Math.round(bp * ICON_RATIO_LG);

    let bodyHtml;
    if (ticks.length) {
      const items = ticks.map(t => `
        <div class="vc-wx-alert-item">
          <div class="vc-wx-alert-icon">&#9888;</div>
          <div class="vc-wx-alert-text">${t}</div>
        </div>`).join('');
      bodyHtml = `<div class="vc-wx-seg-alerts">${items}</div>`;
    } else {
      bodyHtml = `
        <div class="vc-wx-seg-alerts">
          <div class="vc-wx-no-alerts">
            <div class="vc-wx-no-alerts-icon">${iconSvg('sunny', iconLg)}</div>
            <div class="vc-wx-no-alerts-title">No Active Severe Weather Alerts</div>
            <div class="vc-wx-no-alerts-sub">${data?.location || 'Local Area'}</div>
          </div>
        </div>`;
    }

    frame.innerHTML =
      headerHtml('Severe Weather Alerts', iconHdr) +
      updatedBarHtml(data?.location, data?.updated) +
      bodyHtml +
      tickerHtml(ticks);
  }

  function render(data, root) {
    ensureAssets();
    root.querySelectorAll('.vc-overlay').forEach(e => e.remove());
    root.classList.remove('hidden');

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-wx-frame';
    frame.id = 'vc-wx-frame';

    const now = data?.now || {};

    // ── Not configured ──────────────────────────────────────────────────────
    if (now.condition === 'Not Configured') {
      const bp      = Math.max(FONT_MIN_PX, Math.min((root.offsetWidth || 960) / FONT_SCALE_DIVISOR, FONT_MAX_PX));
      const iconLg  = Math.round(bp * ICON_RATIO_LG);
      const iconHdr = Math.round(bp * ICON_RATIO_HDR);
      frame.style.fontSize = bp + 'px';
      frame.innerHTML = `
        <div class="vc-wx-header">
          <div class="vc-wx-header-title">
            <span>RetroIPTV</span>
            ${iconSvg('partly_cloudy', iconHdr)}
            <span>Weather</span>
          </div>
          <div class="vc-wx-header-subtitle">Local Forecast</div>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;
                    justify-content:center;gap:0.5em;padding:1em;text-align:center;">
          <div>${iconSvg('partly_cloudy', iconLg)}</div>
          <div style="font-size:1em;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;
                      color:#90c8ff;">No Location Configured</div>
          <div style="font-size:0.72em;color:#8098c0;max-width:22em;line-height:1.5;">
            Add a Zip Code or Latitude&nbsp;/&nbsp;Longitude in
            Virtual Weather Channel Settings.
          </div>
        </div>
        <div class="vc-wx-ticker-bar">
          <div class="vc-wx-ticker-label">Weather Alert:</div>
          <div class="vc-wx-ticker-scroll">
            <span class="vc-wx-ticker-track">No location configured \u2022 </span>
          </div>
        </div>`;
      overlay.appendChild(frame);
      root.appendChild(overlay);
      return;
    }

    // Base font-size drives all em values
    const fw  = root.offsetWidth || 960;
    const bp  = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX));
    frame.style.fontSize = bp + 'px';

    // Dispatch to the correct segment renderer
    const segment = (data?.segment != null) ? data.segment : 0;
    if      (segment === 1) { renderForecast(data, frame, bp); }
    else if (segment === 2) { renderRadar(data, frame, bp); }
    else if (segment === 3) { renderAlerts(data, frame, bp); }
    else                    { renderCurrent(data, frame, bp); }

    overlay.appendChild(frame);
    root.appendChild(overlay);
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/weather');
  }

  // ── Self-driven cycle timer ────────────────────────────────────────────────
  // Mirrors the on_this_day pattern: after each fetch the client schedules its
  // next OverlayEngine.tick() to fire precisely at the segment boundary using
  // ms_until_next from the API response.  This makes the overlay cycle at the
  // admin-configured rate rather than at the engine's static refreshSeconds.

  const CYCLE_FALLBACK_MS = 60 * 1000;  // fallback if ms_until_next is unavailable
  let _cycleTimer = null;

  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
  }

  async function fetchDataWithCycling() {
    const data = await fetchData();
    if (_cycleTimer === null) {
      const ms = (data && data.ms_until_next > 0) ? data.ms_until_next : CYCLE_FALLBACK_MS;
      _cycleTimer = setTimeout(advanceAndTick, ms);
    }
    return data;
  }

  function _clearCycleTimer() {
    if (_cycleTimer !== null) {
      clearTimeout(_cycleTimer);
      _cycleTimer = null;
    }
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchDataWithCycling, render });
  window.OverlayEngine.onStop(_clearCycleTimer);
})();


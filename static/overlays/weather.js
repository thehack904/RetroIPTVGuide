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
      text-align: right;
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

  function render(data, root) {
    ensureAssets();
    root.querySelectorAll('.vc-overlay').forEach(e => e.remove());
    root.classList.remove('hidden');

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-wx-frame';
    frame.id = 'vc-wx-frame';

    const now   = data?.now   || {};
    const today = Array.isArray(data?.today)    ? data.today    : [];
    const ext   = Array.isArray(data?.extended) ? data.extended : [];
    const ticks = Array.isArray(data?.ticker)   ? data.ticker   : [];

    // Base font-size drives all em values — scales with container width so the
    // overlay is legible at small player sizes without needing to expand it.
    const fw          = root.offsetWidth || 960;
    const baseFontPx  = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX));
    frame.style.fontSize = baseFontPx + 'px';

    // Icon sizes in px, proportional to base font
    const iconLg  = Math.round(baseFontPx * ICON_RATIO_LG);   // current conditions
    const iconMd  = Math.round(baseFontPx * ICON_RATIO_MD);   // today periods
    const iconSm  = Math.round(baseFontPx * ICON_RATIO_SM);   // extended days
    const iconHdr = Math.round(baseFontPx * ICON_RATIO_HDR);  // header icon

    // Today periods
    const periodCols = today.map(p => `
      <div class="vc-wx-period">
        <div class="vc-wx-period-label">${p.label || ''}</div>
        <div class="vc-wx-period-icon">${iconSvg(p.icon, iconMd)}</div>
        <div class="vc-wx-period-temp">${tempStr(p.temp)}</div>
        <div class="vc-wx-period-cond">${p.condition || ''}</div>
      </div>`).join('');

    // Extended days
    const extCols = ext.map(d => `
      <div class="vc-wx-ext-day">
        <div class="vc-wx-ext-dow">${d.dow || ''}</div>
        <div class="vc-wx-ext-icon">${iconSvg(d.icon, iconSm)}</div>
        <div class="vc-wx-ext-temps">${tempStr(d.hi)} <span class="vc-wx-ext-lo">${tempStr(d.lo)}</span></div>
        <div class="vc-wx-ext-cond">${d.condition || ''}</div>
      </div>`).join('');

    // Ticker
    const tickText = ticks.length
      ? ticks.join(' \u2022 ') + ' \u2022 '
      : 'No active weather alerts \u2022 ';

    // Current details
    const details = [];
    if (now.humidity != null) details.push(`Humid: ${now.humidity}%`);
    if (now.wind)              details.push(`Wind: ${now.wind}`);
    if (now.feels_like != null) details.push(`Feels Like: ${now.feels_like}°`);

    frame.innerHTML = `
      <div class="vc-wx-header">
        <div class="vc-wx-header-title">
          <span>RetroIPTV</span>
          ${iconSvg('partly_cloudy', iconHdr)}
          <span>Weather</span>
        </div>
        <div class="vc-wx-header-subtitle">Local Forecast</div>
      </div>
      <div class="vc-wx-updated">UPDATED: ${data?.updated || ''}</div>
      <div class="vc-wx-body">
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
      </div>
      <div class="vc-wx-ticker-bar">
        <div class="vc-wx-ticker-label">Weather Alert:</div>
        <div class="vc-wx-ticker-scroll">
          <span class="vc-wx-ticker-track">${tickText.repeat(3)}</span>
        </div>
      </div>`;

    overlay.appendChild(frame);
    root.appendChild(overlay);
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/weather');
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render });
})();


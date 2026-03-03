/* Status overlay renderer (v2)
 * Renders the full retro TV broadcast status layout into the virtual channel
 * overlay, matching the /status standalone page design.
 * All CSS values are em-based so everything scales with the JS-driven base
 * font-size, keeping the overlay legible at any player size.
 * Endpoint: GET /api/virtual/status
 */
(function () {
  'use strict';
  const TYPE     = 'status';
  const STYLE_ID = 'vc-status-overlay-styles-v2';

  const TICKER_PX_PER_SEC   = 40;
  const TICKER_REPEAT_COUNT = 3;

  // Font-size scaling: base px = container_width / FONT_SCALE_DIVISOR, clamped
  const FONT_SCALE_DIVISOR = 52;
  const FONT_MIN_PX        = 9;
  const FONT_MAX_PX        = 13;

  // ── CSS: em-based so everything scales with JS-driven base font-size ──────
  const CSS = `
    .vc-st-frame {
      position: absolute;
      inset: 0;
      background: linear-gradient(160deg, #1535cc 0%, #0c22a0 35%, #081870 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    .vc-st-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.05) 3px, rgba(0,0,0,0.05) 4px);
      pointer-events: none;
      z-index: 10;
    }
    .vc-st-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1840d8 50%, #0d2aaa 100%);
      border-bottom: 0.18em solid #4a70ff;
      padding: 0 0.9em;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      height: 2.6em;
    }
    .vc-st-header-left {
      display: flex;
      align-items: center;
      gap: 0.3em;
    }
    .vc-st-icon { font-size: 1.6em; line-height: 1; }
    .vc-st-brand {
      font-size: 1.25em;
      font-weight: 400;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-st-brand strong { font-weight: 900; }
    .vc-st-header-right {
      font-size: 1.2em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-st-body {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 0.46fr;
      gap: 0.35em;
      padding: 0.45em 0.55em 0.25em;
      min-height: 0;
    }
    .vc-st-main {
      display: flex;
      flex-direction: column;
      background: rgba(8, 28, 120, 0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.2em 1em rgba(0,0,0,0.6);
    }
    .vc-st-report-label {
      padding: 0.22em 0.5em 0.08em;
      font-size: 0.82em;
      font-style: italic;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-st-headline-bar {
      padding: 0.22em 0.5em;
      background: linear-gradient(90deg, #006622 0%, #008833 55%, #005518 100%);
    }
    .vc-st-headline-bar.warn {
      background: linear-gradient(90deg, #886600 0%, #aa8800 55%, #775500 100%);
    }
    .vc-st-headline-bar.error {
      background: linear-gradient(90deg, #8b0000 0%, #b20000 55%, #800000 100%);
    }
    .vc-st-headline-text {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: #fff;
      line-height: 1.15;
    }
    .vc-st-main-content {
      flex: 1;
      background: rgba(6, 18, 80, 0.5);
      overflow: hidden;
      min-height: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.3em;
      padding: 0.4em 0.7em;
    }
    .vc-st-big-label {
      font-size: 0.72em;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #c8d8ff;
    }
    .vc-st-big-uptime {
      font-size: 2.8em;
      font-weight: 900;
      line-height: 1;
      color: #fff;
      letter-spacing: 0.02em;
    }
    .vc-st-meta-row {
      display: flex;
      gap: 1.4em;
      flex-wrap: wrap;
      justify-content: center;
      margin-top: 0.2em;
    }
    .vc-st-meta-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.08em;
    }
    .vc-st-meta-value {
      font-size: 0.9em;
      font-weight: 900;
      color: #fff;
    }
    .vc-st-meta-key {
      font-size: 0.62em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #90a8d8;
    }
    .vc-st-summary-box {
      background: rgba(6, 20, 90, 0.85);
      border-top: 0.12em solid #3a5ccc;
      padding: 0.3em 0.55em;
    }
    .vc-st-summary-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.15em 0.9em;
    }
    .vc-st-summary-entry {
      font-size: 0.68em;
      font-weight: 400;
      color: #e8eeff;
      line-height: 1.5;
    }
    .vc-st-summary-entry strong {
      font-weight: 700;
      color: #ffd700;
    }
    .vc-st-sidebar {
      display: flex;
      flex-direction: column;
      gap: 0.25em;
    }
    .vc-st-item {
      flex: 1;
      display: flex;
      background: rgba(8, 28, 120, 0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.12em 0.5em rgba(0,0,0,0.5);
      min-height: 0;
    }
    .vc-st-item-dot-panel {
      width: 2.2em;
      flex-shrink: 0;
      background: rgba(4, 12, 60, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .vc-st-item-dot {
      width: 0.72em;
      height: 0.72em;
      border-radius: 50%;
      background: #22cc44;
      box-shadow: 0 0 0.35em #22cc4466;
    }
    .vc-st-item-dot.warn  { background: #ffaa00; box-shadow: 0 0 0.35em #ffaa0066; }
    .vc-st-item-dot.error { background: #ee2222; box-shadow: 0 0 0.35em #ee222266; }
    .vc-st-item-text {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 0.2em 0.4em;
      min-width: 0;
    }
    .vc-st-item-label {
      font-size: 0.62em;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #c8d8ff;
      line-height: 1.2;
    }
    .vc-st-item-value {
      font-size: 0.76em;
      font-weight: 700;
      color: #fff;
      line-height: 1.3;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .vc-st-ticker-bar {
      background: #04091f;
      border-top: 0.12em solid #3a5ccc;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.65em;
    }
    .vc-st-ticker-label {
      background: #0a0e2a;
      color: #ffd700;
      font-size: 0.72em;
      font-weight: 900;
      font-style: italic;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      padding: 0 0.6em;
      white-space: nowrap;
      height: 100%;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      border-right: 0.12em solid #3a5ccc;
    }
    .vc-st-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-st-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.7em;
      font-weight: 700;
      color: #ffd700;
      /* duration overridden in JS for constant px/s speed; 300s fallback keeps it readable if JS fails */
      animation: vc-st-scroll 300s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-st-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
    .vc-st-no-data {
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 1;
      font-size: 0.9em;
      color: #90a8f0;
      letter-spacing: 0.1em;
    }
  `;

  function ensureStyles() {
    if (!document.getElementById(STYLE_ID)) {
      const s = document.createElement('style');
      s.id = STYLE_ID;
      s.textContent = CSS;
      document.head.appendChild(s);
    }
  }

  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function headlineText(state) {
    if (state === 'error') return 'System Warning \u2014 Attention Required';
    if (state === 'warn')  return 'System Advisory \u2014 Minor Issues Detected';
    return 'All Systems Operational';
  }

  function formatLocalTime(isoStr) {
    try {
      return new Date(isoStr).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' });
    } catch (e) { return isoStr || ''; }
  }

  function applyTickerSpeed(frame) {
    const track = frame.querySelector('.vc-st-ticker-track');
    if (!track) return;
    setTimeout(function () {
      const w = track.offsetWidth;
      if (w > 0) {
        track.style.animationDuration = (w / TICKER_PX_PER_SEC).toFixed(1) + 's';
      }
    }, 0);
  }

  function render(data, root) {
    ensureStyles();
    root.querySelectorAll('.vc-overlay').forEach(function (e) { e.remove(); });
    root.classList.remove('hidden');

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-st-frame';

    // Scale font-size proportionally to container width
    const fw = root.offsetWidth || 960;
    frame.style.fontSize = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX)) + 'px';

    const items        = Array.isArray(data && data.items) ? data.items : [];
    const ticks        = Array.isArray(data && data.ticker) ? data.ticker : [];
    const overallState = (data && data.overall_state) || 'good';
    const diskUsedPct  = (data && typeof data.disk_used_pct === 'number') ? data.disk_used_pct : 0;

    function findItem(label) {
      return items.find(function (it) { return it.label === label; }) || null;
    }
    const uptime   = findItem('Uptime');
    const version  = findItem('Version');
    const channels = findItem('Channels');
    const platform = findItem('Platform');
    const python   = findItem('Python');
    const load     = findItem('Load Avg');
    const disk     = findItem('Disk');

    // Ticker
    const tickText = ticks.length
      ? ticks.join(' \u2022 ') + ' \u2022 '
      : 'System Status: Running \u2022 ';
    const tickRepeat = Array(TICKER_REPEAT_COUNT).fill(tickText).join('');

    // Sidebar: all items except App Status (overall state shown in headline bar)
    const sideRows = items
      .filter(function (it) { return it.label !== 'App Status'; })
      .map(function (it) {
        const state = it.state || 'good';
        return '<div class="vc-st-item">' +
          '<div class="vc-st-item-dot-panel">' +
            '<div class="vc-st-item-dot ' + esc(state === 'good' ? '' : state) + '"></div>' +
          '</div>' +
          '<div class="vc-st-item-text">' +
            '<div class="vc-st-item-label">' + esc(it.label) + '</div>' +
            '<div class="vc-st-item-value">' + esc(it.value) + '</div>' +
          '</div>' +
        '</div>';
      }).join('');

    // Summary strip entries
    const summaryParts = [];
    if (platform) summaryParts.push('<span class="vc-st-summary-entry"><strong>Platform:</strong> ' + esc(platform.value) + '</span>');
    if (python)   summaryParts.push('<span class="vc-st-summary-entry"><strong>Python:</strong> '   + esc(python.value)   + '</span>');
    if (load)     summaryParts.push('<span class="vc-st-summary-entry"><strong>Load:</strong> '     + esc(load.value)     + '</span>');
    if (disk)     summaryParts.push('<span class="vc-st-summary-entry"><strong>Disk:</strong> '     + esc(disk.value) + ' (' + diskUsedPct + '% used)</span>');
    if (data && data.updated) summaryParts.push('<span class="vc-st-summary-entry"><strong>Updated:</strong> ' + formatLocalTime(data.updated) + '</span>');

    // Meta row items (version / channels / disk %)
    const metaItems = [];
    if (version)  metaItems.push('<div class="vc-st-meta-item"><div class="vc-st-meta-value">' + esc(version.value)  + '</div><div class="vc-st-meta-key">Version</div></div>');
    if (channels) metaItems.push('<div class="vc-st-meta-item"><div class="vc-st-meta-value">' + esc(channels.value) + '</div><div class="vc-st-meta-key">Channels</div></div>');
    metaItems.push('<div class="vc-st-meta-item"><div class="vc-st-meta-value">' + diskUsedPct + '%</div><div class="vc-st-meta-key">Disk Used</div></div>');

    const headlineBarClass = 'vc-st-headline-bar' + (overallState === 'good' ? '' : ' ' + esc(overallState));

    frame.innerHTML =
      '<div class="vc-st-header">' +
        '<div class="vc-st-header-left">' +
          '<span class="vc-st-icon">\uD83D\uDDA5\uFE0F</span>' +
          '<span class="vc-st-brand">RetroIPTV <strong>Status</strong></span>' +
        '</div>' +
        '<div class="vc-st-header-right">System Health</div>' +
      '</div>' +
      '<div class="vc-st-body">' +
        '<div class="vc-st-main">' +
          '<div class="vc-st-report-label">Status Report</div>' +
          '<div class="' + headlineBarClass + '">' +
            '<div class="vc-st-headline-text">' + esc(headlineText(overallState)) + '</div>' +
          '</div>' +
          '<div class="vc-st-main-content">' +
            '<div class="vc-st-big-label">Server Uptime</div>' +
            '<div class="vc-st-big-uptime">' + esc(uptime ? uptime.value : '--') + '</div>' +
            '<div class="vc-st-meta-row">' + metaItems.join('') + '</div>' +
          '</div>' +
          (summaryParts.length ? '<div class="vc-st-summary-box"><div class="vc-st-summary-row">' + summaryParts.join('') + '</div></div>' : '') +
        '</div>' +
        '<div class="vc-st-sidebar">' + (sideRows || '<div class="vc-st-no-data">No data.</div>') + '</div>' +
      '</div>' +
      '<div class="vc-st-ticker-bar">' +
        '<div class="vc-st-ticker-label">System Status:</div>' +
        '<div class="vc-st-ticker-scroll">' +
          '<span class="vc-st-ticker-track">' + tickRepeat + '</span>' +
        '</div>' +
      '</div>';

    overlay.appendChild(frame);
    root.appendChild(overlay);

    applyTickerSpeed(frame);
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/virtual/status');
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render: render });
})();

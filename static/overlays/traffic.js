/* Traffic overlay renderer (v1)
 * Renders the retro TV traffic broadcast layout into the virtual channel
 * overlay, matching the /traffic standalone page design.
 * Endpoint: GET /api/traffic
 *
 * Wall-clock aligned refresh: the server returns ms_until_next so the
 * overlay advances in sync with the cache slot — all viewers see the same
 * snapshot and the content updates at a consistent wall-clock boundary.
 */
(function () {
  'use strict';
  const TYPE           = 'traffic';
  const STYLE_ID       = 'vc-traffic-overlay-styles-v1';
  // Must match _TRAFFIC_CACHE_TTL in app.py
  const REFRESH_INTERVAL_MS = 2 * 60 * 1000;

  const CSS = `
    .vc-tf-frame {
      position: absolute;
      inset: 0;
      /* font-size set dynamically in JS proportional to container width */
      background: linear-gradient(160deg, #0f2ab0 0%, #0a1a80 40%, #081060 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    .vc-tf-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.06) 3px, rgba(0,0,0,0.06) 4px);
      pointer-events: none;
      z-index: 10;
    }
    .vc-tf-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1640d4 50%, #0d2aaa 100%);
      border-bottom: 0.18em solid #4a70ff;
      padding: 0.28em 0.8em;
      display: flex;
      align-items: center;
      gap: 0.5em;
      flex-shrink: 0;
    }
    .vc-tf-header-title {
      font-size: 1.35em;
      font-weight: 900;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.25em;
    }
    .vc-tf-header-subtitle {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #fff;
      margin-left: auto;
    }
    .vc-tf-updated {
      font-size: 0.75em;
      font-weight: 700;
      color: #ffd700;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.15em 0.8em 0;
      flex-shrink: 0;
    }
    .vc-tf-body {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 2.2fr;
      gap: 0.3em;
      padding: 0.3em 0.45em 0.2em;
      min-height: 0;
    }
    .vc-tf-box {
      background: rgba(10,40,170,0.75);
      border: 1px solid #3058d8;
      border-radius: 3px;
      padding: 0.28em 0.45em;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 6px rgba(0,0,0,0.4);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .vc-tf-box-title {
      font-size: 0.76em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #ffd700;
      border-bottom: 1px solid #3058d8;
      padding-bottom: 0.2em;
      margin-bottom: 0.25em;
      white-space: nowrap;
    }
    .vc-tf-summary-count {
      font-size: 2.8em;
      font-weight: 900;
      text-align: center;
      line-height: 1;
      color: #ffd700;
      margin: 0.1em 0 0.05em;
    }
    .vc-tf-summary-label {
      font-size: 0.72em;
      font-weight: 700;
      text-align: center;
      color: #c8d8ff;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-bottom: 0.4em;
    }
    .vc-tf-congestion-label {
      font-size: 0.68em;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #c8d8ff;
      margin-bottom: 0.15em;
    }
    .vc-tf-bar-track {
      background: rgba(0,0,20,0.5);
      border: 1px solid #3058d8;
      border-radius: 2px;
      height: 0.7em;
      overflow: hidden;
      margin-bottom: 0.2em;
    }
    .vc-tf-bar-fill {
      height: 100%;
      border-radius: 2px;
    }
    .vc-tf-bar-fill[data-level="Low"]      { width: 28%; background: #22cc44; }
    .vc-tf-bar-fill[data-level="Moderate"] { width: 62%; background: #ffaa00; }
    .vc-tf-bar-fill[data-level="Heavy"]    { width: 95%; background: #ee2222; }
    .vc-tf-congestion-value {
      font-size: 1.4em;
      font-weight: 900;
      text-align: center;
      margin: 0.1em 0;
    }
    .vc-tf-congestion-value[data-level="Low"]      { color: #22cc44; }
    .vc-tf-congestion-value[data-level="Moderate"] { color: #ffaa00; }
    .vc-tf-congestion-value[data-level="Heavy"]    { color: #ee2222; }
    .vc-tf-legend {
      margin-top: auto;
      font-size: 0.65em;
      line-height: 1.6;
      color: #d0e0ff;
    }
    .vc-tf-legend-item { display: flex; align-items: center; gap: 0.35em; }
    .vc-tf-legend-dot  { width: 0.6em; height: 0.6em; border-radius: 50%; flex-shrink: 0; }
    .vc-tf-incident-row {
      display: flex;
      align-items: flex-start;
      gap: 0.3em;
      padding: 0.18em 0;
      border-bottom: 1px solid rgba(48,88,216,0.4);
    }
    .vc-tf-incident-row:last-child { border-bottom: none; }
    .vc-tf-dot {
      width: 0.5em;
      height: 0.5em;
      border-radius: 50%;
      flex-shrink: 0;
      margin-top: 0.22em;
    }
    .vc-tf-dot[data-severity="Major"]    { background: #ee2222; }
    .vc-tf-dot[data-severity="Moderate"] { background: #ffaa00; }
    .vc-tf-dot[data-severity="Minor"]    { background: #22cc44; }
    .vc-tf-dot[data-severity="Unknown"]  { background: #8898c0; }
    .vc-tf-inc-info { flex: 1; min-width: 0; }
    .vc-tf-inc-title {
      font-size: 0.78em;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .vc-tf-inc-detail {
      font-size: 0.65em;
      color: #c8d8ff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .vc-tf-inc-dist {
      font-size: 0.65em;
      font-weight: 700;
      color: #ffd700;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .vc-tf-no-incidents {
      font-size: 0.76em;
      color: #90a8f0;
      padding: 0.3em 0;
    }
    .vc-tf-ticker-bar {
      background: #0a0e2a;
      border-top: 1px solid #4a70ff;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.7em;
    }
    .vc-tf-ticker-label {
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
    .vc-tf-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-tf-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.72em;
      font-weight: 700;
      color: #ffd700;
      animation: vc-tf-scroll 36s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-tf-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
  `;

  const FONT_SCALE_DIVISOR = 48;
  const FONT_MIN_PX        = 9;
  const FONT_MAX_PX        = 13;

  function ensureStyles() {
    if (!document.getElementById(STYLE_ID)) {
      const s = document.createElement('style');
      s.id = STYLE_ID;
      s.textContent = CSS;
      document.head.appendChild(s);
    }
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function formatLocalTime(isoStr) {
    try {
      return new Date(isoStr).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch (e) { return isoStr; }
  }

  function render(data, root) {
    ensureStyles();
    root.querySelectorAll('.vc-overlay').forEach(function (e) { e.remove(); });
    root.classList.remove('hidden');

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-tf-frame';

    const fw         = root.offsetWidth || 960;
    const baseFontPx = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX));
    frame.style.fontSize = baseFontPx + 'px';

    const summary   = (data && data.summary)   || {};
    const incidents = Array.isArray(data && data.incidents) ? data.incidents : [];
    const level     = summary.congestion_level || 'Low';
    const count     = summary.incident_count   || 0;

    // Ticker text
    const tickParts = incidents.length
      ? incidents.map(function (i) {
          return [esc(i.title), esc(i.road)].filter(Boolean).join(' \u2014 ');
        })
      : ['No incidents reported in your area'];
    const tickText   = tickParts.join(' \u2022 ') + ' \u2022 ';
    const tickRepeat = tickText.repeat(3);

    // Incident rows
    const incRows = incidents.length
      ? incidents.map(function (inc) {
          const dist   = inc.distance_miles != null ? esc(inc.distance_miles) + ' mi' : '';
          const detail = [esc(inc.road), esc(inc.direction)].filter(Boolean).join(' \u00b7 ');
          return (
            '<div class="vc-tf-incident-row">' +
              '<div class="vc-tf-dot" data-severity="' + esc(inc.severity) + '"></div>' +
              '<div class="vc-tf-inc-info">' +
                '<div class="vc-tf-inc-title">' + esc(inc.title) + '</div>' +
                (detail ? '<div class="vc-tf-inc-detail">' + detail + '</div>' : '') +
              '</div>' +
              (dist ? '<div class="vc-tf-inc-dist">' + dist + '</div>' : '') +
            '</div>'
          );
        }).join('')
      : '<div class="vc-tf-no-incidents">No incidents reported nearby.</div>';

    frame.innerHTML =
      '<div class="vc-tf-header">' +
        '<div class="vc-tf-header-title">' +
          '<span>RetroIPTV</span>' +
          '<span>\uD83D\uDE97</span>' +
          '<span>Traffic</span>' +
        '</div>' +
        '<div class="vc-tf-header-subtitle">Local Conditions</div>' +
      '</div>' +
      '<div class="vc-tf-updated">' +
        '<span>' + esc((data && data.location) || '') + '</span>' +
        '<span>UPDATED: ' + ((data && data.updated) ? formatLocalTime(data.updated) : '') + '</span>' +
      '</div>' +
      '<div class="vc-tf-body">' +
        '<div class="vc-tf-box">' +
          '<div class="vc-tf-box-title">Congestion</div>' +
          '<div class="vc-tf-summary-count">' + count + '</div>' +
          '<div class="vc-tf-summary-label">Incident' + (count !== 1 ? 's' : '') + ' Reported</div>' +
          '<div class="vc-tf-congestion-label">Traffic Level</div>' +
          '<div class="vc-tf-bar-track"><div class="vc-tf-bar-fill" data-level="' + esc(level) + '"></div></div>' +
          '<div class="vc-tf-congestion-value" data-level="' + esc(level) + '">' + esc(level) + '</div>' +
          '<div class="vc-tf-legend">' +
            '<div class="vc-tf-legend-item"><div class="vc-tf-legend-dot" style="background:#22cc44"></div>Low</div>' +
            '<div class="vc-tf-legend-item"><div class="vc-tf-legend-dot" style="background:#ffaa00"></div>Moderate</div>' +
            '<div class="vc-tf-legend-item"><div class="vc-tf-legend-dot" style="background:#ee2222"></div>Heavy</div>' +
          '</div>' +
        '</div>' +
        '<div class="vc-tf-box">' +
          '<div class="vc-tf-box-title">Live Traffic Incidents</div>' +
          incRows +
        '</div>' +
      '</div>' +
      '<div class="vc-tf-ticker-bar">' +
        '<div class="vc-tf-ticker-label">Traffic Alert:</div>' +
        '<div class="vc-tf-ticker-scroll">' +
          '<span class="vc-tf-ticker-track">' + tickRepeat + '</span>' +
        '</div>' +
      '</div>';

    overlay.appendChild(frame);
    root.appendChild(overlay);
  }

  // ── Wall-clock aligned fetch / scheduling ─────────────────────────────────
  // The server returns ms_until_next (time until the next cache-slot boundary)
  // so all clients refresh in sync regardless of tune-in time.
  let _cycleTimer = null;

  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
  }

  async function fetchData() {
    const data = await window.OverlayEngine.fetchJson('/api/traffic');
    // Schedule next refresh at the exact wall-clock boundary
    if (_cycleTimer === null) {
      const msUntilNext = (data.ms_until_next > 0) ? data.ms_until_next : REFRESH_INTERVAL_MS;
      _cycleTimer = setTimeout(advanceAndTick, msUntilNext);
    }
    return data;
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render: render });
})();

/* Updates & Announcements overlay renderer
 * Renders the retro TV updates broadcast layout into the virtual channel overlay,
 * matching the /updates standalone page design.
 * Endpoint: GET /api/virtual/updates
 */
(function () {
  'use strict';
  const TYPE    = 'updates';
  const STYLE_ID = 'vc-updates-overlay-styles-v1';

  const TICKER_PX_PER_SEC  = 40;
  const TICKER_REPEAT_COUNT = 3;
  const SUMMARY_MAX        = 1000;

  // Font-size scaling: base px = container_width / FONT_SCALE_DIVISOR, clamped
  const FONT_SCALE_DIVISOR = 52;
  const FONT_MIN_PX        = 9;
  const FONT_MAX_PX        = 13;

  // ── CSS: em-based so everything scales with JS-driven base font-size ───────
  const CSS = `
    .vc-up-frame {
      position: absolute;
      inset: 0;
      /* font-size set dynamically in JS proportional to container width */
      background: linear-gradient(160deg, #1535cc 0%, #0c22a0 35%, #081870 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    .vc-up-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.05) 3px, rgba(0,0,0,0.05) 4px);
      pointer-events: none;
      z-index: 10;
    }
    .vc-up-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1840d8 50%, #0d2aaa 100%);
      border-bottom: 0.18em solid #4a70ff;
      padding: 0 0.9em;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      height: 2.6em;
    }
    .vc-up-header-left {
      display: flex;
      align-items: center;
      gap: 0.3em;
    }
    .vc-up-icon { font-size: 1.6em; line-height: 1; }
    .vc-up-brand {
      font-size: 1.25em;
      font-weight: 400;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-up-brand strong { font-weight: 900; }
    .vc-up-header-right {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.05em;
    }
    .vc-up-header-title {
      font-size: 1.2em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-up-header-updated {
      font-size: 0.7em;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-up-body {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 0.46fr;
      gap: 0.35em;
      padding: 0.45em 0.55em 0.25em;
      min-height: 0;
    }
    .vc-up-main {
      display: flex;
      flex-direction: column;
      background: rgba(8, 28, 120, 0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.2em 1em rgba(0,0,0,0.6);
    }
    .vc-up-report-label {
      padding: 0.22em 0.5em 0.08em;
      font-size: 0.82em;
      font-style: italic;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-up-headline-bar {
      padding: 0.22em 0.5em;
      background: linear-gradient(90deg, #003399 0%, #0044cc 55%, #002277 100%);
    }
    .vc-up-headline-bar.beta {
      background: linear-gradient(90deg, #886600 0%, #aa8800 55%, #775500 100%);
    }
    .vc-up-headline-text {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: #fff;
      line-height: 1.15;
    }
    .vc-up-main-content {
      flex: 1;
      background: rgba(8, 18, 80, 0.5);
      overflow: hidden;
      min-height: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.3em;
      padding: 0.4em 0.7em;
    }
    .vc-up-version-label {
      font-size: 0.72em;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-up-version-number {
      font-size: 2.8em;
      font-weight: 900;
      line-height: 1;
      color: #fff;
      letter-spacing: 0.02em;
    }
    .vc-up-beta-badge {
      display: inline-block;
      background: #ffd700;
      color: #0a0e2a;
      font-size: 0.6em;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      padding: 0.15em 0.45em;
      border-radius: 2px;
      vertical-align: middle;
    }
    .vc-up-meta-row {
      display: flex;
      gap: 1.4em;
      flex-wrap: wrap;
      justify-content: center;
      margin-top: 0.2em;
    }
    .vc-up-meta-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.08em;
    }
    .vc-up-meta-value {
      font-size: 0.9em;
      font-weight: 900;
      color: #fff;
    }
    .vc-up-meta-key {
      font-size: 0.62em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-up-summary-box {
      background: rgba(6, 20, 90, 0.85);
      border-top: 0.12em solid #3a5ccc;
      padding: 0.3em 0.55em;
    }
    .vc-up-summary-text {
      font-size: 0.68em;
      font-weight: 400;
      line-height: 1.45;
      color: #e8eeff;
    }
    .vc-up-sidebar {
      display: flex;
      flex-direction: column;
      gap: 0.25em;
    }
    .vc-up-notes-panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      background: rgba(8, 28, 120, 0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.12em 0.5em rgba(0,0,0,0.5);
      min-height: 0;
    }
    .vc-up-notes-label {
      background: linear-gradient(90deg, #0d2aaa 0%, #1840d8 50%, #0d2aaa 100%);
      padding: 0.22em 0.5em;
      font-size: 0.82em;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: #ffd700;
      flex-shrink: 0;
    }
    .vc-up-notes-text {
      flex: 1;
      padding: 0.35em 0.5em;
      font-size: 0.68em;
      font-weight: 400;
      line-height: 1.45;
      color: #e8eeff;
      overflow-y: auto;
    }
    .vc-up-notes-empty {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.72em;
      color: #4a70ff;
      padding: 0.4em;
    }
    .vc-up-item-dot-panel {
      width: 2.2em;
      flex-shrink: 0;
      background: rgba(4, 10, 60, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .vc-up-item-dot {
      width: 0.72em;
      height: 0.72em;
      border-radius: 50%;
      background: #22cc44;
      box-shadow: 0 0 0.35em #22cc4466;
    }
    .vc-up-item-dot.beta { background: #ffaa00; box-shadow: 0 0 0.35em #ffaa0066; }
    .vc-up-item-text {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 0.2em 0.4em;
      min-width: 0;
    }
    .vc-up-item-label {
      font-size: 0.62em;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #ffd700;
      line-height: 1.2;
    }
    .vc-up-item-value {
      font-size: 0.76em;
      font-weight: 700;
      color: #fff;
      line-height: 1.3;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .vc-up-ticker-bar {
      background: #04091f;
      border-top: 0.12em solid #3a5ccc;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.65em;
    }
    .vc-up-ticker-label {
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
    .vc-up-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-up-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.7em;
      font-weight: 700;
      color: #ffd700;
      animation: vc-up-scroll 300s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-up-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
    .vc-up-no-data {
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 1;
      font-size: 0.9em;
      color: #ffd700;
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

  function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      return new Date(isoStr).toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (e) { return ''; }
  }

  function formatLocalTime(isoStr) {
    if (!isoStr) return '';
    try {
      return new Date(isoStr).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch (e) { return isoStr || ''; }
  }

  function trimBody(body) {
    if (!body) return '';
    const plain = String(body)
      .replace(/#{1,6}\s+/g, '')
      .replace(/^\s*[-*+]\s+/gm, '')
      .replace(/\r?\n+/g, ' ')
      .trim();
    return plain.length > SUMMARY_MAX ? plain.substring(0, SUMMARY_MAX) + '\u2026' : plain;
  }

  function applyTickerSpeed(frame) {
    const track = frame.querySelector('.vc-up-ticker-track');
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
    frame.className = 'vc-up-frame';

    // Scale font-size proportionally to container width
    const fw = root.offsetWidth || 960;
    frame.style.fontSize = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX)) + 'px';

    const releases = Array.isArray(data && data.releases) ? data.releases : [];
    const latest   = (data && data.latest) || (releases.length ? releases[0] : null);
    const ticker   = Array.isArray(data && data.ticker) ? data.ticker : [];

    // Ticker text
    const tickText = ticker.length
      ? ticker.join(' \u2022 ') + ' \u2022 '
      : 'Current version: ' + esc((data && data.app_version) || '') + ' \u2022 ';
    const tickRepeat = Array(TICKER_REPEAT_COUNT).fill(tickText).join('');

    // Right sidebar: release notes for the latest release
    const summary     = latest ? trimBody(latest.body) : '';
    const releaseDate = latest ? formatDate(latest.published) : '';
    const releaseTag  = latest ? (latest.tag || latest.name) : ((data && data.app_version) || '');

    const sidebarHtml = summary
      ? '<div class="vc-up-notes-panel">' +
          '<div class="vc-up-notes-label">Release Notes</div>' +
          '<div class="vc-up-notes-text">' + esc(summary) + '</div>' +
        '</div>'
      : '<div class="vc-up-notes-panel">' +
          '<div class="vc-up-notes-label">Release Notes</div>' +
          '<div class="vc-up-notes-empty">No notes available.</div>' +
        '</div>';

    // Main panel
    const isBeta        = latest && latest.prerelease;
    const headlineClass = 'vc-up-headline-bar' + (isBeta ? ' beta' : '');
    const headlineText  = isBeta
      ? '\u26A0\uFE0F Beta Release \u2014 Testing in Progress'
      : '\u2714\uFE0F Latest Release Available';

    const metaItems = [];
    if (releaseDate) {
      metaItems.push(
        '<div class="vc-up-meta-item">' +
          '<div class="vc-up-meta-value">' + esc(releaseDate) + '</div>' +
          '<div class="vc-up-meta-key">Released</div>' +
        '</div>'
      );
    }
    if (releases.length > 0) {
      metaItems.push(
        '<div class="vc-up-meta-item">' +
          '<div class="vc-up-meta-value">' + releases.length + '</div>' +
          '<div class="vc-up-meta-key">Releases</div>' +
        '</div>'
      );
    }

    const betaBadge = isBeta ? ' <span class="vc-up-beta-badge">Beta</span>' : '';

    frame.innerHTML =
      '<div class="vc-up-header">' +
        '<div class="vc-up-header-left">' +
          '<span class="vc-up-icon">\uD83D\uDE80</span>' +
          '<span class="vc-up-brand">RetroIPTV <strong>Updates</strong></span>' +
        '</div>' +
        '<div class="vc-up-header-right">' +
          '<div class="vc-up-header-title">What\'s New</div>' +
          '<div class="vc-up-header-updated">Updated: ' + formatLocalTime(data && data.updated) + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="vc-up-body">' +
        '<div class="vc-up-main">' +
          '<div class="vc-up-report-label">Latest Release</div>' +
          '<div class="' + esc(headlineClass) + '">' +
            '<div class="vc-up-headline-text">' + esc(headlineText) + '</div>' +
          '</div>' +
          '<div class="vc-up-main-content">' +
            '<div class="vc-up-version-label">Latest Version' + betaBadge + '</div>' +
            '<div class="vc-up-version-number">' + esc(releaseTag) + '</div>' +
            (metaItems.length ? '<div class="vc-up-meta-row">' + metaItems.join('') + '</div>' : '') +
          '</div>' +
        '</div>' +
        '<div class="vc-up-sidebar">' + sidebarHtml + '</div>' +
      '</div>' +
      '<div class="vc-up-ticker-bar">' +
        '<div class="vc-up-ticker-label">Version History:</div>' +
        '<div class="vc-up-ticker-scroll">' +
          '<span class="vc-up-ticker-track">' + tickRepeat + '</span>' +
        '</div>' +
      '</div>';

    overlay.appendChild(frame);
    root.appendChild(overlay);

    applyTickerSpeed(frame);
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/virtual/updates');
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render: render });
})();

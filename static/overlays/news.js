/* News overlay renderer (v2)
 * Renders the full retro TV broadcast news layout into the virtual channel
 * overlay, matching the /news standalone page design.
 * Ticker speed is constant (pixels/sec) so it is always readable regardless
 * of how many headlines are loaded.
 * Endpoint: GET /api/news
 */
(function () {
  'use strict';
  const TYPE    = 'news';
  const STYLE_ID = 'vc-news-overlay-styles-v2';

  const TICKER_PX_PER_SEC  = 40;   // constant scroll speed in px/s (~50 wpm, TV-ticker pace)
  const TICKER_REPEAT_COUNT = 3;   // how many times to repeat ticker text
  const SUMMARY_MAX        = 220;  // max chars for top-story summary
  const STATUS_POLL_MS     = 3000; // how often to poll /api/news/status for forced advances

  const FALLBACK_IMG = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 90'%3E%3Crect width='160' height='90' fill='%230a1a70'/%3E%3Ctext x='80' y='50' text-anchor='middle' font-family='Arial' font-size='12' fill='%234060cc'%3ENo Image%3C%2Ftext%3E%3C%2Fsvg%3E";

  // ── CSS: em-based so everything scales with the JS-driven base font-size ──
  const CSS = `
    .vc-news-frame {
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
    .vc-news-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.05) 3px, rgba(0,0,0,0.05) 4px);
      pointer-events: none;
      z-index: 10;
    }
    .vc-news-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1840d8 50%, #0d2aaa 100%);
      border-bottom: 0.18em solid #4a70ff;
      padding: 0 0.9em;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      height: 2.6em;
    }
    .vc-news-header-left {
      display: flex;
      align-items: center;
      gap: 0.3em;
    }
    .vc-news-globe { font-size: 1.6em; line-height: 1; }
    .vc-news-brand {
      font-size: 1.25em;
      font-weight: 400;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-news-brand strong { font-weight: 900; }
    .vc-news-header-right {
      font-size: 1.2em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-news-body {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 0.46fr;
      gap: 0.35em;
      padding: 0.45em 0.55em 0.25em;
      min-height: 0;
    }
    .vc-news-main {
      display: flex;
      flex-direction: column;
      background: rgba(8, 28, 120, 0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.2em 1em rgba(0,0,0,0.6);
    }
    .vc-news-top-label {
      background: transparent;
      padding: 0.22em 0.5em 0.08em;
      font-size: 0.82em;
      font-style: italic;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-news-headline-bar {
      background: linear-gradient(90deg, #8b0000 0%, #b20000 55%, #800000 100%);
      padding: 0.22em 0.5em;
    }
    .vc-news-headline-text {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: #fff;
      line-height: 1.15;
    }
    .vc-news-main-image {
      flex: 1;
      background: #0a1a5a;
      overflow: hidden;
      min-height: 0;
    }
    .vc-news-main-image img {
      width: 100%; height: 100%; object-fit: cover; display: block;
    }
    .vc-news-summary-box {
      background: rgba(6, 20, 90, 0.85);
      border-top: 0.12em solid #3a5ccc;
      padding: 0.35em 0.55em;
    }
    .vc-news-summary-text {
      font-size: 0.72em;
      font-weight: 400;
      line-height: 1.45;
      color: #e8eeff;
    }
    .vc-news-sidebar {
      display: flex;
      flex-direction: column;
      gap: 0.25em;
    }
    .vc-news-item {
      flex: 1;
      display: flex;
      background: rgba(8, 28, 120, 0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.12em 0.5em rgba(0,0,0,0.5);
      min-height: 0;
    }
    .vc-news-item-img {
      width: 5.2em;
      flex-shrink: 0;
      background: #071460;
      overflow: hidden;
    }
    .vc-news-item-img img {
      width: 100%; height: 100%; object-fit: cover; display: block;
    }
    .vc-news-item-text {
      flex: 1;
      display: flex;
      align-items: center;
      padding: 0.22em 0.4em;
    }
    .vc-news-item-title {
      font-size: 0.72em;
      font-weight: 700;
      line-height: 1.3;
      color: #fff;
    }
    .vc-news-ticker-bar {
      background: #04091f;
      border-top: 0.12em solid #3a5ccc;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.65em;
    }
    .vc-news-ticker-label {
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
    .vc-news-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-news-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.7em;
      font-weight: 700;
      color: #ffd700;
      /* duration overridden in JS for constant px/s speed; 300s fallback keeps it readable if JS fails */
      animation: vc-news-scroll 300s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-news-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
    .vc-news-item-placeholder { opacity: 0.25; }
    .vc-news-no-data {
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 1;
      font-size: 0.9em;
      color: #90a8f0;
      letter-spacing: 0.1em;
    }
  `;

  // Font-size scaling: base px = container_width / FONT_SCALE_DIVISOR, clamped
  const FONT_SCALE_DIVISOR = 52;
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

  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function imgTag(url, alt) {
    const src = (url && url.trim()) ? esc(url) : FALLBACK_IMG;
    return `<img src="${src}" alt="${esc(alt)}" onerror="this.src='${FALLBACK_IMG}'">`;
  }

  function applyTickerSpeed(frame) {
    const track = frame.querySelector('.vc-news-ticker-track');
    if (!track) return;
    // Use setTimeout so the browser has fully computed layout for the new innerHTML
    setTimeout(function () {
      const w = track.offsetWidth;
      if (w > 0) {
        const dur = (w / TICKER_PX_PER_SEC).toFixed(1);
        track.style.animationDuration = dur + 's';
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
    frame.className = 'vc-news-frame';

    // Scale font-size proportionally to container width
    const fw = root.offsetWidth || 960;
    const baseFontPx = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX));
    frame.style.fontSize = baseFontPx + 'px';

    const headlines = Array.isArray(data && data.headlines) ? data.headlines : [];
    const top       = headlines[0] || null;
    const sideItems = headlines.slice(1, 6);
    const tickItems = headlines.slice(0, 10);

    // Ticker
    const tickText = tickItems.length
      ? tickItems.map(function (h) { return esc(h.title); }).join(' \u2022 ') + ' \u2022 '
      : 'No headlines available \u2022 ';
    const tickRepeat = Array(TICKER_REPEAT_COUNT).fill(tickText).join('');

    // Sidebar (pad to 5)
    const sideRows = [];
    for (let i = 0; i < 5; i++) {
      const h = sideItems[i];
      if (h) {
        sideRows.push(
          '<div class="vc-news-item">' +
            '<div class="vc-news-item-img">' + imgTag(h.image, h.title) + '</div>' +
            '<div class="vc-news-item-text"><div class="vc-news-item-title">' + esc(h.title) + '</div></div>' +
          '</div>'
        );
      } else {
        sideRows.push('<div class="vc-news-item vc-news-item-placeholder"></div>');
      }
    }

    // Top story
    let mainHtml;
    if (top) {
      const raw = top.summary || '';
      const summary = esc(raw.length > SUMMARY_MAX ? raw.substring(0, SUMMARY_MAX) + '\u2026' : raw);
      mainHtml =
        '<div class="vc-news-top-label">Top Story</div>' +
        '<div class="vc-news-headline-bar"><div class="vc-news-headline-text">' + esc(top.title) + '</div></div>' +
        '<div class="vc-news-main-image">' + imgTag(top.image, top.title) + '</div>' +
        (summary ? '<div class="vc-news-summary-box"><div class="vc-news-summary-text">' + summary + '</div></div>' : '');
    } else {
      mainHtml = '<div class="vc-news-no-data">No stories available.</div>';
    }

    frame.innerHTML =
      '<div class="vc-news-header">' +
        '<div class="vc-news-header-left">' +
          '<span class="vc-news-globe">\uD83C\uDF10</span>' +
          '<span class="vc-news-brand">RetroIPTV <strong>News</strong></span>' +
        '</div>' +
        '<div class="vc-news-header-right">Latest Headlines</div>' +
      '</div>' +
      '<div class="vc-news-body">' +
        '<div class="vc-news-main">' + mainHtml + '</div>' +
        '<div class="vc-news-sidebar">' + sideRows.join('') + '</div>' +
      '</div>' +
      '<div class="vc-news-ticker-bar">' +
        '<div class="vc-news-ticker-label">Breaking News:</div>' +
        '<div class="vc-news-ticker-scroll">' +
          '<span class="vc-news-ticker-track">' + tickRepeat + '</span>' +
        '</div>' +
      '</div>';

    overlay.appendChild(frame);
    root.appendChild(overlay);

    // Set constant-speed ticker duration after layout
    applyTickerSpeed(frame);
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/news');
  }

  // ── Feed cycling state ────────────────────────────────────────────────────
  // The server drives which feed is active via wall-clock time so all clients
  // are always in sync regardless of whether anyone is tuned in.
  let _lastFeedIndex = -1;  // feed_index from the last successful fetch
  let _seq           = -1;  // advance sequence (forced-advance detection)
  let _cycleTimer    = null; // fires at ms_until_next_feed to trigger next render
  let _pollTimer     = null; // 3-second poll for forced-advance detection

  // Called when the cycle timer fires — the server has already transitioned to
  // the next slot, so a plain OverlayEngine.tick() picks up the new feed_index.
  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
    // fetchData() will set a new _cycleTimer after the fetch resolves
  }

  // Wraps the plain fetchData so we can hook into the response before render.
  const _origFetchData = fetchData;
  async function fetchDataWithCycling() {
    const data = await _origFetchData();
    if (data.seq !== undefined && _seq === -1) { _seq = data.seq; }
    // Schedule the next feed transition precisely at ms_until_next_feed.
    // Only set a new timer if one isn't already pending — this prevents
    // OverlayEngine's own periodic refresh (e.g. every 60 s) from resetting
    // the cycle timer early.
    if (_cycleTimer === null) {
      const msUntilNext = (data.ms_until_next_feed > 0) ? data.ms_until_next_feed : 5 * 60 * 1000;
      _cycleTimer = setTimeout(advanceAndTick, msUntilNext);
    }
    _lastFeedIndex = data.feed_index;
    return data;
  }

  // Lightweight 3-second poll: detect forced advances via /api/news/advance
  async function pollStatus() {
    try {
      const resp = await fetch('/api/news/status', { credentials: 'same-origin' });
      if (resp.ok) {
        const data = await resp.json();
        if (_seq !== -1 && data.seq !== undefined && data.seq !== _seq) {
          _seq = data.seq;
          // Cancel any pending cycle timer and re-render immediately
          clearTimeout(_cycleTimer);
          _cycleTimer = null;
          if (window.OverlayEngine.isActive(TYPE)) {
            window.OverlayEngine.tick();
          }
        }
      }
    } catch (_) { /* ignore poll errors */ }
    _pollTimer = setTimeout(pollStatus, STATUS_POLL_MS);
  }

  // Wrap render() to start the status poll lazily on first render
  const _origRender = render;
  function renderWithPolling(data, root) {
    _origRender(data, root);
    if (_pollTimer === null) {
      _pollTimer = setTimeout(pollStatus, STATUS_POLL_MS);
    }
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchDataWithCycling, render: renderWithPolling });
})();

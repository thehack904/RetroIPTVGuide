/* On This Day overlay renderer (v1)
 * Renders a broadcast-card style "On This Day" display that cycles through
 * historical events, notable births, and deaths sourced from Wikipedia.
 *
 * Cycle logic (wall-clock aligned so every viewer sees the same event):
 *   event_index = floor((now_ts % (event_count × 30)) ÷ 30)
 *   ms_until_next = remaining ms in the current 30-second slot
 *
 * The server drives all timing via `ms_until_next` in the API response, so
 * the client schedules its next fetch precisely at the event-transition point.
 *
 * Endpoint: GET /api/on_this_day
 */
(function () {
  'use strict';
  const TYPE     = 'on_this_day';
  const STYLE_ID = 'vc-otd-overlay-styles-v1';

  const FONT_SCALE_DIVISOR = 52;
  const FONT_MIN_PX        = 9;
  const FONT_MAX_PX        = 14;

  // ── Category colours ────────────────────────────────────────────────────────
  const CATEGORY_COLORS = {
    event: { bg: '#c8860a', text: '#fff', label: 'EVENT' },
    birth: { bg: '#1a6a2a', text: '#fff', label: 'BORN' },
    death: { bg: '#6a1a1a', text: '#fff', label: 'DIED' },
  };

  // ── CSS ──────────────────────────────────────────────────────────────────────
  const CSS = `
    .vc-otd-frame {
      position: absolute;
      inset: 0;
      background: linear-gradient(160deg, #1030c8 0%, #0a1a80 40%, #081060 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    /* CRT scanline vignette */
    .vc-otd-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.07) 3px, rgba(0,0,0,0.07) 4px);
      pointer-events: none;
      z-index: 20;
    }
    /* ── Header bar ─────────────────────────────────────────────────── */
    .vc-otd-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1640d4 50%, #0d2aaa 100%);
      border-bottom: 0.18em solid #4a70ff;
      padding: 0 0.8em;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      height: 2.5em;
      z-index: 5;
    }
    .vc-otd-header-left {
      display: flex;
      align-items: center;
      gap: 0.35em;
    }
    .vc-otd-brand {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-otd-header-date {
      font-size: 0.95em;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: #c8d8ff;
    }
    .vc-otd-header-right {
      font-size: 0.75em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #c8d8ff;
    }
    /* ── Main content area ────────────────────────────────────────── */
    .vc-otd-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 0.6em 1.2em;
      background: radial-gradient(ellipse at center, #0a2060 0%, #050d3a 100%);
      min-height: 0;
    }
    .vc-otd-year {
      font-size: 4.5em;
      font-weight: 900;
      letter-spacing: 0.04em;
      color: #ffd700;
      text-shadow: 0 0 0.3em rgba(255,215,0,0.4), 0 2px 8px rgba(0,0,0,0.8);
      line-height: 1;
      margin-bottom: 0.1em;
      text-align: center;
    }
    .vc-otd-category-tag {
      display: inline-block;
      font-size: 0.7em;
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      padding: 0.2em 0.65em;
      border-radius: 0.25em;
      margin-bottom: 0.5em;
    }
    .vc-otd-text {
      font-size: 1.3em;
      font-weight: 700;
      text-align: center;
      color: #d0e0ff;
      line-height: 1.45;
      text-shadow: 0 1px 4px rgba(0,0,0,0.9);
      max-width: 90%;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    /* ── Progress bar ──────────────────────────────────────────────── */
    .vc-otd-progress-wrap {
      height: 0.25em;
      background: rgba(255,255,255,0.1);
      flex-shrink: 0;
      overflow: hidden;
      z-index: 5;
    }
    .vc-otd-progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #1a3aaa, #4a70ff);
      transition: width 0.5s linear;
    }
    /* ── Ticker bar ────────────────────────────────────────────────── */
    .vc-otd-ticker-bar {
      background: #0a0e2a;
      border-top: 0.12em solid #4a70ff;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.8em;
      z-index: 5;
    }
    .vc-otd-ticker-label {
      background: #ffd700;
      color: #0a0e2a;
      font-size: 0.65em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 0 0.9em;
      white-space: nowrap;
      height: 100%;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      border-right: 0.1em solid #4a70ff;
    }
    .vc-otd-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-otd-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.65em;
      font-weight: 700;
      color: #ffd700;
      will-change: transform;
    }
    /* ── No-data state ─────────────────────────────────────────────── */
    .vc-otd-no-data {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.6em;
    }
    .vc-otd-no-data-icon  { font-size: 3em; }
    .vc-otd-no-data-text  { font-size: 0.95em; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #6080c0; }
    .vc-otd-no-data-hint  { font-size: 0.7em; color: #4060a0; max-width: 28em; text-align: center; line-height: 1.5; }
    /* ── Event counter ─────────────────────────────────────────────── */
    .vc-otd-counter {
      font-size: 0.65em;
      font-weight: 700;
      color: #90a8f0;
      letter-spacing: 0.06em;
      margin-top: 0.6em;
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

  // ── Cycle timer ───────────────────────────────────────────────────────────────
  let _cycleTimer = null;

  // ── Ticker RAF loop ───────────────────────────────────────────────────────────
  // Scrolls at a constant TICKER_PX_PER_S pixels per second regardless of how
  // much text is in the ticker.  Position is persisted across render() calls so
  // the ticker never resets when the main event card cycles.
  const TICKER_PX_PER_S = 40;
  let _tickerRaf = null;
  let _tickerX   = null;  // persisted position; null = start from right edge

  function _stopTicker() {
    if (_tickerRaf !== null) {
      cancelAnimationFrame(_tickerRaf);
      _tickerRaf = null;
    }
    // _tickerX is intentionally NOT cleared here so the next render can resume.
  }

  function _stopTickerAndReset() {
    _stopTicker();
    _tickerX = null;
  }

  function _startTicker(trackEl, scrollEl) {
    _stopTicker();
    const viewW  = scrollEl.offsetWidth || 400;
    // Resume from the saved position; fall back to right edge on first start.
    let x        = (_tickerX !== null) ? _tickerX : viewW;
    let lastTime = null;

    function step(ts) {
      if (!trackEl.isConnected) { _tickerRaf = null; return; }
      if (lastTime === null) { lastTime = ts; }
      const dt = (ts - lastTime) / 1000;  // seconds
      lastTime = ts;
      x -= TICKER_PX_PER_S * dt;
      // Reset when the text has fully scrolled off the left
      const textW = trackEl.offsetWidth;
      if (x <= -textW) { x = viewW; }
      _tickerX = x;  // persist for the next render
      trackEl.style.transform = 'translateX(' + x.toFixed(2) + 'px)';
      _tickerRaf = requestAnimationFrame(step);
    }
    _tickerRaf = requestAnimationFrame(step);
  }

  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
  }

  function render(data, root) {
    ensureStyles();
    _stopTicker();
    root.querySelectorAll('.vc-overlay').forEach(function (e) { e.remove(); });
    root.classList.remove('hidden');

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-otd-frame';

    const fw = root.offsetWidth || 960;
    frame.style.fontSize = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX)) + 'px';

    const event      = data && data.event;
    const eventCount = (data && data.event_count)  || 0;
    const eventIndex = (data && data.event_index)  || 0;
    const spe        = (data && data.seconds_per_event) || 30;
    const dateLabel  = (data && data.date_label)   || '';
    const msUntilNext = (data && data.ms_until_next) || (spe * 1000);

    // Progress bar
    const slotElapsed = spe - (msUntilNext / 1000);
    const pct = Math.max(0, Math.min(100, (slotElapsed / spe) * 100));

    // Header
    const headerHtml =
      '<div class="vc-otd-header">' +
        '<div class="vc-otd-header-left">' +
          '<span style="font-size:1.4em">&#128240;</span>' +
          '<span class="vc-otd-brand">On This Day</span>' +
          (dateLabel ? '<span class="vc-otd-header-date">\u2014 ' + esc(dateLabel) + '</span>' : '') +
        '</div>' +
        '<div class="vc-otd-header-right">' +
          (eventCount > 0 ? esc((eventIndex + 1) + ' / ' + eventCount) : '') +
        '</div>' +
      '</div>';

    if (!event) {
      frame.innerHTML =
        headerHtml +
        '<div class="vc-otd-no-data">' +
          '<div class="vc-otd-no-data-icon">&#9203;</div>' +
          '<div class="vc-otd-no-data-text">No Events Available</div>' +
          '<div class="vc-otd-no-data-hint">Enable sources in Virtual Channels settings or add custom entries.</div>' +
        '</div>' +
        '<div class="vc-otd-progress-wrap"><div class="vc-otd-progress-bar" style="width:0%"></div></div>' +
        '<div class="vc-otd-ticker-bar">' +
          '<div class="vc-otd-ticker-label">On This Day</div>' +
          '<div class="vc-otd-ticker-scroll">' +
            '<span class="vc-otd-ticker-track">No events loaded \u2022 </span>' +
          '</div>' +
        '</div>';
    } else {
      const cat     = event.category || 'event';
      const colors  = CATEGORY_COLORS[cat] || CATEGORY_COLORS.event;
      const year    = esc(event.year  || '');
      const text    = esc(event.text  || '');
      const tagHtml = '<span class="vc-otd-category-tag" style="background:' +
                      colors.bg + ';color:' + colors.text + '">' +
                      esc(colors.label) + '</span>';

      // Ticker: cycle through all events
      const allEvents = (data && data.events) || [];
      const tickParts = allEvents.slice(0, 20).map(function (ev) {
        const c = CATEGORY_COLORS[ev.category || 'event'] || CATEGORY_COLORS.event;
        return '[' + (ev.year || '') + '] ' + (ev.text || '');
      });
      const tickText = tickParts.join(' \u2022 ') + ' \u2022 ';

      frame.innerHTML =
        headerHtml +
        '<div class="vc-otd-body">' +
          (year ? '<div class="vc-otd-year">' + year + '</div>' : '') +
          tagHtml +
          '<div class="vc-otd-text">' + text + '</div>' +
          '<div class="vc-otd-counter">Event ' + (eventIndex + 1) + ' of ' + eventCount + '</div>' +
        '</div>' +
        '<div class="vc-otd-progress-wrap">' +
          '<div class="vc-otd-progress-bar" id="vc-otd-progress" style="width:' + pct.toFixed(1) + '%"></div>' +
        '</div>' +
        '<div class="vc-otd-ticker-bar">' +
          '<div class="vc-otd-ticker-label">On This Day</div>' +
          '<div class="vc-otd-ticker-scroll">' +
            '<span class="vc-otd-ticker-track">' + esc(tickText) + '</span>' +
          '</div>' +
        '</div>';

      setTimeout(function () {
        const progressEl = frame.querySelector('#vc-otd-progress');
        if (progressEl && msUntilNext > 0) {
          progressEl.style.transition = 'width ' + (msUntilNext / 1000).toFixed(1) + 's linear';
          requestAnimationFrame(function () {
            requestAnimationFrame(function () {
              progressEl.style.width = '100%';
            });
          });
        }
      }, 0);
    }

    overlay.appendChild(frame);
    root.appendChild(overlay);

    // Start constant-speed ticker after the frame is in the DOM
    const trackEl  = frame.querySelector('.vc-otd-ticker-track');
    const scrollEl = frame.querySelector('.vc-otd-ticker-scroll');
    if (trackEl && scrollEl) { _startTicker(trackEl, scrollEl); }
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/on_this_day');
  }

  async function fetchDataWithCycling() {
    const data = await fetchData();
    if (_cycleTimer === null) {
      const ms = (data && data.ms_until_next > 0) ? data.ms_until_next : 30 * 1000;
      _cycleTimer = setTimeout(advanceAndTick, ms);
    }
    return data;
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchDataWithCycling, render: render });
  window.OverlayEngine.onStop(_stopTickerAndReset);
})();

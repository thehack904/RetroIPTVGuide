/* Sports overlay renderer (v1)
 * Renders the retro TV sports broadcast layout into the virtual channel
 * overlay.  Handles both 'scores' mode (user-configured external JSON feed)
 * and 'rss' mode (user-supplied RSS/Atom feeds), matching the /sports
 * standalone page design but using a blue colour palette consistent with the
 * other virtual channels.
 * Compact: base font-size is set proportional to the container width in JS so
 * every em-based value scales together.
 * Endpoint: GET /api/sports
 */
(function () {
  'use strict';
  const TYPE     = 'sports';
  const STYLE_ID = 'vc-sports-overlay-styles-v1';

  const TICKER_PX_PER_SEC  = 40;
  const TICKER_REPEAT_COUNT = 3;
  const SUMMARY_MAX        = 220;

  const FALLBACK_IMG = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 160 90'%3E%3Crect width='160' height='90' fill='%230a1a70'/%3E%3Ctext x='80' y='50' text-anchor='middle' font-family='Arial' font-size='12' fill='%234060cc'%3ENo Image%3C%2Ftext%3E%3C%2Fsvg%3E";

  // ── CSS: em-based so everything scales with the JS-driven base font-size ──
  const CSS = `
    .vc-sp-frame {
      position: absolute;
      inset: 0;
      background: linear-gradient(160deg, #1030c8 0%, #0a1a80 40%, #081060 100%);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    .vc-sp-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.06) 3px, rgba(0,0,0,0.06) 4px);
      pointer-events: none;
      z-index: 10;
    }
    .vc-sp-header {
      background: linear-gradient(90deg, #0d2aaa 0%, #1640d4 50%, #0d2aaa 100%);
      border-bottom: 0.18em solid #4a70ff;
      padding: 0 0.9em;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      height: 2.6em;
    }
    .vc-sp-header-left {
      display: flex;
      align-items: center;
      gap: 0.3em;
    }
    .vc-sp-icon { font-size: 1.6em; line-height: 1; }
    .vc-sp-brand {
      font-size: 1.25em;
      font-weight: 400;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-sp-brand strong { font-weight: 900; }
    .vc-sp-header-right {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.05em;
    }
    .vc-sp-header-title {
      font-size: 1.2em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #fff;
    }
    .vc-sp-header-sub {
      font-size: 0.7em;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #ffd700;
    }

    /* ── Scores mode ── */
    .vc-sp-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      padding: 0.4em 0.5em 0.25em;
      gap: 0.3em;
      min-height: 0;
      overflow: hidden;
    }
    .vc-sp-grid {
      flex: 1;
      display: grid;
      gap: 0.3em;
      min-height: 0;
    }
    .vc-sp-grid.cols-1 { grid-template-columns: 1fr; }
    .vc-sp-grid.cols-2 { grid-template-columns: 1fr 1fr; }
    .vc-sp-grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
    .vc-sp-game {
      background: rgba(10,40,170,0.75);
      border: 0.12em solid #3058d8;
      border-radius: 3px;
      display: flex;
      flex-direction: column;
      align-items: stretch;
      justify-content: center;
      padding: 0.3em 0.55em;
      min-height: 0;
      overflow: hidden;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 6px rgba(0,0,0,0.4);
    }
    .vc-sp-game-status {
      font-size: 0.72em;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      text-align: center;
      margin-bottom: 0.15em;
    }
    .vc-sp-game-status.live  { color: #ff6666; }
    .vc-sp-game-status.final { color: #40c0ff; }
    .vc-sp-game-status.pre   { color: #ffd700; }
    .vc-sp-matchup {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.35em;
    }
    .vc-sp-team {
      display: flex;
      flex-direction: column;
      align-items: center;
      flex: 1;
      min-width: 0;
    }
    .vc-sp-team-abbr {
      font-size: 1.2em;
      font-weight: 900;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #fff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
    }
    .vc-sp-team-name {
      font-size: 0.65em;
      color: #c8d8ff;
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
    }
    .vc-sp-score-block {
      display: flex;
      align-items: center;
      gap: 0.2em;
      flex-shrink: 0;
    }
    .vc-sp-score {
      font-size: 1.75em;
      font-weight: 900;
      color: #fff;
      min-width: 1.3em;
      text-align: center;
      line-height: 1;
    }
    .vc-sp-score-sep {
      font-size: 1.1em;
      font-weight: 700;
      color: #4a70ff;
    }
    .vc-sp-no-games {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.9em;
      color: #90a8f0;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    /* ── RSS mode ── */
    .vc-sp-rss-body {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 0.46fr;
      gap: 0.35em;
      padding: 0.45em 0.55em 0.25em;
      min-height: 0;
    }
    .vc-sp-rss-main {
      display: flex;
      flex-direction: column;
      background: rgba(8,28,120,0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.2em 1em rgba(0,0,0,0.6);
    }
    .vc-sp-rss-top-label {
      padding: 0.22em 0.5em 0.08em;
      font-size: 0.82em;
      font-style: italic;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: #ffd700;
    }
    .vc-sp-rss-headline-bar {
      background: linear-gradient(90deg, #0d2aaa 0%, #1640d4 55%, #0d2aaa 100%);
      padding: 0.22em 0.5em;
    }
    .vc-sp-rss-headline-text {
      font-size: 1.1em;
      font-weight: 900;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: #fff;
      line-height: 1.15;
    }
    .vc-sp-rss-image {
      flex: 1;
      background: #0a1a5a;
      overflow: hidden;
      min-height: 0;
    }
    .vc-sp-rss-image img {
      width: 100%; height: 100%; object-fit: cover; display: block;
    }
    .vc-sp-rss-summary-box {
      background: rgba(6,20,90,0.85);
      border-top: 0.12em solid #3a5ccc;
      padding: 0.35em 0.55em;
    }
    .vc-sp-rss-summary-text {
      font-size: 0.72em;
      font-weight: 400;
      line-height: 1.45;
      color: #e8eeff;
    }
    .vc-sp-rss-sidebar {
      display: flex;
      flex-direction: column;
      gap: 0.25em;
    }
    .vc-sp-rss-item {
      flex: 1;
      display: flex;
      background: rgba(8,28,120,0.65);
      border: 0.12em solid #3a5ccc;
      border-radius: 2px;
      overflow: hidden;
      box-shadow: 0 0.12em 0.5em rgba(0,0,0,0.5);
      min-height: 0;
    }
    .vc-sp-rss-item-img {
      width: 5.2em;
      flex-shrink: 0;
      background: #071460;
      overflow: hidden;
    }
    .vc-sp-rss-item-img img {
      width: 100%; height: 100%; object-fit: cover; display: block;
    }
    .vc-sp-rss-item-text {
      flex: 1;
      display: flex;
      align-items: center;
      padding: 0.22em 0.4em;
    }
    .vc-sp-rss-item-title {
      font-size: 0.72em;
      font-weight: 700;
      line-height: 1.3;
      color: #fff;
    }
    .vc-sp-rss-placeholder { opacity: 0.25; }
    .vc-sp-no-data {
      display: flex;
      align-items: center;
      justify-content: center;
      flex: 1;
      font-size: 0.9em;
      color: #90a8f0;
      letter-spacing: 0.1em;
    }

    /* ── Ticker ── */
    .vc-sp-ticker-bar {
      background: #0a0e2a;
      border-top: 0.12em solid #4a70ff;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.65em;
    }
    .vc-sp-ticker-label {
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
      border-right: 0.12em solid #4a70ff;
    }
    .vc-sp-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-sp-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.7em;
      font-weight: 700;
      color: #ffd700;
      animation: vc-sp-scroll 300s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-sp-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
  `;

  // Font-size scaling constants
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
    return '<img src="' + src + '" alt="' + esc(alt) + '" onerror="this.src=\'' + FALLBACK_IMG + '\'">';
  }

  function formatLocalTime(isoStr) {
    try {
      return new Date(isoStr).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch (e) { return ''; }
  }

  function formatDate() {
    return new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
  }

  function applyTickerSpeed(frame) {
    const track = frame.querySelector('.vc-sp-ticker-track');
    if (!track) return;
    setTimeout(function () {
      const w = track.offsetWidth;
      if (w > 0) {
        track.style.animationDuration = (w / TICKER_PX_PER_SEC).toFixed(1) + 's';
      }
    }, 0);
  }

  // ── Scores mode ──────────────────────────────────────────────────────────
  function buildScoresHtml(data) {
    const league = data.league || null;
    const games  = Array.isArray(data.games) ? data.games : [];

    // Not configured: no leagues selected
    if (!league) {
      return '<div class="vc-sp-header">' +
          '<div class="vc-sp-header-left">' +
            '<span class="vc-sp-icon">\uD83C\uDFC6</span>' +
            '<span class="vc-sp-brand">RetroIPTV <strong>Sports</strong></span>' +
          '</div>' +
          '<div class="vc-sp-header-right">' +
            '<div class="vc-sp-header-title">Scores</div>' +
          '</div>' +
        '</div>' +
        '<div class="vc-sp-body">' +
          '<div class="vc-sp-no-games" style="flex-direction:column;gap:0.4em;">' +
            '<div style="font-size:2.5em;">\uD83C\uDFC6</div>' +
            '<div>No Leagues Configured</div>' +
            '<div style="font-size:0.75em;font-weight:400;color:#4060a0;max-width:22em;text-align:center;line-height:1.45;">' +
              'Select leagues in Virtual Sports Channel Settings.' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="vc-sp-ticker-bar">' +
          '<div class="vc-sp-ticker-label">Scores:</div>' +
          '<div class="vc-sp-ticker-scroll">' +
            '<span class="vc-sp-ticker-track">No leagues configured \u2022 </span>' +
          '</div>' +
        '</div>';
    }

    const emoji  = esc(league.emoji || '\uD83C\uDFC6');
    const name   = esc(league.name  || 'Sports');

    const tickParts = games.length
      ? games.map(function (g) {
          const away = esc(g.away_abbr || g.away_team || '?');
          const home = esc(g.home_abbr || g.home_team || '?');
          return g.status_state === 'pre'
            ? esc(g.status_text) + ' \u2014 ' + away + ' @ ' + home
            : away + ' ' + esc(g.away_score) +
              ' \u2013 ' +
              home + ' ' + esc(g.home_score) +
              ' (' + esc(g.status_text) + ')';
        }).join(' \u2022 ')
      : 'No games scheduled today';
    const tickRepeat = Array(TICKER_REPEAT_COUNT).fill(tickParts + ' \u2022 ').join('');

    const cols = games.length <= 2 ? 'cols-1'
               : games.length <= 4 ? 'cols-2'
               :                     'cols-3';

    const gameCards = games.length
      ? games.map(function (g) {
          const stateClass   = g.status_state === 'in'   ? 'live'
                             : g.status_state === 'post'  ? 'final'
                             :                              'pre';
          const statusLabel  = g.status_state === 'in'   ? '\u25cf LIVE \u2014 ' + esc(g.status_text)
                             : g.status_state === 'post'  ? 'FINAL'
                             :                              esc(g.status_text || 'Scheduled');
          const awayScore    = (g.status_state !== 'pre' && g.away_score !== '') ? esc(g.away_score) : '\u2013';
          const homeScore    = (g.status_state !== 'pre' && g.home_score !== '') ? esc(g.home_score) : '\u2013';
          return '<div class="vc-sp-game">' +
            '<div class="vc-sp-game-status ' + stateClass + '">' + statusLabel + '</div>' +
            '<div class="vc-sp-matchup">' +
              '<div class="vc-sp-team">' +
                '<div class="vc-sp-team-abbr">' + esc(g.away_abbr || g.away_team) + '</div>' +
                '<div class="vc-sp-team-name">'  + esc(g.away_team) + '</div>' +
              '</div>' +
              '<div class="vc-sp-score-block">' +
                '<div class="vc-sp-score">' + awayScore + '</div>' +
                '<div class="vc-sp-score-sep">@</div>' +
                '<div class="vc-sp-score">' + homeScore + '</div>' +
              '</div>' +
              '<div class="vc-sp-team">' +
                '<div class="vc-sp-team-abbr">' + esc(g.home_abbr || g.home_team) + '</div>' +
                '<div class="vc-sp-team-name">'  + esc(g.home_team) + '</div>' +
              '</div>' +
            '</div>' +
          '</div>';
        }).join('')
      : '<div class="vc-sp-no-games">No games scheduled today</div>';

    return '<div class="vc-sp-header">' +
        '<div class="vc-sp-header-left">' +
          '<span class="vc-sp-icon">' + emoji + '</span>' +
          '<span class="vc-sp-brand">RetroIPTV <strong>Sports</strong></span>' +
        '</div>' +
        '<div class="vc-sp-header-right">' +
          '<div class="vc-sp-header-title">' + name + '</div>' +
          '<div class="vc-sp-header-sub">' + formatDate() + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="vc-sp-body">' +
        '<div class="vc-sp-grid ' + cols + '">' + gameCards + '</div>' +
      '</div>' +
      '<div class="vc-sp-ticker-bar">' +
        '<div class="vc-sp-ticker-label">Scores:</div>' +
        '<div class="vc-sp-ticker-scroll">' +
          '<span class="vc-sp-ticker-track">' + tickRepeat + '</span>' +
        '</div>' +
      '</div>';
  }

  // ── RSS mode ─────────────────────────────────────────────────────────────
  function buildRssHtml(data) {
    const feedCount = (data.feed_count != null) ? data.feed_count : -1;
    const headlines = Array.isArray(data.headlines) ? data.headlines : [];
    const top       = headlines[0] || null;

    // Not configured: no RSS feeds set up
    if (feedCount === 0) {
      return '<div class="vc-sp-header">' +
          '<div class="vc-sp-header-left">' +
            '<span class="vc-sp-icon">\uD83C\uDFC6</span>' +
            '<span class="vc-sp-brand">RetroIPTV <strong>Sports</strong></span>' +
          '</div>' +
          '<div class="vc-sp-header-right">' +
            '<div class="vc-sp-header-title">Sports News</div>' +
          '</div>' +
        '</div>' +
        '<div class="vc-sp-rss-body">' +
          '<div class="vc-sp-rss-main">' +
            '<div class="vc-sp-no-data" style="flex-direction:column;gap:0.4em;">' +
              '<div style="font-size:2.5em;">\uD83C\uDFC6</div>' +
              '<div>No RSS Feeds Configured</div>' +
              '<div style="font-size:0.75em;font-weight:400;color:#4060a0;max-width:22em;text-align:center;line-height:1.45;">' +
                'Add sports feed URLs in Virtual Sports Channel Settings.' +
              '</div>' +
            '</div>' +
          '</div>' +
          '<div class="vc-sp-rss-sidebar"></div>' +
        '</div>' +
        '<div class="vc-sp-ticker-bar">' +
          '<div class="vc-sp-ticker-label">Sports News:</div>' +
          '<div class="vc-sp-ticker-scroll">' +
            '<span class="vc-sp-ticker-track">No RSS feeds configured \u2022 </span>' +
          '</div>' +
        '</div>';
    }

    const sideItems = headlines.slice(1, 6);
    const tickItems = headlines.slice(0, 10);

    const tickText = tickItems.length
      ? tickItems.map(function (h) { return esc(h.title); }).join(' \u2022 ') + ' \u2022 '
      : 'No sports headlines available \u2022 ';
    const tickRepeat = Array(TICKER_REPEAT_COUNT).fill(tickText).join('');

    const sideRows = [];
    for (let i = 0; i < 5; i++) {
      const h = sideItems[i];
      if (h) {
        sideRows.push(
          '<div class="vc-sp-rss-item">' +
            '<div class="vc-sp-rss-item-img">' + imgTag(h.image, h.title) + '</div>' +
            '<div class="vc-sp-rss-item-text"><div class="vc-sp-rss-item-title">' + esc(h.title) + '</div></div>' +
          '</div>'
        );
      } else {
        sideRows.push('<div class="vc-sp-rss-item vc-sp-rss-placeholder"></div>');
      }
    }

    let mainHtml;
    if (top) {
      const raw     = top.summary || '';
      const summary = esc(raw.length > SUMMARY_MAX ? raw.substring(0, SUMMARY_MAX) + '\u2026' : raw);
      mainHtml =
        '<div class="vc-sp-rss-top-label">Top Story</div>' +
        '<div class="vc-sp-rss-headline-bar"><div class="vc-sp-rss-headline-text">' + esc(top.title) + '</div></div>' +
        '<div class="vc-sp-rss-image">' + imgTag(top.image, top.title) + '</div>' +
        (summary ? '<div class="vc-sp-rss-summary-box"><div class="vc-sp-rss-summary-text">' + summary + '</div></div>' : '');
    } else {
      mainHtml = '<div class="vc-sp-no-data">No stories available.</div>';
    }

    return '<div class="vc-sp-header">' +
        '<div class="vc-sp-header-left">' +
          '<span class="vc-sp-icon">\uD83C\uDFC6</span>' +
          '<span class="vc-sp-brand">RetroIPTV <strong>Sports</strong></span>' +
        '</div>' +
        '<div class="vc-sp-header-right">' +
          '<div class="vc-sp-header-title">Latest Sports News</div>' +
          '<div class="vc-sp-header-sub">Updated: ' + (data.updated ? formatLocalTime(data.updated) : '') + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="vc-sp-rss-body">' +
        '<div class="vc-sp-rss-main">' + mainHtml + '</div>' +
        '<div class="vc-sp-rss-sidebar">' + sideRows.join('') + '</div>' +
      '</div>' +
      '<div class="vc-sp-ticker-bar">' +
        '<div class="vc-sp-ticker-label">Sports News:</div>' +
        '<div class="vc-sp-ticker-scroll">' +
          '<span class="vc-sp-ticker-track">' + tickRepeat + '</span>' +
        '</div>' +
      '</div>';
  }

  // ── Main render ───────────────────────────────────────────────────────────
  function render(data, root) {
    ensureStyles();
    root.querySelectorAll('.vc-overlay').forEach(function (e) { e.remove(); });
    root.classList.remove('hidden');

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-sp-frame';

    // Scale font-size proportionally to container width
    const fw         = root.offsetWidth || 960;
    const baseFontPx = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX));
    frame.style.fontSize = baseFontPx + 'px';

    frame.innerHTML = (data && data.mode === 'rss')
      ? buildRssHtml(data)
      : buildScoresHtml(data || {});

    overlay.appendChild(frame);
    root.appendChild(overlay);

    applyTickerSpeed(frame);
  }

  // ── Feed cycling (mirrors news.js pattern for rss mode) ───────────────────
  let _cycleTimer    = null;
  let _lastFeedIndex = null;
  let _feedUpdatedAt = null;

  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
  }

  async function fetchData() {
    const data = await window.OverlayEngine.fetchJson('/api/sports');
    if (data.mode === 'rss') {
      if (data.feed_index !== _lastFeedIndex) {
        _lastFeedIndex = data.feed_index;
        _feedUpdatedAt = data.updated;
      }
      data.updated = _feedUpdatedAt || data.updated;
      if (_cycleTimer === null) {
        const msUntilNext = (data.ms_until_next > 0) ? data.ms_until_next : 5 * 60 * 1000;
        _cycleTimer = setTimeout(advanceAndTick, msUntilNext);
      }
    }
    return data;
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render: render });
})();

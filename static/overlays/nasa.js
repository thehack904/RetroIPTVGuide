/* NASA Imagery overlay renderer (v1)
 * Renders a full-screen NASA APOD (Astronomy Picture of the Day) slideshow
 * into the virtual channel overlay with a retro space-broadcast aesthetic.
 *
 * Cycle logic (all wall-clock aligned so every viewer sees the same image):
 *   15-min cycle /  5 images → 180 s (3 min) per image
 *   15-min cycle / 15 images →  60 s (1 min) per image
 *   30-min cycle / 10 images → 180 s (3 min) per image
 *   30-min cycle / 15 images → 120 s (2 min) per image
 *
 * The server drives all timing via `ms_until_next` in the API response, so
 * the client schedules its next fetch precisely at the image-transition point.
 *
 * Endpoint: GET /api/nasa
 */
(function () {
  'use strict';
  const TYPE     = 'nasa';
  const STYLE_ID = 'vc-nasa-overlay-styles-v1';

  const FONT_SCALE_DIVISOR = 52;
  const FONT_MIN_PX        = 9;
  const FONT_MAX_PX        = 14;

  // ── CSS ───────────────────────────────────────────────────────────────────
  const CSS = `
    .vc-nasa-frame {
      position: absolute;
      inset: 0;
      background: #000;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    /* subtle CRT scanline vignette */
    .vc-nasa-frame::after {
      content: '';
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(0deg, transparent, transparent 3px,
                  rgba(0,0,0,0.07) 3px, rgba(0,0,0,0.07) 4px);
      pointer-events: none;
      z-index: 20;
    }
    /* ── Header bar ──────────────────────────────────────────────────── */
    .vc-nasa-header {
      background: linear-gradient(90deg, #0c0e1a 0%, #0d1a3a 50%, #0c0e1a 100%);
      border-bottom: 0.18em solid #1a4aaa;
      padding: 0 0.8em;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      height: 2.5em;
      z-index: 5;
    }
    .vc-nasa-header-left {
      display: flex;
      align-items: center;
      gap: 0.35em;
    }
    .vc-nasa-brand {
      font-size: 1.2em;
      font-weight: 400;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #c8d8ff;
    }
    .vc-nasa-brand strong { font-weight: 900; color: #fff; }
    .vc-nasa-header-right {
      font-size: 0.78em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #ffd700;
    }
    /* ── Main image area ─────────────────────────────────────────────── */
    .vc-nasa-image-wrap {
      flex: 1;
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 0;
    }
    .vc-nasa-img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      display: block;
      position: relative;
      z-index: 1;
      transition: opacity 0.6s ease;
    }
    .vc-nasa-img.loading { opacity: 0; }
    /* blurred backdrop to fill letterbox areas */
    .vc-nasa-backdrop {
      position: absolute;
      inset: 0;
      background-size: cover;
      background-position: center;
      filter: blur(18px) brightness(0.28) saturate(1.6);
      transform: scale(1.08);
      z-index: 0;
    }
    /* ── Info strip at bottom of image ──────────────────────────────── */
    .vc-nasa-info {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      background: linear-gradient(0deg, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.55) 75%, transparent 100%);
      padding: 1.5em 0.9em 0.5em;
      z-index: 3;
    }
    .vc-nasa-title {
      font-size: 1.05em;
      font-weight: 900;
      letter-spacing: 0.02em;
      color: #fff;
      text-shadow: 0 1px 4px rgba(0,0,0,0.9);
      margin-bottom: 0.18em;
    }
    .vc-nasa-meta {
      font-size: 0.72em;
      font-weight: 700;
      color: #90b8f8;
      letter-spacing: 0.04em;
    }
    .vc-nasa-desc {
      font-size: 0.68em;
      font-weight: 400;
      color: #d0deff;
      line-height: 1.45;
      margin-top: 0.3em;
      /* clamp to 3 lines */
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
      max-height: 12em;
      transition: opacity 0.8s ease, max-height 1.0s ease 0.6s, margin-top 1.0s ease 0.6s;
    }
    .vc-nasa-desc.fading {
      opacity: 0;
      max-height: 0;
      margin-top: 0;
    }
    .vc-nasa-header {
      /* existing rules kept; add transition for fade-out */
      transition: opacity 0.8s ease, height 0.8s ease 0.4s, padding 0.8s ease 0.4s, border-bottom-width 0.8s ease 0.4s;
    }
    .vc-nasa-header.faded {
      opacity: 0;
      pointer-events: none;
      height: 0 !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      border-bottom-width: 0 !important;
      overflow: hidden;
    }
    /* ── Image counter dots ──────────────────────────────────────────── */
    .vc-nasa-dots {
      position: absolute;
      top: 0.55em;
      right: 0.7em;
      display: flex;
      gap: 0.3em;
      z-index: 4;
    }
    .vc-nasa-dot {
      width: 0.5em;
      height: 0.5em;
      border-radius: 50%;
      background: rgba(255,255,255,0.35);
      transition: background 0.3s;
    }
    .vc-nasa-dot.active {
      background: #ffd700;
      box-shadow: 0 0 0.3em #ffd70088;
    }
    /* ── Progress bar ────────────────────────────────────────────────── */
    .vc-nasa-progress-wrap {
      height: 0.22em;
      background: rgba(255,255,255,0.12);
      flex-shrink: 0;
      overflow: hidden;
      z-index: 5;
    }
    .vc-nasa-progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #1a6aff, #00c8ff);
      transition: width 0.5s linear;
    }
    /* ── Ticker bar ──────────────────────────────────────────────────── */
    .vc-nasa-ticker-bar {
      background: #04091f;
      border-top: 0.12em solid #1a4aaa;
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
      height: 1.65em;
      z-index: 5;
    }
    .vc-nasa-ticker-label {
      background: linear-gradient(90deg, #0d1a3a, #1a3a7a);
      color: #ffd700;
      font-size: 0.7em;
      font-weight: 900;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 0 0.7em;
      white-space: nowrap;
      height: 100%;
      display: flex;
      align-items: center;
      flex-shrink: 0;
      border-right: 0.12em solid #1a4aaa;
    }
    .vc-nasa-ticker-scroll {
      overflow: hidden;
      flex: 1;
      height: 100%;
      display: flex;
      align-items: center;
    }
    .vc-nasa-ticker-track {
      display: inline-block;
      white-space: nowrap;
      font-size: 0.7em;
      font-weight: 700;
      color: #a8c8ff;
      animation: vc-nasa-scroll 40s linear infinite;
      padding-left: 100%;
    }
    @keyframes vc-nasa-scroll {
      from { transform: translateX(0); }
      to   { transform: translateX(-100%); }
    }
    /* ── No-data state ───────────────────────────────────────────────── */
    .vc-nasa-no-data {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.6em;
      background: radial-gradient(ellipse at center, #0a1a40 0%, #03061a 100%);
    }
    .vc-nasa-no-data-icon { font-size: 3.5em; }
    .vc-nasa-no-data-text {
      font-size: 0.9em;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #4060b0;
    }
    .vc-nasa-no-data-hint {
      font-size: 0.72em;
      color: #304080;
      max-width: 22em;
      text-align: center;
      line-height: 1.5;
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

  function formatDate(dateStr) {
    try {
      const d = new Date(dateStr + 'T12:00:00');
      return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch (e) { return dateStr || ''; }
  }

  // ── Cycle timer (mirrors news.js pattern) ──────────────────────────────────
  let _cycleTimer = null;

  // ── Description/header fade-out state ────────────────────────────────────
  // Once the description fades after 30 s it stays hidden until a full page
  // reload (even as the image cycles forward).
  let _descFaded    = false;
  let _descFadeTimer = null;

  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
  }

  function render(data, root) {
    ensureStyles();
    root.querySelectorAll('.vc-overlay').forEach(function (e) { e.remove(); });
    root.classList.remove('hidden');

    // Cancel any pending 30-second fade timer from the previous render
    if (_descFadeTimer !== null) { clearTimeout(_descFadeTimer); _descFadeTimer = null; }

    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';

    const frame = document.createElement('div');
    frame.className = 'vc-nasa-frame';

    const fw = root.offsetWidth || 960;
    frame.style.fontSize = Math.max(FONT_MIN_PX, Math.min(fw / FONT_SCALE_DIVISOR, FONT_MAX_PX)) + 'px';

    const img         = data && data.image;
    const imageCount  = (data && data.image_count)  || 0;
    const imageIndex  = (data && data.image_index)  || 0;
    const totalImages = (data && data.total_images) || 0;
    const spi         = (data && data.seconds_per_image) || 180;
    const interval    = (data && data.interval) || '15';
    const msUntilNext = (data && data.ms_until_next) || (spi * 1000);

    // Build dot indicators
    const dotsHtml = Array.from({ length: Math.min(imageCount, 15) }, function (_, i) {
      return '<div class="vc-nasa-dot' + (i === imageIndex ? ' active' : '') + '"></div>';
    }).join('');

    // Progress bar: proportion of current slot elapsed
    const slotElapsed = spi - (msUntilNext / 1000);
    const pct = Math.max(0, Math.min(100, (slotElapsed / spi) * 100));

    // Ticker text
    const tickBase = img
      ? esc(img.title || '') + ' — ' + formatDate(img.date || '') +
        ' \u2022 Image ' + (imageIndex + 1) + ' of ' + totalImages +
        ' \u2022 ' + interval + '-Minute Cycle \u2022 '
      : 'NASA Astronomy Picture of the Day \u2022 ';
    const tickText = tickBase.repeat(3);

    // Header / cycle label
    const cycleLabel = interval + '-Min Cycle \u2022 ' + spi + 's/Image';

    if (!img) {
      frame.innerHTML =
        '<div class="vc-nasa-header">' +
          '<div class="vc-nasa-header-left">' +
            '<span style="font-size:1.5em">&#127760;</span>' +
            '<span class="vc-nasa-brand">RetroIPTV <strong>NASA</strong></span>' +
          '</div>' +
          '<div class="vc-nasa-header-right">' + esc(cycleLabel) + '</div>' +
        '</div>' +
        '<div class="vc-nasa-no-data">' +
          '<div class="vc-nasa-no-data-icon">&#128301;</div>' +
          '<div class="vc-nasa-no-data-text">No Images Available</div>' +
          '<div class="vc-nasa-no-data-hint">NASA Astronomy Pictures of the Day are temporarily unavailable. Check Virtual Channels settings or try again shortly.</div>' +
        '</div>' +
        '<div class="vc-nasa-ticker-bar">' +
          '<div class="vc-nasa-ticker-label">NASA APOD:</div>' +
          '<div class="vc-nasa-ticker-scroll">' +
            '<span class="vc-nasa-ticker-track">No images loaded \u2022 </span>' +
          '</div>' +
        '</div>';
    } else {
      const imgUrl  = esc(img.url || '');
      const hdUrl   = esc(img.hdurl || img.url || '');
      const title   = esc(img.title || 'Astronomy Picture of the Day');
      const dateStr = formatDate(img.date || '');
      const credit  = img.copyright ? ' \u00a9 ' + esc(img.copyright) : 'NASA / Public Domain';
      // Clamp explanation to a reasonable preview
      const explanation = esc((img.explanation || '').substring(0, 380));

      frame.innerHTML =
        '<div class="vc-nasa-header">' +
          '<div class="vc-nasa-header-left">' +
            '<span style="font-size:1.5em">&#127760;</span>' +
            '<span class="vc-nasa-brand">RetroIPTV <strong>NASA</strong></span>' +
          '</div>' +
          '<div class="vc-nasa-header-right">' + esc(cycleLabel) + '</div>' +
        '</div>' +
        '<div class="vc-nasa-image-wrap">' +
          '<div class="vc-nasa-backdrop" style="background-image:url(\'' + imgUrl + '\')"></div>' +
          '<img class="vc-nasa-img loading" src="' + hdUrl + '" alt="' + title + '" id="vc-nasa-current-img">' +
          '<div class="vc-nasa-dots" id="vc-nasa-dots">' + dotsHtml + '</div>' +
          '<div class="vc-nasa-info">' +
            '<div class="vc-nasa-title">' + title + '</div>' +
            '<div class="vc-nasa-meta">' + dateStr + ' &nbsp;\u2022&nbsp; ' + credit + '</div>' +
            (explanation ? '<div class="vc-nasa-desc">' + explanation + '</div>' : '') +
          '</div>' +
        '</div>' +
        '<div class="vc-nasa-progress-wrap">' +
          '<div class="vc-nasa-progress-bar" id="vc-nasa-progress" style="width:' + pct.toFixed(1) + '%"></div>' +
        '</div>' +
        '<div class="vc-nasa-ticker-bar">' +
          '<div class="vc-nasa-ticker-label">NASA APOD:</div>' +
          '<div class="vc-nasa-ticker-scroll">' +
            '<span class="vc-nasa-ticker-track">' + tickText + '</span>' +
          '</div>' +
        '</div>';

      // Fade-in the image once loaded
      setTimeout(function () {
        const imgEl = frame.querySelector('#vc-nasa-current-img');
        if (!imgEl) return;
        if (imgEl.complete && imgEl.naturalWidth) {
          imgEl.classList.remove('loading');
        } else {
          imgEl.addEventListener('load', function () { imgEl.classList.remove('loading'); });
          imgEl.addEventListener('error', function () { imgEl.classList.remove('loading'); });
        }
        // Animate progress bar smoothly to 100% over the remaining slot
        var progressEl = frame.querySelector('#vc-nasa-progress');
        if (progressEl && msUntilNext > 0) {
          progressEl.style.transition = 'width ' + (msUntilNext / 1000).toFixed(1) + 's linear';
          // Kick off transition on next frame
          requestAnimationFrame(function () {
            requestAnimationFrame(function () {
              progressEl.style.width = '100%';
            });
          });
        }

        // ── Description & header fade-out after 30 s (wall-clock aware) ──────
        // If the user tunes in mid-slot (elapsed > 30 s), fade immediately.
        var descEl   = frame.querySelector('.vc-nasa-desc');
        var headerEl = frame.querySelector('.vc-nasa-header');
        var slotElapsedMs = (spi - (msUntilNext / 1000)) * 1000;
        var fadeDelay     = Math.max(0, 30000 - slotElapsedMs);
        if (_descFaded || fadeDelay === 0) {
          // Already past 30 s in this slot — hide immediately
          _descFaded = true;
          if (descEl)   { descEl.classList.add('fading'); }
          if (headerEl) { headerEl.classList.add('faded'); }
        } else {
          _descFadeTimer = setTimeout(function () {
            _descFadeTimer = null;
            _descFaded = true;
            var dEl = frame.querySelector('.vc-nasa-desc');
            var hEl = frame.querySelector('.vc-nasa-header');
            if (dEl)   { dEl.classList.add('fading'); }
            if (hEl)   { hEl.classList.add('faded'); }
          }, fadeDelay);
        }
      }, 0);
    }

    overlay.appendChild(frame);
    root.appendChild(overlay);
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson('/api/nasa');
  }

  // ── Precise cycle scheduling (mirrors news.js fetchDataWithCycling) ────────
  async function fetchDataWithCycling() {
    const data = await fetchData();
    // Schedule the next image transition precisely at ms_until_next
    if (_cycleTimer === null) {
      const ms = (data && data.ms_until_next > 0) ? data.ms_until_next : 60 * 1000;
      _cycleTimer = setTimeout(advanceAndTick, ms);
    }
    return data;
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchDataWithCycling, render: render });
})();

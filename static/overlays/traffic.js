/* Traffic overlay renderer (v2)
 * Renders the full traffic broadcast (map + stats + road overlay) inside the
 * virtual channel by embedding the /traffic standalone page in an iframe.
 * The iframe manages its own Leaflet map, data polling, and city rotation;
 * this renderer only creates it once and uses /api/traffic solely for
 * wall-clock aligned refresh scheduling so city rotation stays in sync
 * across all connected clients.
 */
(function () {
  'use strict';
  const TYPE                = 'traffic';
  const STYLE_ID            = 'vc-traffic-overlay-styles-v2';
  // Must match _TRAFFIC_CACHE_TTL in app.py
  const REFRESH_INTERVAL_MS = 2 * 60 * 1000;

  const CSS = `
    .vc-tf-iframe-wrap {
      position: absolute;
      inset: 0;
    }
    .vc-tf-iframe-wrap iframe {
      width: 100%;
      height: 100%;
      border: none;
      display: block;
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

  // Create the iframe once; no-op if it already exists in root.
  function render(data, root) {
    // Null-safety: root may be absent if called before the DOM is ready.
    if (!root) return;
    // Idempotency: the /traffic page manages its own lifecycle, so don't
    // recreate the iframe on every tick() call.
    if (root.querySelector('.vc-tf-iframe-wrap')) return;
    ensureStyles();
    root.classList.remove('hidden');
    const wrap = document.createElement('div');
    wrap.className = 'vc-overlay vc-tf-iframe-wrap';
    const iframe = document.createElement('iframe');
    iframe.src = '/traffic?embedded=1';
    iframe.setAttribute('allowfullscreen', '');
    wrap.appendChild(iframe);
    root.appendChild(wrap);
  }

  // ── Wall-clock aligned fetch / scheduling ─────────────────────────────────
  // The server returns ms_until_next (time until the next cache-slot boundary)
  // so all clients rotate cities in sync regardless of tune-in time.
  let _cycleTimer = null;

  function advanceAndTick() {
    _cycleTimer = null;
    if (!window.OverlayEngine.isActive(TYPE)) { return; }
    window.OverlayEngine.tick();
  }

  async function fetchData() {
    // Eagerly create the iframe before the first await so the overlay is
    // visible immediately rather than after the API round-trip.
    render(null, document.getElementById('virtual-overlay-root'));
    const data = await window.OverlayEngine.fetchJson('/api/traffic');
    // Schedule next city rotation at the exact wall-clock boundary.
    if (_cycleTimer === null) {
      const msUntilNext = (data.ms_until_next > 0) ? data.ms_until_next : REFRESH_INTERVAL_MS;
      _cycleTimer = setTimeout(advanceAndTick, msUntilNext);
    }
    return data;
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render: render });
})();


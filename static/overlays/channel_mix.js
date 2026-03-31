/* Channel Mix overlay renderer
 * Cycles through configured virtual channels based on wall-clock time.
 * Delegates rendering to each sub-channel's registered renderer.
 * Endpoint: GET /api/channel_mix
 */
(function () {
  'use strict';
  const TYPE    = 'channel_mix';
  const STYLE_ID = 'vc-channel-mix-styles';

  // Map overlay_type → API endpoint for direct data fetching
  const SUB_APIS = {
    news:        '/api/news',
    weather:     '/api/weather',
    traffic:     '/api/traffic',
    status:      '/api/virtual/status',
    sports:      '/api/sports',
    updates:     '/api/virtual/updates',
    nasa:        '/api/nasa',
    on_this_day: '/api/on_this_day',
  };

  const CSS = `
    .vc-cm-frame {
      position: absolute;
      inset: 0;
      background: linear-gradient(160deg, #0a0e2a 0%, #05081a 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: Arial, Helvetica, sans-serif;
      color: #fff;
    }
    .vc-cm-empty {
      color: #4a70ff;
      font-size: 1.1em;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-align: center;
      padding: 1.5em;
    }
    .vc-cm-badge {
      position: absolute;
      bottom: 0.6em;
      right: 0.7em;
      background: rgba(10, 14, 42, 0.82);
      border: 1px solid #4a70ff;
      border-radius: 4px;
      padding: 0.2em 0.55em;
      font-size: 0.72em;
      font-weight: 700;
      color: #c8d8ff;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.1em;
      z-index: 100;
      pointer-events: none;
      transition: opacity 1s ease;
    }
    .vc-cm-badge-label {
      color: #4a70ff;
      font-size: 0.85em;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .vc-cm-badge-channel {
      color: #ffd700;
      font-weight: 900;
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

  // Timer used to trigger a precise re-render exactly when the active channel switches
  let _switchTimer = null;

  // Track the last rendered sub-channel type so we can detect when it changes
  // and notify the guide's fullscreen handler to swap the iframe to the new page.
  let _lastActiveType = null;

  function clearSwitchTimer() {
    if (_switchTimer !== null) {
      clearTimeout(_switchTimer);
      _switchTimer = null;
    }
  }

  // Schedule a precise re-render when the current channel's time slot ends
  function scheduleSwitchAt(secondsRemaining) {
    clearSwitchTimer();
    if (secondsRemaining > 0) {
      _switchTimer = setTimeout(function () {
        _switchTimer = null;
        if (window.OverlayEngine.isActive(TYPE)) {
          window.OverlayEngine.tick();
        }
      }, secondsRemaining * 1000);
    }
  }

  async function fetchData() {
    const mix = await window.OverlayEngine.fetchJson('/api/channel_mix');
    if (!mix || !mix.active_type || !SUB_APIS[mix.active_type]) {
      return { mix: mix, subData: null };
    }
    try {
      const subData = await window.OverlayEngine.fetchJson(SUB_APIS[mix.active_type]);
      return { mix: mix, subData: subData };
    } catch (e) {
      return { mix: mix, subData: null };
    }
  }

  function renderEmpty(root, mixName) {
    ensureStyles();
    root.querySelectorAll('.vc-overlay').forEach(function (e) { e.remove(); });
    root.classList.remove('hidden');
    const overlay = document.createElement('div');
    overlay.className = 'vc-overlay';
    const frame = document.createElement('div');
    frame.className = 'vc-cm-frame';
    frame.innerHTML =
      '<div class="vc-cm-empty">' +
        '&#127902;&nbsp; ' + (mixName || 'Channel Mix') + '<br>' +
        '<span style="font-size:0.8em;color:#4a70ff;font-weight:400;">' +
          'No channels configured &mdash; add channels in Virtual Channels settings.' +
        '</span>' +
      '</div>';
    overlay.appendChild(frame);
    root.appendChild(overlay);
  }

  // Timer for fading the badge after it has been visible long enough
  let _badgeFadeTimer = null;

  function addBadge(root, mix) {
    // Cancel any previous badge fade timer and remove existing badges
    if (_badgeFadeTimer !== null) { clearTimeout(_badgeFadeTimer); _badgeFadeTimer = null; }
    root.querySelectorAll('.vc-cm-badge').forEach(function (b) { b.remove(); });
    const badge = document.createElement('div');
    badge.className = 'vc-cm-badge';
    badge.innerHTML =
      '<span class="vc-cm-badge-label">&#127902; ' + esc(mix.name || 'Channel Mix') + '</span>' +
      '<span class="vc-cm-badge-channel">' + esc(mix.active_name || '') + '</span>';
    root.appendChild(badge);
    // Fade the badge out after 15 seconds
    _badgeFadeTimer = setTimeout(function () {
      _badgeFadeTimer = null;
      if (badge.isConnected) badge.style.opacity = '0';
    }, 15000);
  }

  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function render(data, root) {
    ensureStyles();
    const mix     = data && data.mix;
    const subData = data && data.subData;

    // Expose the active sub-channel type on the root element so the guide's
    // fullscreen handler can load the matching standalone page (same look as
    // when that channel is opened directly in fullscreen).
    if (mix && mix.active_type) {
      root.dataset.cmActiveType = mix.active_type;
    } else {
      delete root.dataset.cmActiveType;
    }

    // When the active sub-channel changes, notify guide.html so that the
    // fullscreen iframe can be swapped to the new sub-channel's standalone page
    // without the user needing to exit and re-enter fullscreen.
    const newActiveType = (mix && mix.active_type) || null;
    if (newActiveType !== _lastActiveType) {
      _lastActiveType = newActiveType;
      if (newActiveType) {
        document.dispatchEvent(new CustomEvent('vc-cm-switched', {
          detail: { activeType: newActiveType },
        }));
      }
    }

    if (!mix || !mix.channels || mix.channels.length === 0) {
      renderEmpty(root, mix && mix.name);
      // Even with no channels, keep polling so we catch when channels get added.
      // Use a 30s fallback since there's no slot time available.
      setTimeout(function () {
        if (window.OverlayEngine.isActive(TYPE)) window.OverlayEngine.tick();
      }, 30000);
      return;
    }

    const subRenderer = mix.active_type
      ? window.OverlayEngine.getRenderer(mix.active_type)
      : null;

    if (subRenderer && subData) {
      // Let the sub-renderer paint the overlay, then overlay our badge on top
      subRenderer.render(subData, root);
      addBadge(root, mix);
    } else {
      // Channel is configured but its data isn't available yet — show a
      // temporary placeholder while cycling continues normally.
      ensureStyles();
      root.querySelectorAll('.vc-overlay').forEach(function (e) { e.remove(); });
      root.classList.remove('hidden');
      const overlay = document.createElement('div');
      overlay.className = 'vc-overlay';
      const frame = document.createElement('div');
      frame.className = 'vc-cm-frame';
      frame.innerHTML =
        '<div class="vc-cm-empty">' +
          '&#127902;&nbsp; ' + esc(mix.active_name || mix.name || 'Channel Mix') + '<br>' +
          '<span style="font-size:0.8em;color:#4a70ff;font-weight:400;">Loading channel data&hellip;</span>' +
        '</div>';
      overlay.appendChild(frame);
      root.appendChild(overlay);
    }

    // Schedule a precise switch at the end of the current channel's slot
    if (mix.seconds_remaining > 0) {
      scheduleSwitchAt(mix.seconds_remaining);
    }
  }

  window.OverlayEngine.register(TYPE, {
    fetch: fetchData,
    render: render,
  });

  // Clean up the switch timer when the overlay engine stops
  window.OverlayEngine.onStop(function () {
    clearSwitchTimer();
    if (_badgeFadeTimer !== null) { clearTimeout(_badgeFadeTimer); _badgeFadeTimer = null; }
    _lastActiveType = null;
    // Remove the active sub-channel hint so stale data is never used
    const root = document.getElementById('virtual-overlay-root');
    if (root) delete root.dataset.cmActiveType;
  });
})();

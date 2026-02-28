// user-prefs.js — Per-user channel preferences for RetroIPTVGuide
// Features:
//   • Auto-load channel: automatically plays a saved channel when the guide opens
//   • Hidden channels:   hides selected channels from the guide grid (right-click to hide)
//   • Sizzle reels:      muted hover preview of a channel stream after a short delay
//
// Prefs are loaded from window.__initialUserPrefs (injected by guide.html) and
// saved back to the server via POST /api/user_prefs.
//
// Public API exposed as window.__userPrefs:
//   .prefs                    — current prefs object
//   .save(patch)              — PATCH prefs on server and apply locally
//   .setAutoLoad()            — set currently-playing channel as auto-load
//   .clearAutoLoad()          — clear auto-load channel
//   .toggleSizzleReels()      — toggle sizzle-reel mode and save
//   .toggleShowHidden()       — toggle visibility of hidden rows in the guide
//   .hideChannel(id)          — add channel to hidden list
//   .unhideChannel(id)        — remove channel from hidden list

(function () {
  'use strict';

  // ─── Constants ────────────────────────────────────────────────────────────
  const WEATHER_CHANNEL_ID  = '__weather__';
  const WEATHER_ZIP_UNSET   = '(not set)';

  // ─── State ────────────────────────────────────────────────────────────────
  let prefs = Object.assign(
    { auto_load_channel: null, hidden_channels: [], sizzle_reels_enabled: false,
      weather_enabled: false, weather_zip: '', weather_units: 'F' },
    (typeof window.__initialUserPrefs === 'object' && window.__initialUserPrefs) || {}
  );
  let showingHidden = false;   // current toggle state for "show hidden channels"
  let sizzleTimer   = null;
  let sizzleHls     = null;
  let sizzleVideo   = null;

  // ─── Helpers ──────────────────────────────────────────────────────────────
  function log() {
    if (window.console && console.debug) {
      console.debug.apply(console, ['[user-prefs]'].concat(Array.from(arguments)));
    }
  }

  /** POST a partial update to the server and merge the returned prefs. */
  async function savePatch(patch) {
    try {
      const res = await fetch('/api/user_prefs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(patch)
      });
      if (!res.ok) { log('save failed', res.status); return; }
      const body = await res.json();
      if (body && body.prefs) {
        prefs = Object.assign(prefs, body.prefs);
      }
    } catch (e) {
      log('save error', e);
    }
  }

  // ─── Hidden channels ──────────────────────────────────────────────────────
  function applyHiddenChannels() {
    const hidden = prefs.hidden_channels || [];
    document.querySelectorAll('.guide-row[data-cid]').forEach(row => {
      const cid = row.dataset.cid;
      // Never apply user-hidden class to the virtual weather channel; it has
      // its own separate weather-ch-hidden toggle.
      if (cid === WEATHER_CHANNEL_ID) return;
      if (hidden.includes(cid)) {
        row.classList.add('chan-hidden');
      } else {
        row.classList.remove('chan-hidden');
      }
    });
  }

  function syncShowHiddenButton() {
    const label = showingHidden ? '🙈 Hide Hidden Channels' : '👁 Show Hidden Channels';
    ['toggleShowHidden', 'mobileToggleShowHidden'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = label;
    });
  }

  function toggleShowHidden() {
    showingHidden = !showingHidden;
    document.querySelectorAll('.guide-row.chan-hidden').forEach(row => {
      row.classList.toggle('chan-hidden-visible', showingHidden);
    });
    syncShowHiddenButton();
  }

  async function hideChannel(cid) {
    if (!cid) return;
    const hidden = prefs.hidden_channels || [];
    if (!hidden.includes(cid)) {
      const next = hidden.concat([cid]);
      await savePatch({ hidden_channels: next });
      applyHiddenChannels();
    }
    log('hidden channel', cid);
  }

  async function unhideChannel(cid) {
    if (!cid) return;
    const next = (prefs.hidden_channels || []).filter(id => id !== cid);
    await savePatch({ hidden_channels: next });
    applyHiddenChannels();
    log('unhidden channel', cid);
  }

  // ─── Auto-load channel ────────────────────────────────────────────────────
  function syncAutoLoadButton() {
    const al = prefs.auto_load_channel;
    const label = al ? `Auto-Load: ${al.name}` : 'Set Auto-Load Channel';
    const showClear = !!al;

    ['setAutoLoadChannel', 'mobileSetAutoLoadChannel'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = label;
    });
    ['clearAutoLoadChannel', 'mobileClearAutoLoadChannel'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.style.display = showClear ? '' : 'none';
    });
  }

  /** Mark channel rows that are the current auto-load channel. */
  function applyAutoLoadMarker() {
    document.querySelectorAll('.guide-row[data-cid]').forEach(row => {
      row.classList.remove('chan-autoload');
    });
    const al = prefs.auto_load_channel;
    if (al && al.id) {
      const row = document.querySelector(`.guide-row[data-cid="${CSS.escape(al.id)}"]`);
      if (row) row.classList.add('chan-autoload');
    }
  }

  async function setAutoLoad() {
    // Read currently-playing channel (set by guide.html's playChannel())
    const meta = window.currentChannelMeta;
    if (!meta || !meta.id) {
      alert('Please play a channel first, then set it as your Auto-Load Channel.');
      return;
    }
    await savePatch({ auto_load_channel: { id: meta.id, name: meta.name } });
    syncAutoLoadButton();
    applyAutoLoadMarker();
    log('auto-load set to', prefs.auto_load_channel);
  }

  async function clearAutoLoad() {
    await savePatch({ auto_load_channel: null });
    syncAutoLoadButton();
    applyAutoLoadMarker();
    log('auto-load cleared');
  }

  /** Auto-play the saved channel shortly after the guide finishes loading. */
  function scheduleAutoLoad() {
    const al = prefs.auto_load_channel;
    if (!al || !al.id) return;

    function tryPlay() {
      setTimeout(function () {
        // Use dataset comparison instead of CSS.escape-based selector for robustness
        // with channel IDs that contain special characters.
        let chanEl = null;
        document.querySelectorAll('.chan-name').forEach(function (el) {
          if (el.dataset.cid === al.id) chanEl = el;
        });
        if (!chanEl) { log('auto-load channel not found in guide', al.id); return; }
        const url  = chanEl.dataset.url;
        const name = chanEl.dataset.name || al.name;
        if (!url) { log('auto-load channel has no URL'); return; }
        log('auto-loading channel', name);
        if (typeof window.playChannel === 'function') {
          window.playChannel(url, al.id, name);
        }
      }, 800);
    }

    // Always wait for DOMContentLoaded before attempting auto-play so that the
    // page is fully interactive and all deferred scripts have run.
    // When user-prefs.js runs as a defer script, readyState is 'interactive'
    // and DOMContentLoaded is about to fire — adding the listener here fires
    // tryPlay() right after that event, then the 800 ms grace period follows.
    if (document.readyState === 'complete') {
      tryPlay();
    } else {
      document.addEventListener('DOMContentLoaded', tryPlay, { once: true });
    }
  }

  // ─── Sizzle reels ─────────────────────────────────────────────────────────
  function syncSizzleButton() {
    const label = prefs.sizzle_reels_enabled ? '🎬 Sizzle Reels: On' : '🎬 Sizzle Reels: Off';
    ['toggleSizzleReels', 'mobileToggleSizzleReels'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = label;
    });
  }

  async function toggleSizzleReels() {
    await savePatch({ sizzle_reels_enabled: !prefs.sizzle_reels_enabled });
    syncSizzleButton();
    attachSizzleListeners();
    if (!prefs.sizzle_reels_enabled) hideSizzle();
    log('sizzle reels', prefs.sizzle_reels_enabled ? 'enabled' : 'disabled');
  }

  function ensureSizzleVideo() {
    if (sizzleVideo) return;
    sizzleVideo = document.createElement('video');
    sizzleVideo.id = 'sizzle-preview';
    sizzleVideo.muted = true;
    sizzleVideo.autoplay = true;
    sizzleVideo.playsinline = true;
    sizzleVideo.setAttribute('aria-hidden', 'true');
    sizzleVideo.style.cssText = [
      'position:fixed', 'right:12px', 'bottom:64px',
      'width:220px', 'height:124px',
      'background:#000',
      'border:2px solid var(--primary-color,#1ed3ce)',
      'border-radius:6px',
      'z-index:8800',
      'display:none',
      'pointer-events:none'
    ].join(';');
    document.body.appendChild(sizzleVideo);
  }

  function showSizzle(url) {
    ensureSizzleVideo();
    sizzleVideo.style.display = 'block';
    if (sizzleHls) { sizzleHls.destroy(); sizzleHls = null; }
    if (window.Hls && Hls.isSupported()) {
      sizzleHls = new Hls({ maxBufferLength: 8, maxMaxBufferLength: 16 });
      sizzleHls.loadSource(url);
      sizzleHls.attachMedia(sizzleVideo);
    } else {
      sizzleVideo.src = url;
    }
    sizzleVideo.play().catch(function () {});
  }

  function hideSizzle() {
    clearTimeout(sizzleTimer);
    sizzleTimer = null;
    if (sizzleVideo) sizzleVideo.style.display = 'none';
    if (sizzleHls) { sizzleHls.destroy(); sizzleHls = null; }
    if (sizzleVideo) { sizzleVideo.src = ''; }
  }

  function attachSizzleListeners() {
    document.querySelectorAll('.chan-name').forEach(el => {
      // Remove stale listeners by replacing dataset flag
      if (prefs.sizzle_reels_enabled) {
        if (!el.dataset.sizzleAttached) {
          el.dataset.sizzleAttached = '1';
          el.addEventListener('mouseenter', function () {
            if (!prefs.sizzle_reels_enabled) return;
            const url = el.dataset.url;
            if (!url) return;
            sizzleTimer = setTimeout(function () { showSizzle(url); }, 1500);
          });
          el.addEventListener('mouseleave', hideSizzle);
        }
      } else {
        delete el.dataset.sizzleAttached;
      }
    });
  }

  // ─── Weather settings ─────────────────────────────────────────────────────

  /** Show/hide the virtual Channel 1 row based on weather_enabled pref. */
  function applyWeatherEnabled() {
    const enabled = !!prefs.weather_enabled;
    document.querySelectorAll('.guide-row[data-cid="' + WEATHER_CHANNEL_ID + '"]').forEach(function (row) {
      row.classList.toggle('weather-ch-hidden', !enabled);
    });
  }

  function syncWeatherButton() {
    const enabled = !!prefs.weather_enabled;
    const zip = prefs.weather_zip || WEATHER_ZIP_UNSET;
    const units = prefs.weather_units || 'F';

    ['toggleWeatherChannel', 'mobileToggleWeatherChannel'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = enabled ? '🌤 Weather: On (Click to Disable)' : '🌤 Weather: Off (Click to Enable)';
    });
    ['setWeatherZip', 'mobileSetWeatherZip'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = 'ZIP Code: ' + zip;
    });
    ['setWeatherUnitsF', 'mobileSetWeatherUnitsF'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = units === 'F' ? '✓ °F (Fahrenheit)' : '°F (Fahrenheit)';
    });
    ['setWeatherUnitsC', 'mobileSetWeatherUnitsC'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = units === 'C' ? '✓ °C (Celsius)' : '°C (Celsius)';
    });
  }

  async function toggleWeatherChannel() {
    await savePatch({ weather_enabled: !prefs.weather_enabled });
    syncWeatherButton();
    applyWeatherEnabled();
    log('weather channel', prefs.weather_enabled ? 'enabled' : 'disabled');
  }

  async function setWeatherZip() {
    const zip = prompt('Enter your ZIP code for weather:', prefs.weather_zip || '');
    if (zip === null) return;
    await savePatch({ weather_zip: zip.trim() });
    syncWeatherButton();
    log('weather zip set to', prefs.weather_zip);
  }

  async function setWeatherUnitsF() {
    await savePatch({ weather_units: 'F' });
    syncWeatherButton();
    log('weather units set to F');
  }

  async function setWeatherUnitsC() {
    await savePatch({ weather_units: 'C' });
    syncWeatherButton();
    log('weather units set to C');
  }

  // ─── Right-click context menu ──────────────────────────────────────────────
  let ctxMenu = null;
  let ctxTarget = null;   // the .chan-name element that was right-clicked

  function createContextMenu() {
    const menu = document.createElement('div');
    menu.id = 'chan-ctx-menu';
    menu.setAttribute('role', 'menu');
    menu.style.cssText = [
      'position:fixed',
      'z-index:9500',
      'background:var(--dropdown-bg,#1a1a1a)',
      'color:var(--panel-text,#eee)',
      'border:1px solid rgba(255,255,255,0.12)',
      'border-radius:7px',
      'padding:5px 0',
      'min-width:200px',
      'box-shadow:0 6px 20px rgba(0,0,0,0.5)',
      'display:none',
      'font-size:0.93rem'
    ].join(';');

    function item(id, text) {
      const d = document.createElement('div');
      d.id = id;
      d.setAttribute('role', 'menuitem');
      d.setAttribute('tabindex', '0');
      d.textContent = text;
      d.style.cssText = 'padding:8px 14px;cursor:pointer;white-space:nowrap';
      d.addEventListener('mouseover', function () { d.style.background = 'rgba(30,211,206,0.15)'; });
      d.addEventListener('mouseout',  function () { d.style.background = ''; });
      return d;
    }

    menu.appendChild(item('ctxPlay',      '▶  Play Channel'));
    menu.appendChild(item('ctxAutoLoad',  'Set as Auto-Load Channel'));
    menu.appendChild(item('ctxHide',      '🙈 Hide Channel'));
    menu.appendChild(item('ctxUnhide',    '👁  Unhide Channel'));

    document.body.appendChild(menu);

    menu.querySelector('#ctxPlay').addEventListener('click', function () {
      closeCtxMenu();
      if (!ctxTarget) return;
      if (typeof window.playChannel === 'function') {
        window.playChannel(ctxTarget.dataset.url, ctxTarget.dataset.cid, ctxTarget.dataset.name);
      }
    });
    menu.querySelector('#ctxAutoLoad').addEventListener('click', async function () {
      closeCtxMenu();
      if (!ctxTarget) return;
      await savePatch({ auto_load_channel: { id: ctxTarget.dataset.cid, name: ctxTarget.dataset.name } });
      syncAutoLoadButton();
      applyAutoLoadMarker();
    });
    menu.querySelector('#ctxHide').addEventListener('click', async function () {
      closeCtxMenu();
      if (ctxTarget) await hideChannel(ctxTarget.dataset.cid);
    });
    menu.querySelector('#ctxUnhide').addEventListener('click', async function () {
      closeCtxMenu();
      if (ctxTarget) await unhideChannel(ctxTarget.dataset.cid);
    });

    return menu;
  }

  function openCtxMenu(x, y, chanEl) {
    if (!ctxMenu) ctxMenu = createContextMenu();
    ctxTarget = chanEl;
    const cid = chanEl.dataset.cid;
    const isWeather = (cid === WEATHER_CHANNEL_ID);
    const isHidden = !isWeather && (prefs.hidden_channels || []).includes(cid);
    // Hide/Unhide actions are not available for the virtual weather channel
    ctxMenu.querySelector('#ctxHide').style.display   = (isWeather || isHidden) ? 'none' : '';
    ctxMenu.querySelector('#ctxUnhide').style.display = (!isWeather && isHidden) ? '' : 'none';

    ctxMenu.style.display = 'block';
    // Keep within viewport
    const menuW = 210, menuH = 140;
    const left = (x + menuW > window.innerWidth)  ? (x - menuW) : x;
    const top  = (y + menuH > window.innerHeight) ? (y - menuH) : y;
    ctxMenu.style.left = left + 'px';
    ctxMenu.style.top  = top  + 'px';
  }

  function closeCtxMenu() {
    if (ctxMenu) ctxMenu.style.display = 'none';
    ctxTarget = null;
  }

  // ─── Init ──────────────────────────────────────────────────────────────────
  function init() {
    applyHiddenChannels();
    applyAutoLoadMarker();
    applyWeatherEnabled();
    syncAutoLoadButton();
    syncSizzleButton();
    syncShowHiddenButton();
    syncWeatherButton();
    scheduleAutoLoad();

    if (prefs.sizzle_reels_enabled) {
      attachSizzleListeners();
    }

    // Wire Settings-menu buttons (desktop + mobile, present in _header.html)
    function wire(id, fn) {
      const el = document.getElementById(id);
      if (el) el.addEventListener('click', function (e) { e.preventDefault(); fn(); });
    }
    wire('setAutoLoadChannel',         setAutoLoad);
    wire('clearAutoLoadChannel',       clearAutoLoad);
    wire('toggleSizzleReels',          toggleSizzleReels);
    wire('toggleShowHidden',           toggleShowHidden);
    wire('mobileSetAutoLoadChannel',   setAutoLoad);
    wire('mobileClearAutoLoadChannel', clearAutoLoad);
    wire('mobileToggleSizzleReels',    toggleSizzleReels);
    wire('mobileToggleShowHidden',     toggleShowHidden);
    wire('toggleWeatherChannel',       toggleWeatherChannel);
    wire('setWeatherZip',              setWeatherZip);
    wire('setWeatherUnitsF',           setWeatherUnitsF);
    wire('setWeatherUnitsC',           setWeatherUnitsC);
    wire('mobileToggleWeatherChannel', toggleWeatherChannel);
    wire('mobileSetWeatherZip',        setWeatherZip);
    wire('mobileSetWeatherUnitsF',     setWeatherUnitsF);
    wire('mobileSetWeatherUnitsC',     setWeatherUnitsC);

    // Right-click context menu on channel names
    document.querySelectorAll('.chan-name').forEach(function (el) {
      el.addEventListener('contextmenu', function (e) {
        e.preventDefault();
        openCtxMenu(e.clientX, e.clientY, el);
      });
    });

    // Close context menu on outside click / scroll / Escape
    document.addEventListener('click', function (e) {
      if (ctxMenu && !ctxMenu.contains(e.target)) closeCtxMenu();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeCtxMenu();
    });
    document.addEventListener('scroll', closeCtxMenu, true);
  }

  // ─── Public API ───────────────────────────────────────────────────────────
  window.__userPrefs = {
    get prefs() { return prefs; },
    save:                 savePatch,
    setAutoLoad:          setAutoLoad,
    clearAutoLoad:        clearAutoLoad,
    toggleSizzleReels:    toggleSizzleReels,
    toggleShowHidden:     toggleShowHidden,
    hideChannel:          hideChannel,
    unhideChannel:        unhideChannel,
    toggleWeatherChannel: toggleWeatherChannel,
    setWeatherZip:        setWeatherZip,
    setWeatherUnitsF:     setWeatherUnitsF,
    setWeatherUnitsC:     setWeatherUnitsC,
  };

  // Bootstrap when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

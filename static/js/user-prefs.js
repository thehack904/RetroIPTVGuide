// user-prefs.js — Per-user channel preferences for RetroIPTVGuide
// Features:
//   • Auto-load channel: automatically plays a saved channel when the guide opens
//   • Hidden channels:   hides selected channels from the guide grid (right-click to hide)
//   • Favorite channels: marks favorite channels with a star; optional filter to show only favorites
//
// Prefs are loaded from window.__initialUserPrefs (injected by guide.html) and
// saved back to the server via POST /api/user_prefs.
//
// Public API exposed as window.__userPrefs:
//   .prefs                    — current prefs object
//   .save(patch)              — PATCH prefs on server and apply locally
//   .setAutoLoad()            — set currently-playing channel as auto-load
//   .clearAutoLoad()          — clear auto-load channel
//   .toggleShowHidden()       — toggle visibility of hidden rows in the guide
//   .hideChannel(id)          — add channel to hidden list
//   .unhideChannel(id)        — remove channel from hidden list
//   .addFavorite(id)          — add channel to favorites list
//   .removeFavorite(id)       — remove channel from favorites list
//   .toggleShowFavoritesOnly() — toggle guide filter to show only favorite channels

(function () {
  'use strict';

  // ─── State ────────────────────────────────────────────────────────────────
  let prefs = Object.assign(
    { auto_load_channel: null, hidden_channels: [], favorite_channels: [], channel_numbers_enabled: false },
    (typeof window.__initialUserPrefs === 'object' && window.__initialUserPrefs) || {}
  );
  let showingHidden = false;   // current toggle state for "show hidden channels"
  let showingFavoritesOnly = false; // current toggle state for "show favorites only"
  let channelNumberReapplyQueued = false;
  const CHANNEL_NUMBER_PREFIX = 'CH ';
  const THEMES_WITH_BUILT_IN_CHANNEL_NUMBERS = ['tvguide1990', 'classic-cable'];

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

  // ─── Favorite channels ────────────────────────────────────────────────────
  function applyFavoriteChannels() {
    const favorites = prefs.favorite_channels || [];
    document.querySelectorAll('.guide-row[data-cid]').forEach(row => {
      const cid = row.dataset.cid;
      if (favorites.includes(cid)) {
        row.classList.add('chan-favorite');
      } else {
        row.classList.remove('chan-favorite');
      }
    });
  }

  function syncShowFavoritesButton() {
    const label = showingFavoritesOnly ? '⭐ Show All Channels' : '⭐ Show Favorites Only';
    ['toggleShowFavoritesOnly', 'mobileToggleShowFavoritesOnly'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = label;
    });
  }

  function toggleShowFavoritesOnly() {
    showingFavoritesOnly = !showingFavoritesOnly;
    document.body.classList.toggle('favorites-only', showingFavoritesOnly);
    syncShowFavoritesButton();
  }

  async function addFavorite(cid) {
    if (!cid) return;
    const favorites = prefs.favorite_channels || [];
    if (!favorites.includes(cid)) {
      const next = favorites.concat([cid]);
      await savePatch({ favorite_channels: next });
      applyFavoriteChannels();
    }
    log('added favorite', cid);
  }

  async function removeFavorite(cid) {
    if (!cid) return;
    const next = (prefs.favorite_channels || []).filter(id => id !== cid);
    await savePatch({ favorite_channels: next });
    applyFavoriteChannels();
    log('removed favorite', cid);
  }

  // ─── Channel numbers toggle ────────────────────────────────────────────────
  function isThemeWithBuiltInChannelNumbers() {
    return THEMES_WITH_BUILT_IN_CHANNEL_NUMBERS.some(function (theme) {
      return document.body.classList.contains(theme);
    });
  }

  function removeUserChannelNumbers() {
    document.querySelectorAll('.chan-name .user-channel-number').forEach(function (el) {
      el.remove();
    });
  }

  function addUserChannelNumbers() {
    var channelEls = Array.from(document.querySelectorAll('.guide-row[data-cid] .chan-name')).filter(function (el) {
      return !el.closest('.__auto_scroll_clone');
    });
    removeUserChannelNumbers();
    channelEls.forEach(function (el, idx) {
      if (el.querySelector('.channel-number')) return;
      var num = document.createElement('span');
      num.className = 'user-channel-number';
      num.textContent = CHANNEL_NUMBER_PREFIX + String(idx + 1);
      el.insertBefore(num, el.firstChild);
    });
  }

  function applyChannelNumbersPreference() {
    const shouldShow = !!prefs.channel_numbers_enabled && !isThemeWithBuiltInChannelNumbers();
    if (shouldShow) {
      addUserChannelNumbers();
    } else {
      removeUserChannelNumbers();
    }
  }

  function scheduleChannelNumbersReapply() {
    if (channelNumberReapplyQueued) return;
    channelNumberReapplyQueued = true;
    var run = function () {
      channelNumberReapplyQueued = false;
      if (!prefs.channel_numbers_enabled || isThemeWithBuiltInChannelNumbers()) return;
      applyChannelNumbersPreference();
    };
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(run);
    } else {
      setTimeout(run, 0);
    }
  }

  function syncChannelNumbersButton() {
    const hidden = isThemeWithBuiltInChannelNumbers();
    const enabled = !!prefs.channel_numbers_enabled;
    const label = enabled ? '🔢 Hide Channel Numbers' : '🔢 Show Channel Numbers';
    ['toggleChannelNumbers', 'mobileToggleChannelNumbers'].forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.style.display = hidden ? 'none' : '';
      el.textContent = label;
    });
  }

  async function toggleChannelNumbers() {
    if (isThemeWithBuiltInChannelNumbers()) return;
    prefs.channel_numbers_enabled = !prefs.channel_numbers_enabled;
    await savePatch({ channel_numbers_enabled: !!prefs.channel_numbers_enabled });
    syncChannelNumbersButton();
    applyChannelNumbersPreference();
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
        const isVirtual = chanEl.dataset.isVirtual === 'true';
        if (!url && !isVirtual) { log('auto-load channel has no URL'); return; }
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

    menu.appendChild(item('ctxPlay',       '▶  Play Channel'));
    menu.appendChild(item('ctxAutoLoad',   'Set as Auto-Load Channel'));
    menu.appendChild(item('ctxFavorite',   '⭐ Add to Favorites'));
    menu.appendChild(item('ctxUnfavorite', '✖  Remove from Favorites'));
    menu.appendChild(item('ctxHide',       '🙈 Hide Channel'));
    menu.appendChild(item('ctxUnhide',     '👁  Unhide Channel'));

    document.body.appendChild(menu);

    menu.querySelector('#ctxPlay').addEventListener('click', function () {
      const tgt = ctxTarget;
      closeCtxMenu();
      if (!tgt) return;
      if (typeof window.playChannel === 'function') {
        window.playChannel(tgt.dataset.url, tgt.dataset.cid, tgt.dataset.name);
      }
    });
    menu.querySelector('#ctxAutoLoad').addEventListener('click', async function () {
      const tgt = ctxTarget;
      closeCtxMenu();
      if (!tgt) return;
      await savePatch({ auto_load_channel: { id: tgt.dataset.cid, name: tgt.dataset.name } });
      syncAutoLoadButton();
      applyAutoLoadMarker();
    });
    menu.querySelector('#ctxHide').addEventListener('click', async function () {
      const cid = ctxTarget ? ctxTarget.dataset.cid : null;
      closeCtxMenu();
      if (cid) await hideChannel(cid);
    });
    menu.querySelector('#ctxUnhide').addEventListener('click', async function () {
      const cid = ctxTarget ? ctxTarget.dataset.cid : null;
      closeCtxMenu();
      if (cid) await unhideChannel(cid);
    });
    menu.querySelector('#ctxFavorite').addEventListener('click', async function () {
      const cid = ctxTarget ? ctxTarget.dataset.cid : null;
      closeCtxMenu();
      if (cid) await addFavorite(cid);
    });
    menu.querySelector('#ctxUnfavorite').addEventListener('click', async function () {
      const cid = ctxTarget ? ctxTarget.dataset.cid : null;
      closeCtxMenu();
      if (cid) await removeFavorite(cid);
    });

    return menu;
  }

  function openCtxMenu(x, y, chanEl) {
    if (!ctxMenu) ctxMenu = createContextMenu();
    ctxTarget = chanEl;
    const cid = chanEl.dataset.cid;
    const isHidden   = (prefs.hidden_channels   || []).includes(cid);
    const isFavorite = (prefs.favorite_channels || []).includes(cid);
    ctxMenu.querySelector('#ctxHide').style.display        = isHidden   ? 'none' : '';
    ctxMenu.querySelector('#ctxUnhide').style.display      = isHidden   ? ''     : 'none';
    ctxMenu.querySelector('#ctxFavorite').style.display    = isFavorite ? 'none' : '';
    ctxMenu.querySelector('#ctxUnfavorite').style.display  = isFavorite ? ''     : 'none';

    ctxMenu.style.display = 'block';
    // Keep within viewport
    const menuW = 210, menuH = 180;
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
    applyFavoriteChannels();
    applyAutoLoadMarker();
    syncAutoLoadButton();
    syncShowHiddenButton();
    syncShowFavoritesButton();
    syncChannelNumbersButton();
    applyChannelNumbersPreference();
    scheduleAutoLoad();

    // Wire Settings-menu buttons (desktop + mobile, present in _header.html)
    function wire(id, fn) {
      const el = document.getElementById(id);
      if (el) el.addEventListener('click', function (e) { e.preventDefault(); fn(); });
    }
    wire('setAutoLoadChannel',           setAutoLoad);
    wire('clearAutoLoadChannel',         clearAutoLoad);
    wire('toggleShowHidden',             toggleShowHidden);
    wire('toggleShowFavoritesOnly',      toggleShowFavoritesOnly);
    wire('mobileSetAutoLoadChannel',     setAutoLoad);
    wire('mobileClearAutoLoadChannel',   clearAutoLoad);
    wire('mobileToggleShowHidden',       toggleShowHidden);
    wire('mobileToggleShowFavoritesOnly', toggleShowFavoritesOnly);
    wire('toggleChannelNumbers',         toggleChannelNumbers);
    wire('mobileToggleChannelNumbers',   toggleChannelNumbers);

    window.addEventListener('theme:applied', function () {
      syncChannelNumbersButton();
      applyChannelNumbersPreference();
    });

    var guideOuter = document.getElementById('guideOuter');
    if (guideOuter && typeof MutationObserver === 'function') {
      var rowObserver = new MutationObserver(function () {
        scheduleChannelNumbersReapply();
      });
      rowObserver.observe(guideOuter, { childList: true });
    }

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
    save:                  savePatch,
    setAutoLoad:           setAutoLoad,
    clearAutoLoad:         clearAutoLoad,
    toggleShowHidden:      toggleShowHidden,
    hideChannel:           hideChannel,
    unhideChannel:         unhideChannel,
    addFavorite:           addFavorite,
    removeFavorite:        removeFavorite,
    toggleShowFavoritesOnly: toggleShowFavoritesOnly,
    toggleChannelNumbers:  toggleChannelNumbers
  };

  // Bootstrap when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

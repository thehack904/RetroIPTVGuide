// reminders.js — Program reminders / browser notifications for RetroIPTVGuide
//
// Lets users set a reminder on any upcoming program in the guide grid.
// When the program is about to start (configurable minutes in advance),
// the browser fires a native Notification.
//
// Usage:
//   • Right-click any future .program block → "🔔 Set Reminder" (or remove)
//   • Click the 🔔 Reminders button in the header to view / manage reminders
//
// Reminders are persisted server-side in user prefs (key "reminders") via
// POST /api/user_prefs and are loaded from window.__initialUserPrefs.
//
// Public API exposed as window.__reminders:
//   .list()           — returns copy of current reminders array
//   .open()           — opens the reminders panel
//   .close()          — closes the reminders panel

(function () {
  'use strict';

  var POLL_MS            = 30 * 1000;   // check every 30 s
  var DEFAULT_NOTIFY_BEFORE = 5;        // minutes before program start
  var FIRED_KEY          = 'reminders_fired'; // sessionStorage key for fired IDs
  var _timer             = null;
  var _panel             = null;

  // ─── State ────────────────────────────────────────────────────────────────
  var _reminders = [];  // [{id, channel_id, channel_name, program_title, program_start, notify_before_mins}]

  // Load initial state from server-injected prefs
  (function () {
    var ip = (typeof window.__initialUserPrefs === 'object' && window.__initialUserPrefs) || {};
    var saved = ip.reminders;
    if (Array.isArray(saved)) _reminders = saved.slice();
  }());

  // ─── Helpers ──────────────────────────────────────────────────────────────
  function log() {
    if (window.console && console.debug) {
      console.debug.apply(console, ['[reminders]'].concat(Array.from(arguments)));
    }
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function uniqueId() {
    return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  /** Return the set of already-fired reminder IDs for this session. */
  function firedSet() {
    try {
      return new Set(JSON.parse(sessionStorage.getItem(FIRED_KEY) || '[]'));
    } catch (e) {
      return new Set();
    }
  }

  /** Mark a reminder ID as fired in sessionStorage. */
  function markFired(id) {
    try {
      var s = firedSet();
      s.add(id);
      sessionStorage.setItem(FIRED_KEY, JSON.stringify(Array.from(s)));
    } catch (e) { /* ignore */ }
  }

  // ─── Server persistence ───────────────────────────────────────────────────
  async function persist() {
    try {
      await fetch('/api/user_prefs', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reminders: _reminders })
      });
    } catch (e) {
      log('persist failed', e);
    }
  }

  // ─── Notification permission ───────────────────────────────────────────────
  /** Request browser notification permission if not already granted.
   *  Returns a Promise that resolves to true if permission is granted. */
  function requestPermission() {
    if (!('Notification' in window)) return Promise.resolve(false);
    if (Notification.permission === 'granted') return Promise.resolve(true);
    if (Notification.permission === 'denied')  return Promise.resolve(false);
    return Notification.requestPermission().then(function (p) {
      return p === 'granted';
    });
  }

  // ─── Reminder CRUD ────────────────────────────────────────────────────────
  async function addReminder(channelId, channelName, programTitle, programStart, notifyBeforeMins) {
    // Remove any existing reminder for the same program/channel
    _reminders = _reminders.filter(function (r) {
      return !(r.channel_id === channelId && r.program_start === programStart);
    });
    _reminders.push({
      id:               uniqueId(),
      channel_id:       channelId,
      channel_name:     channelName,
      program_title:    programTitle,
      program_start:    programStart,
      notify_before_mins: notifyBeforeMins
    });
    await persist();
    applyBellMarkers();
    renderPanel();
    log('added reminder for', programTitle);
  }

  async function removeReminder(id) {
    _reminders = _reminders.filter(function (r) { return r.id !== id; });
    await persist();
    applyBellMarkers();
    renderPanel();
    log('removed reminder', id);
  }

  /** Check if a reminder is already set for a given channel+programStart. */
  function hasReminder(channelId, programStart) {
    return _reminders.some(function (r) {
      return r.channel_id === channelId && r.program_start === programStart;
    });
  }

  // ─── Bell markers ─────────────────────────────────────────────────────────
  /** Annotate .program elements that have an active reminder with a bell icon. */
  function applyBellMarkers() {
    // Build a lookup: "channelId|programStart" → true
    var lookup = {};
    _reminders.forEach(function (r) {
      lookup[r.channel_id + '|' + r.program_start] = true;
    });

    document.querySelectorAll('.guide-row[data-cid] .program').forEach(function (prog) {
      var row = prog.closest('.guide-row[data-cid]');
      if (!row) return;
      var cid   = row.dataset.cid || '';
      var start = prog.dataset.start || '';
      var key   = cid + '|' + start;
      var bell  = prog.querySelector('.reminder-bell');

      if (lookup[key]) {
        if (!bell) {
          bell = document.createElement('span');
          bell.className = 'reminder-bell';
          bell.setAttribute('aria-label', 'Reminder set');
          bell.textContent = '🔔';
          prog.appendChild(bell);
        }
      } else {
        if (bell) bell.parentNode.removeChild(bell);
      }
    });
  }

  // ─── Polling / notification firing ────────────────────────────────────────
  function checkReminders() {
    if (!_reminders.length) return;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;

    var now    = Date.now();
    var fired  = firedSet();

    _reminders.forEach(function (r) {
      if (fired.has(r.id)) return;
      var start     = new Date(r.program_start).getTime();
      var notifyAt  = start - (r.notify_before_mins || 0) * 60 * 1000;
      if (now >= notifyAt && now < start + 5 * 60 * 1000) {
        // Fire the notification
        markFired(r.id);
        var notifyBefore = r.notify_before_mins || 0;
        var body = notifyBefore > 0
          ? 'Starts in ' + notifyBefore + ' min on ' + r.channel_name
          : 'Now starting on ' + r.channel_name;
        try {
          var n = new Notification('📺 ' + r.program_title, {
            body: body,
            icon: '/static/logo.png',
            tag:  'reminder-' + r.id
          });
          n.onclick = function () {
            window.focus();
            n.close();
          };
        } catch (e) {
          log('notification failed', e);
        }
        log('fired notification for', r.program_title);
      }
    });
  }

  function startPolling() {
    if (_timer !== null) return;
    _timer = setInterval(checkReminders, POLL_MS);
    checkReminders();  // run immediately on start
  }

  // ─── Reminder panel ───────────────────────────────────────────────────────
  function ensurePanel() {
    if (_panel) return _panel;

    _panel = document.createElement('div');
    _panel.id = 'reminders-panel';
    _panel.setAttribute('role', 'dialog');
    _panel.setAttribute('aria-modal', 'true');
    _panel.setAttribute('aria-label', 'Reminders');
    _panel.style.cssText = [
      'position:fixed', 'top:60px', 'right:12px',
      'z-index:9600',
      'background:var(--panel-bg,#1a1a1a)',
      'color:var(--panel-text,#eee)',
      'border:1px solid rgba(255,255,255,0.14)',
      'border-radius:9px',
      'padding:14px 16px',
      'min-width:280px', 'max-width:360px',
      'max-height:70vh', 'overflow-y:auto',
      'box-shadow:0 8px 28px rgba(0,0,0,0.55)',
      'display:none',
      'font-size:0.93rem'
    ].join(';');

    document.body.appendChild(_panel);
    return _panel;
  }

  function renderPanel() {
    var panel = ensurePanel();
    var html = '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
      + '<strong style="font-size:1.05rem;">🔔 Reminders</strong>'
      + '<button id="reminders-panel-close" aria-label="Close reminders panel" '
      + 'style="background:none;border:none;color:inherit;font-size:1.2rem;cursor:pointer;padding:0 2px;">✕</button>'
      + '</div>';

    if (_reminders.length === 0) {
      html += '<p style="color:var(--panel-muted,#888);margin:0;">No reminders set.<br>'
        + '<small>Right-click a future program in the guide to add one.</small></p>';
    } else {
      html += '<ul style="list-style:none;margin:0;padding:0;">';
      _reminders.slice().sort(function (a, b) {
        return new Date(a.program_start) - new Date(b.program_start);
      }).forEach(function (r) {
        var startDate = new Date(r.program_start);
        var timeStr   = isNaN(startDate) ? r.program_start
          : startDate.toLocaleDateString([], {month:'short', day:'numeric'})
            + ' ' + startDate.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
        var notifyLabel = r.notify_before_mins > 0
          ? ' (' + r.notify_before_mins + ' min before)'
          : ' (at start)';
        html += '<li style="display:flex;align-items:flex-start;gap:8px;padding:7px 0;'
          + 'border-bottom:1px solid rgba(255,255,255,0.07);">'
          + '<div style="flex:1;min-width:0;">'
          + '<div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
          + esc(r.program_title) + '</div>'
          + '<div style="font-size:0.82rem;color:var(--panel-muted,#888);">'
          + esc(r.channel_name) + ' · ' + esc(timeStr) + esc(notifyLabel)
          + '</div>'
          + '</div>'
          + '<button data-remove-id="' + esc(r.id) + '" aria-label="Remove reminder for ' + esc(r.program_title) + '" '
          + 'style="background:none;border:none;color:#e55;font-size:1rem;cursor:pointer;padding:0 2px;flex-shrink:0;">🗑</button>'
          + '</li>';
      });
      html += '</ul>';
    }

    panel.innerHTML = html;

    var closeBtn = panel.querySelector('#reminders-panel-close');
    if (closeBtn) closeBtn.addEventListener('click', closePanel);

    panel.querySelectorAll('[data-remove-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        removeReminder(btn.dataset.removeId);
      });
    });
  }

  function openPanel() {
    renderPanel();
    var panel = ensurePanel();
    panel.style.display = 'block';
    syncBellButton();
  }

  function closePanel() {
    if (_panel) _panel.style.display = 'none';
    syncBellButton();
  }

  function isPanelOpen() {
    return _panel && _panel.style.display !== 'none';
  }

  function togglePanel() {
    if (isPanelOpen()) closePanel(); else openPanel();
  }

  // ─── Header bell button state ──────────────────────────────────────────────
  function syncBellButton() {
    var count = _reminders.length;
    var label = count > 0 ? '🔔 Reminders (' + count + ')' : '🔔 Reminders';
    ['remindersBtn', 'mobileRemindersBtn'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = label;
    });
  }

  // ─── Program right-click context menu ────────────────────────────────────
  var _progCtxMenu   = null;
  var _progCtxTarget = null;   // the .program element that was right-clicked

  function createProgCtxMenu() {
    var menu = document.createElement('div');
    menu.id = 'prog-ctx-menu';
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
      var d = document.createElement('div');
      d.id = id;
      d.setAttribute('role', 'menuitem');
      d.setAttribute('tabindex', '0');
      d.textContent = text;
      d.style.cssText = 'padding:8px 14px;cursor:pointer;white-space:nowrap';
      d.addEventListener('mouseover', function () { d.style.background = 'rgba(30,211,206,0.15)'; });
      d.addEventListener('mouseout',  function () { d.style.background = ''; });
      return d;
    }

    menu.appendChild(item('progCtxSetReminder',    '🔔 Set Reminder (5 min before)'));
    menu.appendChild(item('progCtxRemoveReminder', '🔕 Remove Reminder'));

    document.body.appendChild(menu);

    menu.querySelector('#progCtxSetReminder').addEventListener('click', async function () {
      var tgt = _progCtxTarget;
      closeProgCtxMenu();
      if (!tgt) return;
      var row = tgt.closest('.guide-row[data-cid]');
      if (!row) return;
      var cid        = row.dataset.cid || '';
      var chanName   = (function () {
        var cn = row.querySelector('.chan-name');
        return cn ? (cn.dataset.name || cn.textContent.trim()) : cid;
      }());
      var title      = tgt.dataset.title || '';
      var start      = tgt.dataset.start || '';
      if (!start) { log('no start time on program'); return; }
      var ok = await requestPermission();
      if (!ok && 'Notification' in window && Notification.permission === 'denied') {
        alert('Browser notifications are blocked for this site. Please allow notifications in your browser settings to receive program reminders.');
        return;
      }
      await addReminder(cid, chanName, title, start, DEFAULT_NOTIFY_BEFORE);
      startPolling();
    });

    menu.querySelector('#progCtxRemoveReminder').addEventListener('click', async function () {
      var tgt = _progCtxTarget;
      closeProgCtxMenu();
      if (!tgt) return;
      var row = tgt.closest('.guide-row[data-cid]');
      if (!row) return;
      var cid   = row.dataset.cid || '';
      var start = tgt.dataset.start || '';
      var r = _reminders.find(function (x) { return x.channel_id === cid && x.program_start === start; });
      if (r) await removeReminder(r.id);
    });

    return menu;
  }

  function openProgCtxMenu(x, y, progEl) {
    if (!_progCtxMenu) _progCtxMenu = createProgCtxMenu();
    _progCtxTarget = progEl;

    var row   = progEl.closest('.guide-row[data-cid]');
    var cid   = row ? row.dataset.cid : '';
    var start = progEl.dataset.start || '';
    var alreadySet = hasReminder(cid, start);

    _progCtxMenu.querySelector('#progCtxSetReminder').style.display    = alreadySet ? 'none' : '';
    _progCtxMenu.querySelector('#progCtxRemoveReminder').style.display = alreadySet ? ''     : 'none';

    // Only show menu for programs that haven't ended yet
    var stop = progEl.dataset.stop ? new Date(progEl.dataset.stop) : null;
    if (stop && stop < new Date()) {
      // Past program — only "remove" makes sense (if set)
      _progCtxMenu.querySelector('#progCtxSetReminder').style.display = 'none';
    }

    _progCtxMenu.style.display = 'block';
    var menuW = 220, menuH = 60;
    var left  = (x + menuW > window.innerWidth)  ? (x - menuW) : x;
    var top   = (y + menuH > window.innerHeight) ? (y - menuH) : y;
    _progCtxMenu.style.left = left + 'px';
    _progCtxMenu.style.top  = top  + 'px';
  }

  function closeProgCtxMenu() {
    if (_progCtxMenu) _progCtxMenu.style.display = 'none';
    _progCtxTarget = null;
  }

  // ─── Attach right-click handlers to program elements ─────────────────────
  function wirePrograms() {
    document.querySelectorAll('.guide-row[data-cid] .program').forEach(function (prog) {
      if (prog.dataset.reminderWired) return;
      prog.dataset.reminderWired = '1';
      prog.addEventListener('contextmenu', function (e) {
        // Don't fire on no-guide placeholders
        if (prog.classList.contains('no-guide')) return;
        if (!prog.dataset.start) return;
        e.preventDefault();
        e.stopPropagation();
        openProgCtxMenu(e.clientX, e.clientY, prog);
      });
    });
  }

  // ─── Init ─────────────────────────────────────────────────────────────────
  function init() {
    syncBellButton();
    applyBellMarkers();

    // Wire header buttons
    function wire(id, fn) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('click', function (e) { e.preventDefault(); fn(); });
    }
    wire('remindersBtn',       togglePanel);
    wire('mobileRemindersBtn', togglePanel);

    // Close panel on outside click
    document.addEventListener('click', function (e) {
      if (_panel && _panel.style.display !== 'none' && !_panel.contains(e.target)) {
        var isBtnClick = (e.target.id === 'remindersBtn' || e.target.id === 'mobileRemindersBtn');
        if (!isBtnClick) closePanel();
      }
      // Close program context menu on outside click
      if (_progCtxMenu && !_progCtxMenu.contains(e.target)) closeProgCtxMenu();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closePanel();
        closeProgCtxMenu();
      }
    });
    document.addEventListener('scroll', closeProgCtxMenu, true);

    // Wire program elements (initial + MutationObserver for guide refreshes)
    wirePrograms();
    var guideOuter = document.getElementById('guideOuter');
    if (guideOuter && typeof MutationObserver === 'function') {
      var obs = new MutationObserver(function () {
        wirePrograms();
        applyBellMarkers();
      });
      obs.observe(guideOuter, { childList: true, subtree: true });
    }

    // Start polling if there are existing reminders and permission is already granted
    if (_reminders.length > 0 && 'Notification' in window && Notification.permission === 'granted') {
      startPolling();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  // ─── Public API ────────────────────────────────────────────────────────────
  window.__reminders = {
    list:  function () { return _reminders.slice(); },
    open:  openPanel,
    close: closePanel
  };
}());

/**
 * tv-remote-nav.js — Fire TV / Android TV DPAD channel navigation (Option A)
 *
 * Activated only when a TV user-agent is detected (AFT, Silk, Android TV, etc.).
 * Provides:
 *   - Up/Down arrow (DPAD) moves selection through channels
 *   - OK / Enter plays the selected channel
 *   - Visible focus highlight always on the selected channel
 *   - Selection scrolls into view on navigation
 *
 * Loaded conditionally from guide.html after TV-UA detection.
 */
(function () {
  'use strict';

  /* ── Inject styles (focus highlight + TV-mode player sizing) ─────────────── */
  var style = document.createElement('style');
  style.textContent = [
    '.chan-name { cursor: pointer; outline: none; }',
    '.chan-name.tv-focused {',
    '  outline: 3px solid #f90 !important;',
    '  outline-offset: -2px;',
    '  background: rgba(255,153,0,0.18) !important;',
    '  box-shadow: 0 0 0 4px rgba(255,153,0,0.25);',
    '  position: relative; z-index: 2;',
    '}',
    /* guide-row highlight is applied via JS to avoid :has() compat issues */
    '.guide-row.tv-focused-row { background: rgba(255,153,0,0.07); }',
    /* ── TV-mode: reduce entire UI proportionally to match 50% player ────── */
    /* Player row */
    'body.tv-mode .player { padding: 6px; gap: 8px; }',
    'body.tv-mode #video  { width: 310px; height: 175px; }',
    'body.tv-mode .summary { font-size: 0.7em; padding: 4px 8px; }',
    'body.tv-mode .summary h3 { font-size: 1em; margin: 0 0 2px; }',
    'body.tv-mode .summary p  { margin: 0; line-height: 1.3; }',
    /* Header */
    'body.tv-mode .header { height: 20px; padding: 0 5px; font-size: 11px; }',
    'body.tv-mode .header .links > a,',
    'body.tv-mode .header .links > .dropdown > .dropbtn,',
    'body.tv-mode .header .links > span,',
    'body.tv-mode .header .links > div { height: 20px; line-height: 20px; }',
    /* Channel column */
    'body.tv-mode { --chan-col-width: 100px; }',
    'body.tv-mode .chan-col { width: 100px; }',
    'body.tv-mode .chan-name { padding: 5px; gap: 3px; font-size: 0.75em; }',
    'body.tv-mode .chan-name img { max-width: 50px; }',
    'body.tv-mode .chan-header { height: 17px; }',
    /* Program grid cells */
    'body.tv-mode .program { height: 24px !important; font-size: 9px; padding: 2px 3px; top: 3px; }',
    'body.tv-mode .time-cell { font-size: 9px; }',
    /* Fixed time bar */
    'body.tv-mode .time-header-fixed { height: 17px; }',
    /* Guide outer: fill space below shorter header+player+timebar (20+175+17+18px padding ≈ 230px) */
    'body.tv-mode .guide-outer { height: calc(100vh - 230px); }'
  ].join('\n');
  document.head.appendChild(style);

  /* ── State ────────────────────────────────────────────────────────────────── */
  var selectedIndex = -1;   // index into chanNames[]
  var chanNames = [];        // live NodeList snapshot, refreshed on demand

  /* ── Helpers ──────────────────────────────────────────────────────────────── */
  function getChannels() {
    // Re-query each time in case the DOM changes (guide refresh, etc.)
    chanNames = Array.from(document.querySelectorAll('.chan-name'));
    return chanNames;
  }

  function clearFocus() {
    document.querySelectorAll('.chan-name.tv-focused').forEach(function (el) {
      el.classList.remove('tv-focused');
      var row = el.closest('.guide-row');
      if (row) row.classList.remove('tv-focused-row');
    });
  }

  function setFocus(index) {
    var channels = getChannels();
    if (!channels.length) return;

    // Clamp index
    if (index < 0) index = 0;
    if (index >= channels.length) index = channels.length - 1;

    clearFocus();
    selectedIndex = index;

    var el = channels[selectedIndex];
    el.classList.add('tv-focused');
    var row = el.closest('.guide-row');
    if (row) row.classList.add('tv-focused-row');

    // Scroll the channel row into view (vertically), without snapping the
    // horizontal scroll position — we only want vertical alignment.
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  function activateSelected() {
    var channels = getChannels();
    if (selectedIndex < 0 || selectedIndex >= channels.length) return;

    var el = channels[selectedIndex];
    // Delegate to the existing click handler wired by guide.html
    el.click();
  }

  /* ── Keyboard handler ─────────────────────────────────────────────────────── */
  function onKeyDown(e) {
    var channels = getChannels();
    if (!channels.length) return;

    switch (e.keyCode) {
      case 38: // ArrowUp  / DPAD Up
        e.preventDefault();
        setFocus(selectedIndex <= 0 ? 0 : selectedIndex - 1);
        break;

      case 40: // ArrowDown / DPAD Down
        e.preventDefault();
        setFocus(selectedIndex < 0 ? 0 : selectedIndex + 1);
        break;

      case 13: // Enter / OK
        e.preventDefault();
        if (selectedIndex < 0) {
          setFocus(0);
        } else {
          activateSelected();
        }
        break;

      default:
        break;
    }
  }

  /* ── Init ─────────────────────────────────────────────────────────────────── */
  function init() {
    var channels = getChannels();
    if (!channels.length) return;

    // Mark body so TV-mode CSS rules apply (player sizing, etc.)
    document.body.classList.add('tv-mode');

    // Sync selectedIndex when a channel element receives native focus.
    channels.forEach(function (el) {
      el.addEventListener('focus', function () {
        var idx = getChannels().indexOf(el);
        if (idx !== -1) {
          clearFocus();
          selectedIndex = idx;
          el.classList.add('tv-focused');
          var row = el.closest('.guide-row');
          if (row) row.classList.add('tv-focused-row');
        }
      });
    });

    // Start with the first channel highlighted.
    setFocus(0);

    document.addEventListener('keydown', onKeyDown);

    console.log('RetroIPTVGuide: TV remote nav active (' + channels.length + ' channels)');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

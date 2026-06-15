/**
 * channel-number-entry.js — Classic TV-style channel number entry
 *
 * When the user presses digit keys (0–9) anywhere in the guide, a retro HUD
 * overlay appears showing the accumulated characters.  After a short idle
 * timeout (1.5 s) the guide scrolls to the matching channel and starts
 * playback.  Pressing Enter/OK confirms immediately; Escape cancels.
 *
 * Sub-channel numbers (e.g. 2.1, 16.5, 31.2) are supported: pressing the
 * period key appends a "." to the buffer so the user can type the full
 * sub-channel designator.
 *
 * Channel numbers are read from the data-chan-num attribute on each
 * .chan-name element (set by guide.html using tvg_chno or a sequential
 * fallback index that matches the tvguide1990 / classic-cable capsule numbers).
 */
(function () {
  'use strict';

  /* ── Configuration ──────────────────────────────────────────────────────── */
  var ENTRY_TIMEOUT_MS = 1500;  // ms after last keypress before auto-navigate
  var MAX_CHARS        = 5;     // longest channel id accepted (e.g. "123.4")

  /* ── State ──────────────────────────────────────────────────────────────── */
  var buffer = '';   // accumulated digit string
  var timer  = null; // auto-navigate timeout handle
  var hudEl  = null; // HUD DOM node (created lazily)

  /* ── Inject HUD styles ──────────────────────────────────────────────────── */
  var style = document.createElement('style');
  style.textContent = [
    '#chan-num-hud {',
    '  position: fixed;',
    '  top: 50%;',
    '  left: 50%;',
    '  transform: translate(-50%, -50%);',
    '  background: rgba(0, 0, 0, 0.88);',
    '  color: #f90;',
    '  font-family: "Courier New", Courier, monospace;',
    '  font-size: clamp(3rem, 8vw, 6rem);',
    '  font-weight: 700;',
    '  letter-spacing: 0.12em;',
    '  padding: 0.25em 0.6em;',
    '  border: 3px solid #f90;',
    '  border-radius: 8px;',
    '  box-shadow: 0 0 28px rgba(255,153,0,0.55), inset 0 0 14px rgba(255,153,0,0.1);',
    '  text-shadow: 0 0 14px #f90;',
    '  z-index: 9998;',
    '  pointer-events: none;',
    '  user-select: none;',
    '  min-width: 2.5em;',
    '  text-align: center;',
    '  display: none;',
    '  opacity: 1;',
    '  transition: opacity 0.3s ease;',
    '}',
    '#chan-num-hud.visible { display: block; }',
    '#chan-num-hud.fading { opacity: 0; }',
    /* label beneath the number */
    '#chan-num-hud .hud-label {',
    '  display: block;',
    '  font-size: 0.3em;',
    '  letter-spacing: 0.2em;',
    '  color: rgba(255,153,0,0.7);',
    '  text-transform: uppercase;',
    '  margin-top: 0.1em;',
    '  text-shadow: none;',
    '}'
  ].join('\n');
  document.head.appendChild(style);

  /* ── HUD helpers ────────────────────────────────────────────────────────── */
  function ensureHud() {
    if (hudEl) return hudEl;
    hudEl = document.createElement('div');
    hudEl.id = 'chan-num-hud';
    hudEl.setAttribute('aria-live', 'assertive');
    hudEl.setAttribute('aria-atomic', 'true');
    hudEl.setAttribute('role', 'status');
    document.body.appendChild(hudEl);
    return hudEl;
  }

  function showHud(digits, label) {
    var el = ensureHud();
    el.textContent = '';

    var numSpan = document.createElement('span');
    numSpan.textContent = digits;
    el.appendChild(numSpan);

    if (label) {
      var lblSpan = document.createElement('span');
      lblSpan.className = 'hud-label';
      lblSpan.textContent = label;
      el.appendChild(lblSpan);
    }

    el.classList.remove('fading');
    el.classList.add('visible');
  }

  function hideHud() {
    if (!hudEl) return;
    hudEl.classList.add('fading');
    setTimeout(function () {
      if (hudEl) hudEl.classList.remove('visible', 'fading');
    }, 300);
  }

  /* ── Channel index ──────────────────────────────────────────────────────── */
  /**
   * Build a map of channel-number → .chan-name element.
   * Primary keys come from data-chan-num (set by the template); secondary keys
   * include the visible row index (1-based), so users can also jump by the
   * displayed sequence when virtual channels shift row positions.
   * Excludes elements inside auto-scroll clones so duplicate DOM nodes don't
   * shadow the originals.
   */
  function buildIndex() {
    var index = {};
    var els = Array.from(document.querySelectorAll('.chan-name')).filter(function (el) {
      // Skip cloned rows used by the auto-scroll module
      return !el.closest('.__auto_scroll_clone');
    });

    function setPrimary(num, el) {
      if (!num) return;
      if (!index[num]) {
        index[num] = el;
        return;
      }
      var existing = index[num];
      var existingIsVirtual = existing.dataset.isVirtual === 'true';
      var candidateIsVirtual = el.dataset.isVirtual === 'true';
      if (candidateIsVirtual && !existingIsVirtual) index[num] = el;
    }

    // Pass 1: explicit channel numbers (including decimals like 2.1)
    els.forEach(function (el) {
      var num = (el.dataset.chanNum || '').trim();
      setPrimary(num, el);
    });

    // Pass 2: sequential row numbers, used as fallback aliases
    els.forEach(function (el, i) {
      var seqNum = String(i + 1);
      if (!index[seqNum]) index[seqNum] = el;
    });

    return index;
  }

  /* ── Navigation ─────────────────────────────────────────────────────────── */
  function navigate() {
    var digits = buffer;
    reset(/* keepHud= */ true);

    var index = buildIndex();
    var target = index[digits];

    if (!target) {
      // Channel not found — flash an error label then dismiss
      showHud(digits, 'not found');
      setTimeout(hideHud, 900);
      return;
    }

    hideHud();

    // Scroll the channel row into view
    target.scrollIntoView({ block: 'center', behavior: 'smooth' });

    // Give the browser a moment to finish scrolling before triggering playback.
    // Move focus to the target first so screen readers announce the selection.
    setTimeout(function () {
      target.focus();
      target.click();
    }, 180);
  }

  function reset(keepHud) {
    if (timer) { clearTimeout(timer); timer = null; }
    buffer = '';
    if (!keepHud) hideHud();
  }

  /* ── Keyboard handler ───────────────────────────────────────────────────── */
  function onKeyDown(e) {
    // Ignore keypresses directed at text inputs
    var tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

    var key = e.key;

    /* ── Digit keys (0–9) ─────────────────────────────────────────────────── */
    if (/^[0-9]$/.test(key)) {
      e.preventDefault();
      if (buffer.length >= MAX_CHARS) {
        // If a decimal point is already in the buffer the sub-channel is fully
        // specified — ignore further digits rather than corrupting the number.
        if (buffer.indexOf('.') !== -1) return;
        // Pure-digit entry: slide the window (drop oldest digit, append new).
        buffer = buffer.slice(1) + key;
      } else {
        buffer += key;
      }
      showHud(buffer, 'ch');
      if (timer) clearTimeout(timer);
      timer = setTimeout(navigate, ENTRY_TIMEOUT_MS);
      return;
    }

    /* ── Period — sub-channel separator (e.g. 2.1, 16.5) ────────────────── */
    if (key === '.' && buffer.length > 0 && buffer.indexOf('.') === -1) {
      e.preventDefault();
      buffer += '.';
      showHud(buffer, 'ch');
      if (timer) clearTimeout(timer);
      timer = setTimeout(navigate, ENTRY_TIMEOUT_MS);
      return;
    }

    /* ── Enter / OK — confirm immediately ────────────────────────────────── */
    if (key === 'Enter' && buffer) {
      // Consume the event so TV remote nav (if active) doesn't also fire
      e.preventDefault();
      e.stopImmediatePropagation();
      if (timer) clearTimeout(timer);
      navigate();
      return;
    }

    /* ── Escape / Back — cancel ──────────────────────────────────────────── */
    if ((key === 'Escape' || key === 'GoBack') && buffer) {
      e.preventDefault();
      reset();
      return;
    }

    /* ── L key — return to last channel (only when no digit entry is active) */
    if ((key === 'l' || key === 'L') && !buffer) {
      if (typeof window.returnToLastChannel === 'function' && window.lastChannelMeta) {
        e.preventDefault();
        window.returnToLastChannel();
      }
      return;
    }
  }

  /* ── Init ───────────────────────────────────────────────────────────────── */
  // Bubble phase (capture=false) so this runs alongside tv-remote-nav handlers.
  // stopImmediatePropagation on Enter prevents other bubble-phase handlers from
  // also acting when the user is mid-entry.
  document.addEventListener('keydown', onKeyDown, false);

  // Expose a minimal public API so other modules can query / reset state
  window.__chanNumEntry = {
    /** True while the user is mid-entry (buffer non-empty). */
    isActive: function () { return buffer.length > 0; },
    /** Programmatically cancel any pending entry. */
    cancel:   function () { reset(); }
  };
})();

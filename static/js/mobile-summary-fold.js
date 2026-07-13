/**
 * mobile-summary-fold.js
 *
 * On mobile (viewport ≤ 900 px) the program-info summary panel beneath the
 * header can be folded away so the video and guide grid get more vertical
 * room.  A thin toggle strip always remains visible so the user can re-open
 * the panel at any time.
 *
 * Auto-collapse behaviour: once the video has been playing for
 * AUTO_HIDE_DELAY_MS milliseconds without user interaction the panel
 * collapses automatically.  The timer is reset whenever the user expands
 * the panel, and it is cancelled while the video is paused.
 */
(function () {
  'use strict';

  var AUTO_HIDE_DELAY_MS = 60000; // 1 minute
  var MOBILE_BREAKPOINT = 900;

  var autoHideTimer = null;
  var _initialized = false;

  /* ── helpers ── */

  function isMobile() {
    return window.innerWidth <= MOBILE_BREAKPOINT;
  }

  function getSummary() {
    return document.getElementById('summary');
  }

  function getToggle() {
    return document.getElementById('mobileSummaryToggle');
  }

  function isCollapsed() {
    var el = getSummary();
    return el ? el.classList.contains('summary-collapsed') : false;
  }

  function updateToggleLabel(collapsed) {
    var btn = getToggle();
    if (!btn) return;
    if (collapsed) {
      btn.textContent = '\u25b2 Program Info'; // ▲
      btn.setAttribute('aria-expanded', 'false');
    } else {
      btn.textContent = '\u25bc Hide Info'; // ▼
      btn.setAttribute('aria-expanded', 'true');
    }
  }

  /* ── collapse / expand ── */

  function collapse(opts) {
    if (!isMobile()) return;
    var summary = getSummary();
    if (!summary || isCollapsed()) return;
    summary.classList.add('summary-collapsed');
    updateToggleLabel(true);
    clearAutoHideTimer();
    // Let the video-height adaptor reclaim the freed space
    window.dispatchEvent(new Event('resize'));
  }

  function expand() {
    if (!isMobile()) return;
    var summary = getSummary();
    if (!summary) return;
    summary.classList.remove('summary-collapsed');
    updateToggleLabel(false);
    clearAutoHideTimer();
    window.dispatchEvent(new Event('resize'));
  }

  // Expose for external callers (e.g. playChannel re-expands summary on channel switch)
  window.mobileSummaryExpand = expand;

  /* ── auto-hide timer ── */

  function clearAutoHideTimer() {
    if (autoHideTimer) {
      clearTimeout(autoHideTimer);
      autoHideTimer = null;
    }
  }

  function startAutoHideTimer() {
    clearAutoHideTimer();
    if (!isMobile() || isCollapsed()) return;
    autoHideTimer = setTimeout(function () {
      collapse();
    }, AUTO_HIDE_DELAY_MS);
  }

  /* ── toggle button click ── */

  function onToggleClick() {
    if (isCollapsed()) {
      expand();
      // If video is still playing, restart the auto-hide countdown after manual re-open
      var video = document.getElementById('video');
      if (video && !video.paused) {
        startAutoHideTimer();
      }
    } else {
      collapse();
    }
  }

  /* ── responsive: desktop ↔ mobile transitions ── */

  function onResize() {
    var summary = getSummary();
    var toggle = getToggle();
    if (!summary || !toggle) return;
    if (!isMobile()) {
      // Restore full summary on desktop; clear any pending timers
      summary.classList.remove('summary-collapsed');
      clearAutoHideTimer();
    }
  }

  /* ── initialisation ── */

  function init() {
    if (_initialized) return;
    _initialized = true;

    var toggle = getToggle();
    if (toggle) {
      toggle.addEventListener('click', onToggleClick);
    }

    var video = document.getElementById('video');
    if (video) {
      // Start auto-hide countdown when video begins playing
      video.addEventListener('play', function () {
        if (isMobile()) {
          startAutoHideTimer();
        }
      });
      // Pause the countdown while the video is paused
      video.addEventListener('pause', function () {
        clearAutoHideTimer();
      });
      // When a new channel is selected playChannel() calls window.mobileSummaryExpand()
      // which handles re-expansion. Here we only need to clear the auto-hide timer
      // so it resets cleanly for the next stream.
      video.addEventListener('emptied', function () {
        clearAutoHideTimer();
      });
    }

    window.addEventListener('resize', onResize);

    // Ensure the toggle label reflects the initial (expanded) state
    updateToggleLabel(false);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

/**
 * wake-lock.js — Prevent the Fire TV (Silk Browser) screen saver from
 * appearing while the user is browsing the guide (i.e. not in full-screen
 * video mode).
 *
 * Strategy
 * ────────
 * 1. Use the Screen Wake Lock API if the browser supports it.
 * 2. Fall back to a tiny (≈5 KB) muted looping <video> element (status.mp4)
 *    which keeps the browser's media pipeline active and prevents the
 *    platform-level screen saver from triggering on Fire TV / Silk.
 *
 * The lock is automatically re-acquired whenever the document becomes visible
 * again (e.g. the user returns from a background app).
 *
 * Loaded conditionally from guide.html only when a TV user-agent is detected
 * (AFT, Silk, Android TV, etc.) so it has zero overhead for regular browsers.
 */
(function () {
  'use strict';

  var _wakeLock = null;     // Screen Wake Lock API handle
  var _fallbackVideo = null; // hidden <video> used when WakeLock is unavailable

  /* ── 1. Screen Wake Lock API ──────────────────────────────────────────────── */
  function acquireWakeLock() {
    if (!('wakeLock' in navigator)) {
      startFallback();
      return;
    }
    navigator.wakeLock.request('screen').then(function (lock) {
      _wakeLock = lock;
      _wakeLock.addEventListener('release', function () {
        _wakeLock = null;
        console.log('RetroIPTVGuide: screen wake lock released');
      });
      console.log('RetroIPTVGuide: screen wake lock acquired');
    }).catch(function (err) {
      console.warn('RetroIPTVGuide: wake lock unavailable (' + err.message + '), using video fallback');
      startFallback();
    });
  }

  /* ── 2. Fallback: hidden muted looping <video> ────────────────────────────── */
  function startFallback() {
    if (_fallbackVideo) return; // already running

    var vid = document.createElement('video');
    vid.loop = true;
    vid.muted = true;
    vid.setAttribute('playsinline', '');
    vid.setAttribute('aria-hidden', 'true');
    // Positioned 1×1 px off-screen: invisible but still processed by the browser.
    vid.style.cssText = 'position:fixed;top:-2px;left:-2px;width:1px;height:1px;' +
                        'opacity:0;pointer-events:none;z-index:-9999';

    // Resolve the /static root from the data-static-root attribute set by the
    // template (via Flask's url_for), falling back to the hls.js script tag so
    // the path stays consistent with the rest of the application.
    var staticRoot = (document.currentScript && document.currentScript.dataset.staticRoot) ||
                     (function () {
                       var hlsTag = document.querySelector('script[src*="hls.js"]');
                       return hlsTag ? hlsTag.src.replace(/\/hls\.js[^/]*$/, '') : '/static';
                     })();

    var src = document.createElement('source');
    src.src = staticRoot + '/loops/status.mp4';
    src.type = 'video/mp4';
    vid.appendChild(src);
    document.body.appendChild(vid);

    vid.play().then(function () {
      _fallbackVideo = vid;
      console.log('RetroIPTVGuide: screen-saver fallback video started');
    }).catch(function (e) {
      console.warn('RetroIPTVGuide: fallback video autoplay blocked', e);
      if (vid.parentNode) vid.parentNode.removeChild(vid);
    });
  }

  /* ── Re-acquire lock on page visibility change ────────────────────────────── */
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState !== 'visible') return;

    if (_wakeLock === null && _fallbackVideo === null) {
      // No lock is active — try again (WakeLock is released when page is hidden).
      acquireWakeLock();
    } else if (_fallbackVideo && _fallbackVideo.paused) {
      // Browser may have paused the fallback video while hidden; resume it.
      _fallbackVideo.play().catch(function () {});
    }
  });

  /* ── Bootstrap ────────────────────────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', acquireWakeLock);
  } else {
    acquireWakeLock();
  }
})();

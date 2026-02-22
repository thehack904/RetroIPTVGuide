/**
 * wakelock.js – Prevent the screen saver from appearing on Fire TV (Silk Browser)
 * and other TV/mobile platforms while the guide page is active and no full-screen
 * video is playing.
 *
 * Strategy:
 *  1. Try the Screen Wake Lock API (available in Chromium 84+ / modern Silk).
 *  2. Fall back to an invisible 1×1 canvas-stream video element (the classic
 *     "NoSleep" trick) which also works on Silk / Fire TV and any other
 *     Chromium-based browser that supports captureStream().
 *
 * The lock is acquired on page load and re-acquired whenever the page becomes
 * visible again (e.g. after the user switches back from another Fire TV app).
 * Special care is taken to resume the NoSleep video if the browser paused it
 * while the page was hidden, and to handle the race between the Wake Lock
 * sentinel's release event and the visibilitychange event.
 */
(function () {
  'use strict';

  var wakeLockSentinel = null;
  var noSleepVideo = null;

  // ---------------------------------------------------------------------------
  // Wake Lock API path
  // ---------------------------------------------------------------------------
  function requestWakeLock() {
    if (!('wakeLock' in navigator)) {
      startNoSleepVideo();
      return;
    }
    navigator.wakeLock.request('screen').then(function (sentinel) {
      wakeLockSentinel = sentinel;
      sentinel.addEventListener('release', function () {
        wakeLockSentinel = null;
      });
    }).catch(function () {
      // Permission denied or API failed; use the video fallback instead.
      startNoSleepVideo();
    });
  }

  // ---------------------------------------------------------------------------
  // NoSleep video fallback (canvas-stream, no external file needed)
  // ---------------------------------------------------------------------------
  function startNoSleepVideo() {
    if (noSleepVideo) return; // already running

    var canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;

    var video = document.createElement('video');
    video.setAttribute('muted', '');
    video.setAttribute('playsinline', '');
    video.setAttribute('loop', '');
    video.style.cssText =
      'position:fixed;top:-2px;left:-2px;width:1px;height:1px;' +
      'opacity:0;pointer-events:none;z-index:-1;';

    // captureStream is available in Chromium (including Silk) and Firefox.
    if (typeof canvas.captureStream === 'function') {
      video.srcObject = canvas.captureStream(1);
    } else {
      // No captureStream support; nothing more we can do silently.
      return;
    }

    document.body.appendChild(video);
    noSleepVideo = video;

    video.play().catch(function () {
      // Autoplay was blocked (requires user gesture on some platforms).
      // Wire up a one-shot user-interaction handler to start it on first input.
      function onUserGesture() {
        // Subsequent failures are silently ignored; the video is best-effort.
        video.play().catch(function () {});
        document.removeEventListener('click', onUserGesture, true);
        document.removeEventListener('keydown', onUserGesture, true);
        document.removeEventListener('touchstart', onUserGesture, true);
      }
      document.addEventListener('click', onUserGesture, true);
      document.addEventListener('keydown', onUserGesture, true);
      document.addEventListener('touchstart', onUserGesture, true);
    });
  }

  // ---------------------------------------------------------------------------
  // Re-acquire when the page becomes visible again
  // ---------------------------------------------------------------------------
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState !== 'visible') return;

    if (noSleepVideo) {
      // The browser pauses media elements while the page is hidden.
      // Resume the canvas-stream video so screen-saver prevention stays active.
      if (noSleepVideo.paused) {
        noSleepVideo.play().catch(function () {});
      }
    } else if (!wakeLockSentinel) {
      // Wake Lock was released while hidden (or never acquired); re-acquire now.
      // This also covers the race where the sentinel's release event fires just
      // after the visibilitychange event for the hidden state.
      requestWakeLock();
    } else {
      // A sentinel exists but the browser may release it asynchronously right
      // after this event; re-request now to stay ahead of that race.
      navigator.wakeLock.request('screen').then(function (newSentinel) {
        try { wakeLockSentinel.release(); } catch (e) {}
        wakeLockSentinel = newSentinel;
        newSentinel.addEventListener('release', function () {
          wakeLockSentinel = null;
        });
      }).catch(function () {
        // Wake Lock unavailable right now; fall back to the video strategy.
        wakeLockSentinel = null;
        startNoSleepVideo();
      });
    }
  });

  // ---------------------------------------------------------------------------
  // Kick off on page load
  // ---------------------------------------------------------------------------
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', requestWakeLock);
  } else {
    requestWakeLock();
  }
})();

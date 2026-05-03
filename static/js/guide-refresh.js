(() => {
  // Adjust the hours parameter if you prefer 8-hour browser view
  const ENDPOINT = '/api/guide_snapshot?hours=6';
  const REFRESH_INTERVAL_MIN = 30; // same cadence as Cairo

  // Track whether a refresh was skipped because video was in fullscreen
  let _pendingRefresh = false;

  function isFullscreenActive() {
    return !!(
      document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.mozFullScreenElement ||
      document.msFullscreenElement
    );
  }

  async function refreshGuide() {
    // Do not reload while video is playing in fullscreen — it kills the stream.
    // Set a flag so we reload as soon as fullscreen is exited.
    if (isFullscreenActive()) {
      _pendingRefresh = true;
      console.log('[guide-refresh] Fullscreen active — deferring guide refresh.');
      return;
    }

    try {
      const res = await fetch(ENDPOINT, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      // You can either rebuild just the EPG grid, or simply reload the page
      // depending on how your current guide is generated.
      // For now, safest approach is a full reload:
      _pendingRefresh = false;
      window.location.reload();
    } catch (err) {
      console.error('[guide-refresh] Failed to refresh guide:', err);
    }
  }

  // When the user exits fullscreen, perform the deferred reload if one is waiting.
  function onFullscreenChange() {
    if (!isFullscreenActive() && _pendingRefresh) {
      _pendingRefresh = false;
      console.log('[guide-refresh] Fullscreen exited — running deferred guide refresh.');
      window.location.reload();
    }
  }

  document.addEventListener('fullscreenchange', onFullscreenChange);
  document.addEventListener('webkitfullscreenchange', onFullscreenChange);
  document.addEventListener('mozfullscreenchange', onFullscreenChange);
  document.addEventListener('MSFullscreenChange', onFullscreenChange);

  // Run once every X minutes so the grid rolls forward with real time
  setInterval(refreshGuide, REFRESH_INTERVAL_MIN * 60 * 1000);
})();


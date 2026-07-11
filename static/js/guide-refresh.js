(() => {
  // Adjust the hours parameter if you prefer 8-hour browser view
  const ENDPOINT = '/api/guide_snapshot?hours=6';
  const REFRESH_INTERVAL_MIN = 30; // same cadence as Cairo

  // Track whether a refresh was skipped because video was playing
  let _pendingRefresh = false;
  // Debounce handle for the deferred reload (guards against simultaneous events)
  let _idleTimer = null;

  function isFullscreenActive() {
    return !!(
      document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.mozFullScreenElement ||
      document.msFullscreenElement
    );
  }

  // Returns true if video is actively playing in any mode:
  // fullscreen, embedded in the guide, or Picture-in-Picture.
  function isVideoPlaying() {
    if (isFullscreenActive()) return true;
    if (document.pictureInPictureElement) return true;
    const video = document.getElementById('video');
    if (video && !video.paused && !video.ended) return true;
    return false;
  }

  async function refreshGuide() {
    // Do not reload while video is playing in any mode — it kills the stream.
    // Set a flag so we reload as soon as playback stops.
    if (isVideoPlaying()) {
      _pendingRefresh = true;
      console.log('[guide-refresh] Video is playing — deferring guide refresh.');
      return;
    }

    try {
      const res = await fetch(ENDPOINT, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      _pendingRefresh = false;
      window.location.reload();
    } catch (err) {
      console.error('[guide-refresh] Failed to refresh guide:', err);
    }
  }

  // Called whenever playback may have stopped; performs the deferred reload
  // if one is pending and the video is no longer playing.
  // Debounced with a stored timer ID so simultaneous events (e.g. `pause` +
  // `leavepictureinpicture`) never schedule more than one reload, and to
  // guard against false triggers during brief buffering pauses or channel
  // switching where playback resumes within milliseconds.
  function onVideoIdle() {
    if (!_pendingRefresh) return;
    clearTimeout(_idleTimer);
    _idleTimer = setTimeout(() => {
      _idleTimer = null;
      if (_pendingRefresh && !isVideoPlaying()) {
        _pendingRefresh = false;
        console.log('[guide-refresh] Video stopped — running deferred guide refresh.');
        window.location.reload();
      }
    }, 500);
  }

  // Called when the video resumes playing; cancels any pending idle reload to
  // avoid false triggers during channel switching or brief buffering pauses.
  function onVideoPlaying() {
    clearTimeout(_idleTimer);
    _idleTimer = null;
  }

  // When the user exits fullscreen, perform the deferred reload if one is waiting.
  function onFullscreenChange() {
    if (!isFullscreenActive()) onVideoIdle();
  }

  document.addEventListener('fullscreenchange', onFullscreenChange);
  document.addEventListener('webkitfullscreenchange', onFullscreenChange);
  document.addEventListener('mozfullscreenchange', onFullscreenChange);
  document.addEventListener('MSFullscreenChange', onFullscreenChange);

  // Attach pause/ended/playing listeners to the video element so a deferred
  // refresh fires as soon as the user stops watching (covers embedded and
  // popped-out modes). The #video element is a long-lived static element;
  // a console warning is emitted if it is unexpectedly absent.
  function attachVideoListeners() {
    const video = document.getElementById('video');
    if (!video) {
      console.warn('[guide-refresh] #video element not found; video-playing guard inactive.');
      return;
    }
    video.addEventListener('pause', onVideoIdle);
    video.addEventListener('ended', onVideoIdle);
    // If playback resumes within the debounce window, cancel the pending reload.
    video.addEventListener('playing', onVideoPlaying);
    // leavepictureinpicture fires on the video element, not the document.
    video.addEventListener('leavepictureinpicture', onVideoIdle);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachVideoListeners);
  } else {
    attachVideoListeners();
  }

  // Run once every X minutes so the grid rolls forward with real time
  setInterval(refreshGuide, REFRESH_INTERVAL_MIN * 60 * 1000);
})();


(() => {
  const ENDPOINT = '/api/guide_snapshot?hours=6';
  const REFRESH_INTERVAL_MIN = 30;      // re-sync with server window (Cairo-style)
  const TICK_MS = 60000;               // move line every 1 min
  const SCALE = 5;                     // must match SCALE in app.py

  const timeRow = document.getElementById('gridTimeRow');
  if (!timeRow) return;

  const nowLine = document.getElementById('nowLineOriginal');
  if (!nowLine) return;

  // Element that owns the CSS variable; your layout already wraps now-line in .grid-content
  const gridContent = timeRow.querySelector('.time-header-wrap .grid-content') || timeRow;
  if (!gridContent) return;

  let windowStart = null;    // Date from API
  let windowMinutes = null;  // total minutes from API

  function setNowOffset(px) {
    gridContent.style.setProperty('--now-offset', px + 'px');
  }

  async function syncWindowFromAPI() {
    try {
      const res = await fetch(ENDPOINT, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.window || !data.window.start_iso || !data.window.minutes) return;

      windowStart = new Date(data.window.start_iso);
      windowMinutes = data.window.minutes;

      // Make sure the line is visible once we have a valid window
      nowLine.style.display = 'block';

      updateNowLine(); // snap immediately after sync
      console.log('[guide-now-sync] window synced');
    } catch (e) {
      console.error('[guide-now-sync] failed to sync window', e);
    }
  }

  function minutesSinceStart() {
    if (!windowStart) return 0;
    return (Date.now() - windowStart.getTime()) / 60000;
  }

  function updateNowLine() {
    if (!windowStart || !windowMinutes) return;

    const elapsed = minutesSinceStart();

    if (elapsed < 0 || elapsed > windowMinutes) {
      // Outside current window: hide line so it doesn't lie
      nowLine.style.display = 'none';
      return;
    }

    nowLine.style.display = 'block';
    const offsetPx = elapsed * SCALE;
    setNowOffset(offsetPx);
  }

  // Kick things off
  syncWindowFromAPI();

  // Re-sync to server window (so page follows the same rolling window as Cairo)
  setInterval(syncWindowFromAPI, REFRESH_INTERVAL_MIN * 60 * 1000);

  // Smoothly advance between syncs
  setInterval(updateNowLine, TICK_MS);
})();


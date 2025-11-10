(() => {
  // Adjust the hours parameter if you prefer 8-hour browser view
  const ENDPOINT = '/api/guide_snapshot?hours=6';
  const REFRESH_INTERVAL_MIN = 30; // same cadence as Cairo

  async function refreshGuide() {
    try {
      const res = await fetch(ENDPOINT, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      // You can either rebuild just the EPG grid, or simply reload the page
      // depending on how your current guide is generated.
      // For now, safest approach is a full reload:
      window.location.reload();

      console.log(`[guide-refresh] Guide refreshed at ${new Date().toLocaleTimeString()}`);
    } catch (err) {
      console.error('[guide-refresh] Failed to refresh guide:', err);
    }
  }

  // Run once every X minutes so the grid rolls forward with real time
  setInterval(refreshGuide, REFRESH_INTERVAL_MIN * 60 * 1000);
})();


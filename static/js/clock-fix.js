// Small resilient clock updater (fallback)
// Place at: static/js/clock-fix.js and include with defer.
//
// This will update #clock every second and also attempt an initial update on DOMContentLoaded/load.
// It also listens for DOM mutations so it recovers if the header is re-rendered dynamically.

(function(){
  function formatNow() {
    try {
      const now = new Date();
      return now.toLocaleString([], {
        weekday: 'short',
        month:   'short',
        day:     'numeric',
        hour:    '2-digit',
        minute:  '2-digit',
        second:  '2-digit'
      });
    } catch (e) {
      // fallback simple formatting
      return new Date().toString();
    }
  }

  function doUpdateClock() {
    try {
      const el = document.getElementById('clock');
      if (!el) return;
      el.textContent = formatNow();
    } catch (e) {
      // swallow errors so this helper can't break other scripts
      console.debug('clock-fix update error', e);
    }
  }

  // Expose a legacy-compatible global function name so existing code that calls
  // updateClock() won't throw ReferenceError.
  // If another script already defines updateClock, do not overwrite it.
  if (typeof window !== 'undefined' && typeof window.updateClock !== 'function') {
    window.updateClock = doUpdateClock;
  }

  // Update immediately on DOM ready and on load (cover different load orders)
  document.addEventListener('DOMContentLoaded', doUpdateClock);
  window.addEventListener('load', doUpdateClock);

  // Continuous interval update
  setInterval(doUpdateClock, 1000);

  // Observe DOM mutations (in case header is re-rendered/replaced by other scripts)
  const observer = new MutationObserver(() => {
    // small debounce
    if (observer._t) clearTimeout(observer._t);
    observer._t = setTimeout(() => {
      doUpdateClock();
    }, 80);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  // Also try a best-effort immediate run in case this file is included late
  doUpdateClock();
})();

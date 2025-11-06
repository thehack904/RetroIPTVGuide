// Keep fixed timebar correctly positioned on mobile when the page scrolls
// Place at: static/js/mobile-scroll-fix.js
// Include after mobile-nav.js and grid-adapt.js: <script src="{{ url_for('static', filename='js/mobile-scroll-fix.js') }}" defer></script>

(function(){
  // Don't run unnecessarily on desktop
  const MOBILE_MAX = 900;
  let last = 0;
  let rafPending = false;

  function throttle(fn) {
    return function() {
      const now = Date.now();
      if (rafPending) return;
      if (now - last < 80) { // ~12 FPS throttle
        rafPending = true;
        setTimeout(() => { rafPending = false; last = Date.now(); fn(); }, 80);
        return;
      }
      last = now;
      fn();
    };
  }

  function recomputeFixedBar() {
    try {
      if (window.innerWidth > MOBILE_MAX) return;
      if (typeof window.createOrUpdateFixedTimeBar === 'function') {
        // use rAF to ensure layout has settled
        requestAnimationFrame(() => {
          window.createOrUpdateFixedTimeBar();
          if (typeof window.updateNowLine === 'function') window.updateNowLine();
        });
      }
    } catch (e) { console.debug('recomputeFixedBar err', e); }
  }

  const recomputeThrottled = throttle(recomputeFixedBar);

  // Recompute on scroll & touchmove for mobile
  window.addEventListener('scroll', recomputeThrottled, { passive: true });
  window.addEventListener('touchmove', recomputeThrottled, { passive: true });

  // Also recompute when nav opens/closes via class change (mobile-nav-open)
  const bodyObserver = new MutationObserver(() => {
    recomputeThrottled();
  });
  bodyObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });

  // Recompute on resize / orientation change
  window.addEventListener('resize', recomputeThrottled);
})();

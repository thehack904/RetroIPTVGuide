// Keep fixed timebar correctly positioned on mobile.
// With the fixed-viewport layout, the timebar sits permanently just below the
// player row which is itself at the top of the fixed #appZoomRoot.  The bar
// position never changes on scroll (guide-outer scrolls internally), so we only
// need to recompute on resize / orientation change.
// Place at: static/js/mobile-scroll-fix.js

(function(){
  const MOBILE_MAX = 900;

  function recomputeFixedBar() {
    try {
      if (window.innerWidth > MOBILE_MAX) return;
      if (typeof window.createOrUpdateFixedTimeBar === 'function') {
        requestAnimationFrame(() => {
          window.createOrUpdateFixedTimeBar();
          if (typeof window.updateNowLine === 'function') window.updateNowLine();
        });
      }
    } catch (e) { console.debug('recomputeFixedBar err', e); }
  }

  // Recompute when nav opens/closes (class mutation changes player row height)
  const bodyObserver = new MutationObserver(() => { recomputeFixedBar(); });
  bodyObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });

  // Recompute on resize / orientation change
  window.addEventListener('resize', recomputeFixedBar);
})();

(function(){
  // This helper keeps the video height reasonable on narrow viewports,
  // accounting for the header height and the fixed timebar (if present).
  function adjustVideoHeight() {
    try {
      if (window.innerWidth > 900) {
        // desktop: let CSS/base rules handle sizing
        const video = document.getElementById('video');
        if (video) {
          video.style.maxHeight = '';
        }
        return;
      }

      const video = document.getElementById('video');
      const playerRow = document.getElementById('playerRow');
      const header = document.querySelector('.header');
      const fixedBar = document.getElementById('fixedTimeBar');

      if (!video || !playerRow) return;

      const vh = window.innerHeight;
      const headerHeight = header ? Math.round(header.getBoundingClientRect().height) : 40;
      const fixedBarHeight = fixedBar ? Math.round(fixedBar.getBoundingClientRect().height) : 0;
      const reserved = headerHeight + fixedBarHeight + 80; // 80px for summary + paddings/controls
      // Give the video a max height that's the remaining viewport minus some buffer
      const maxH = Math.max(160, Math.round(vh - reserved));
      // Restrict to a reasonable share of viewport (so timeline remains reachable)
      const cap = Math.round(vh * 0.55); // at most 55% of viewport height
      const finalH = Math.min(maxH, cap);

      video.style.maxHeight = finalH + 'px';
      video.style.height = 'auto';

      // If using scaled grid via grid-adapt.js we expect grid-adapt to recompute when this runs.
      if (typeof window.createOrUpdateFixedTimeBar === 'function') {
        window.createOrUpdateFixedTimeBar();
      }
    } catch(e){
      console.debug('mobile-player-adapt err', e);
    }
  }

  window.addEventListener('resize', adjustVideoHeight);
  document.addEventListener('DOMContentLoaded', adjustVideoHeight);

  // Recompute when body class mutates (theme change) or when mobile nav opens/closes (mobile-nav dispatches resize)
  const observer = new MutationObserver(function(){ adjustVideoHeight(); });
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
})();

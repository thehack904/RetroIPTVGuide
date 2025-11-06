// Adaptive grid scaling for narrow/mobile viewports.
// Place at: static/js/grid-adapt.js
// Include after your other scripts, e.g.:
// <script src="{{ url_for('static', filename='js/grid-adapt.js') }}" defer></script>

(function(){
  const MOBILE_MAX = 900; // only adapt on viewports <= this width

  function parsePx(value) {
    if (!value) return NaN;
    return parseFloat(String(value).replace('px','')) || NaN;
  }

  function findGridContent() {
    // Prefer the main guide grid-content inside guide-outer
    let el = document.querySelector('#guideOuter .grid-content');
    if (el) return el;
    // fallback to the first .grid-content found
    return document.querySelector('.grid-content');
  }

  function adaptGridToViewport(){
    try {
      const gridContent = findGridContent();
      if (!gridContent) return;

      // On large screens reset any transforms
      if (window.innerWidth > MOBILE_MAX) {
        gridContent.style.transform = '';
        gridContent.style.transformOrigin = '';
        // restore guide-outer height if modified
        const guideOuter = document.getElementById('guideOuter');
        if (guideOuter) guideOuter.style.height = '';
        return;
      }

      // Determine total timeline width:
      // Prefer CSS var --total-width if set, otherwise measured scrollWidth
      const rootStyle = getComputedStyle(document.documentElement);
      let totalWidth = parsePx(rootStyle.getPropertyValue('--total-width'));
      if (!totalWidth || Number.isNaN(totalWidth) || totalWidth <= 0) {
        // gridContent may be transformed already; measure scrollWidth which is unscaled
        totalWidth = gridContent.scrollWidth || gridContent.getBoundingClientRect().width || 1;
      }

      // Determine channel column width (prefer CSS var)
      let chanColWidth = parsePx(rootStyle.getPropertyValue('--chan-col-width'));
      if (!chanColWidth || Number.isNaN(chanColWidth) || chanColWidth <= 0) {
        const firstChan = document.querySelector('.guide-row .chan-col');
        chanColWidth = firstChan ? firstChan.getBoundingClientRect().width : 200;
      }

      // Compute available width for the timeline (viewport minus chan column)
      const available = Math.max(120, window.innerWidth - chanColWidth);
      let scale = 1;
      if (totalWidth > 0 && available > 0) {
        scale = Math.min(1, available / totalWidth);
      }

      // Only apply scaling when we need to shrink (never expand)
      if (scale < 1) {
        gridContent.style.transformOrigin = 'left top';
        gridContent.style.transform = `scale(${scale})`;
        gridContent.style.willChange = 'transform';
      } else {
        gridContent.style.transform = '';
        gridContent.style.transformOrigin = '';
      }

      // Adjust guideOuter height to accommodate scaled content so that elements below remain reachable
      const guideOuter = document.getElementById('guideOuter');
      if (guideOuter) {
        if (scale < 1) {
          // estimate original content height using bounding rect and scale factor
          const rect = gridContent.getBoundingClientRect();
          // boundingRect is already scaled; estimate original by dividing by scale
          const estimatedUnscaledH = rect.height / (scale || 1);
          const scaledHeight = Math.round(estimatedUnscaledH * scale);
          // keep a sensible minimum and add room for the player row above
          const minHeight = 220;
          guideOuter.style.height = Math.max(minHeight, scaledHeight + 180) + 'px';
        } else {
          guideOuter.style.height = '';
        }
      }

      // Recompute fixed header/now-line if helper exists
      if (typeof window.createOrUpdateFixedTimeBar === 'function') {
        window.createOrUpdateFixedTimeBar();
      }
      if (typeof window.updateNowLine === 'function') {
        window.updateNowLine();
      }
    } catch (e) {
      console.debug('grid-adapt error', e);
    }
  }

  // Run on load
  document.addEventListener('DOMContentLoaded', adaptGridToViewport);
  // And on resize
  window.addEventListener('resize', adaptGridToViewport);

  // Recompute on theme changes or other body-class mutations
  const observer = new MutationObserver(adaptGridToViewport);
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });

  // Also watch for layout changes to the grid-content (images, dynamic content)
  const gridEl = findGridContent();
  if (gridEl) {
    const gridObserver = new MutationObserver(() => {
      // small debounce to avoid thrashing
      clearTimeout(gridAdaptDebounce);
      gridAdaptDebounce = setTimeout(adaptGridToViewport, 100);
    });
    let gridAdaptDebounce = null;
    gridObserver.observe(gridEl, { childList: true, subtree: true, attributes: true });
  }
})();

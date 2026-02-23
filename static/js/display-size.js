/* display-size.js
   Manages the "Display Size" preference (Large / Medium / Small) which scales
   the entire page the same way the browser's built-in Cmd/Ctrl +/- zoom does:
     Large  = 100% (no scaling)
     Medium =  80%
     Small  =  67%

   Implementation: transform: scale(s) on #appZoomRoot (a single wrapper div that
   contains all visual content in the page). The wrapper is expanded to
   width/height = (100/s)% so that after scale(s) it fills exactly the viewport.
   This is browser-zoom-equivalent and has none of the cross-browser quirks of the
   CSS `zoom` property (body height resolution, fixed-position offsets, etc.).

   Preference is stored in localStorage under the key 'displaySize'.
*/
(function () {
  'use strict';

  var STORAGE_KEY = 'displaySize';
  var ZOOM_PRESETS = { large: 1.0, medium: 0.8, small: 0.67 };

  // Module-level scale — read by window.getDisplayZoom()
  var _scale = 1.0;

  /**
   * Apply transform: scale(s) + compensating width/height to #appZoomRoot.
   * The compensation (width = 100/s %, height = 100/s %) ensures that after
   * scaling the wrapper fills the full visual viewport.
   *
   * Also sets --display-zoom as an inline CSS variable on <html> so that
   * existing JS helpers (createOrUpdateFixedTimeBar, updateNowLine, grid-adapt)
   * can read it via getComputedStyle without needing to know the implementation.
   */
  function getViewportSize() {
    var vv = window.visualViewport;
    var w = (vv && vv.width) ? vv.width : window.innerWidth;
    var h = (vv && vv.height) ? vv.height : window.innerHeight;
    return { w: w, h: h };
  }

  function applyUiZoom(scale) {
    var root = document.getElementById('appZoomRoot');
    if (root) {
      // Enforce fixed wrapper so body/percent sizing cannot clip the scaled UI
      root.style.position = 'fixed';
      root.style.top = '0';
      root.style.left = '0';
      root.style.overflow = 'hidden';
      root.style.transformOrigin = 'top left';

      var vp = getViewportSize();

      if (scale < 1) {
        // Explicit px avoids 100%/vh resolution quirks when overflow:hidden is involved
        root.style.transform = 'scale(' + scale + ')';
        root.style.width = Math.ceil(vp.w / scale) + 'px';
        root.style.height = Math.ceil(vp.h / scale) + 'px';
      } else {
        root.style.transform = '';
        // Fixed + 100% resolves to the viewport
        root.style.width = '100%';
        root.style.height = '100%';
      }
    }
    // Keep --display-zoom in sync so CSS/JS consumers always read the right value
    document.documentElement.style.setProperty('--display-zoom', String(scale));
  }

  function applyDisplaySize(size) {
    var scale = ZOOM_PRESETS[size] || 1.0;
    _scale = scale;

    // Keep data-display-size attribute for CSS theming hooks
    if (!size || size === 'large') {
      document.documentElement.removeAttribute('data-display-size');
    } else {
      document.documentElement.setAttribute('data-display-size', size);
    }

    try { localStorage.setItem(STORAGE_KEY, size || 'large'); } catch (e) { /* ignore */ }

    applyUiZoom(scale);

    // Notify layout helpers (fixed timebar, now-line, grid-adapt, video-resize)
    try { window.dispatchEvent(new Event('resize')); } catch (e) { /* ignore */ }
    try {
      window.dispatchEvent(new CustomEvent('displaySize:applied', { detail: { size: size || 'large' } }));
    } catch (e) { /* ignore */ }
  }

  // Public API — same surface as before so all callers continue to work
  window.setDisplaySize = applyDisplaySize;

  /**
   * Returns the active scale factor (1.0 for Large, 0.8 for Medium, 0.67 for Small).
   * Used by createOrUpdateFixedTimeBar, updateNowLine, and grid-adapt.js to convert
   * getBoundingClientRect() visual pixels → CSS pixels in appZoomRoot's coordinate space:
   *   cssPixels = visualPixels / getDisplayZoom()
   */
  window.getDisplayZoom = function () { return _scale; };

  // Delegated click handler for [data-display-size-selector] elements
  document.addEventListener('click', function (e) {
    try {
      var btn = e.target.closest && e.target.closest('[data-display-size-selector]');
      if (!btn) return;
      if (typeof e.preventDefault === 'function') e.preventDefault();
      var s = btn.getAttribute('data-display-size');
      if (s) applyDisplaySize(s);
    } catch (err) { /* ignore */ }
  }, false);

  // Re-apply on real viewport resize (orientation change, window resize) so the
  // compensating width/height stays correct.
  window.addEventListener('resize', function () {
    try {
      if (_scale < 1) applyUiZoom(_scale);
    } catch (e) { /* ignore */ }
  });

  // Restore saved preference on DOMContentLoaded.
  // The inline <head> script already injected a CSS rule so #appZoomRoot is
  // scaled on the very first paint (FOUC prevention).  Here we replace that CSS
  // rule with authoritative inline styles and set _scale so getDisplayZoom()
  // returns the correct value immediately.
  document.addEventListener('DOMContentLoaded', function () {
    try {
      // Remove the FOUC-prevention style tag if present
      var initStyle = document.getElementById('__dsinit');
      if (initStyle) initStyle.parentNode.removeChild(initStyle);

      var saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      var scale = ZOOM_PRESETS[saved] || 1.0;
      _scale = scale;

      if (saved !== 'large') {
        document.documentElement.setAttribute('data-display-size', saved);
        applyUiZoom(scale);
        // Trigger resize so timebar / now-line recompute with the correct scale
        try { window.dispatchEvent(new Event('resize')); } catch (e) { /* ignore */ }
      } else {
        applyUiZoom(1.0); // ensure any leftover transform is cleared
      }
    } catch (e) { /* ignore */ }
  });
})();

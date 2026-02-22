/* display-size.js
   Manages the "Display Size" preference (Large / Medium / Small) which scales
   the entire page similarly to the browser's built-in zoom:
     Large  = 100% (no scaling)
     Medium =  80%
     Small  =  67%
   Preference is stored in localStorage under the key 'displaySize'.
*/
(function () {
  'use strict';
  var STORAGE_KEY = 'displaySize';

  // Map size name -> zoom factor
  var ZOOM_MAP = { large: 1.0, medium: 0.8, small: 0.67 };

  /**
   * Set html element's width and height so that after CSS zoom is applied the
   * element visually fills the entire viewport.
   *
   * CSS zoom does NOT update window.innerWidth/innerHeight, and whether browsers
   * scale 100vh/100vw by the zoom factor is inconsistent. Using window.innerWidth/
   * innerHeight directly is the only reliable method — they always reflect the true
   * physical viewport size regardless of CSS zoom.
   *
   *   html CSS size = window.innerWidth / zoom
   *   html visual size = html CSS size × zoom = window.innerWidth  ✓
   */
  function setHtmlDimensions(zoom) {
    var el = document.documentElement;
    if (zoom < 1.0) {
      el.style.width  = Math.ceil(window.innerWidth  / zoom) + 'px';
      el.style.height = Math.ceil(window.innerHeight / zoom) + 'px';
    } else {
      el.style.width  = '';
      el.style.height = '';
    }
  }

  function applyDisplaySize(size) {
    var zoom = ZOOM_MAP[size] || 1.0;
    if (!size || size === 'large') {
      document.documentElement.removeAttribute('data-display-size');
    } else {
      document.documentElement.setAttribute('data-display-size', size);
    }
    setHtmlDimensions(zoom);
    try { localStorage.setItem(STORAGE_KEY, size || 'large'); } catch (e) { /* ignore */ }

    // Notify other parts of the app (layout helpers, grid-adapt, etc.)
    try { window.dispatchEvent(new Event('resize')); } catch (e) { /* ignore */ }
    try {
      var ev = new CustomEvent('displaySize:applied', { detail: { size: size || 'large' } });
      window.dispatchEvent(ev);
    } catch (e) { /* ignore */ }
  }

  // Expose global API
  window.setDisplaySize = applyDisplaySize;

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

  // Keep html dimensions in sync when the real viewport is resized (e.g. window
  // resize, orientation change) while a zoom level is active.
  window.addEventListener('resize', function () {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (saved && saved !== 'large') {
        var zoom = ZOOM_MAP[saved] || 1.0;
        setHtmlDimensions(zoom);
      }
    } catch (e) { /* ignore */ }
  });

  // Restore saved size on load. The inline early-apply script in the template already
  // sets the html attribute for non-'large' values before paint. Here we handle the
  // 'large' case (which the inline script skips) and any page that lacks the inline
  // script. We avoid firing a second resize when the attribute was already applied.
  document.addEventListener('DOMContentLoaded', function () {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      var current = document.documentElement.getAttribute('data-display-size') || 'large';
      var expected = saved || 'large';
      if (current !== expected) {
        applyDisplaySize(saved);
      } else if (saved !== 'large') {
        // Attribute already set by inline script — still need to set html dimensions
        // because the inline script doesn't do that.
        var zoom = ZOOM_MAP[saved] || 1.0;
        setHtmlDimensions(zoom);
        // Also trigger resize so JS layout helpers (fixed bar, now-line) recompute
        try { window.dispatchEvent(new Event('resize')); } catch (e) { /* ignore */ }
      }
    } catch (e) { /* ignore */ }
  });
})();

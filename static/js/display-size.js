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

  function applyDisplaySize(size) {
    if (!size || size === 'large') {
      document.documentElement.removeAttribute('data-display-size');
    } else {
      document.documentElement.setAttribute('data-display-size', size);
    }
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

  // Restore saved size on load. The inline early-apply script in the template already
  // sets the html attribute for non-'large' values before paint. Here we handle the
  // 'large' case (which the inline script skips) and any page that lacks the inline
  // script. We avoid firing a second resize when the attribute was already applied.
  document.addEventListener('DOMContentLoaded', function () {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
      // Check whether the inline script already set the correct attribute so we
      // don't trigger an unnecessary resize/reflow.
      var current = document.documentElement.getAttribute('data-display-size') || 'large';
      var expected = (!saved || saved === 'large') ? 'large' : saved;
      if (current !== expected) {
        applyDisplaySize(saved);
      }
    } catch (e) { /* ignore */ }
  });
})();

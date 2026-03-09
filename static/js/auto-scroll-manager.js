// auto-scroll-manager.js
// Defensive helper additions: remove auto-scroll clones and respond to theme changes.
// Add/merge this into your existing auto-scroll implementation. This file is safe if
// your existing auto-scroll code exposes window.__autoScroll or uses localStorage.autoScrollEnabled.

(function () {
  'use strict';

  // Class name used by the auto-scroll clones in this app
  var CLONE_SELECTOR = '.__auto_scroll_clone';

  function removeAutoScrollClones() {
    try {
      var clones = document.querySelectorAll(CLONE_SELECTOR);
      if (!clones || clones.length === 0) return 0;
      clones.forEach(function (c) {
        // If the clone has any attached cleanup hooks, try to call them
        try {
          if (c.__autoScrollCleanup && typeof c.__autoScrollCleanup === 'function') {
            try { c.__autoScrollCleanup(); } catch (e) { /* ignore */ }
          }
        } catch (e) {}
        // Remove the clone node from DOM
        if (c.parentNode) c.parentNode.removeChild(c);
      });
      return clones.length;
    } catch (err) {
      console.error('removeAutoScrollClones error', err);
      return 0;
    }
  }

  // Public helper so other code can call it: window.__autoScrollCleanup()
  try {
    window.__autoScrollCleanup = function () {
      return removeAutoScrollClones();
    };
  } catch (e) {}

  // Disable auto-scroll safely using whatever API is available,
  // and ensure localStorage flag is set so future loads know it's disabled.
  function disableAutoScrollForTheme() {
    try { localStorage.setItem('autoScrollEnabled', 'false'); } catch (e) {}
    try {
      if (window.__autoScroll) {
        if (typeof window.__autoScroll.disable === 'function') {
          try { window.__autoScroll.disable(); } catch (e) {}
        } else if (typeof window.__autoScroll.toggle === 'function') {
          // Try to get current status and toggle off if necessary
          try {
            var s = (typeof window.__autoScroll.status === 'function') ? window.__autoScroll.status() : null;
            var pref = s && typeof s.pref !== 'undefined' ? s.pref : null;
            if (pref === null && typeof window.__autoScroll.pref === 'function') {
              pref = window.__autoScroll.pref();
            }
            if (pref) window.__autoScroll.toggle();
          } catch (e) { /* ignore */ }
        }
        try { window.__autoScroll._disabledByTheme = true; } catch (e) {}
      }
    } catch (e) { /* ignore */ }

    // Remove remaining clones from the DOM
    try { removeAutoScrollClones(); } catch (e) {}
  }

  // When leaving the theme we clear the marker but do not automatically re-enable auto-scroll.
  function clearThemeDisableMarker() {
    try {
      if (window.__autoScroll && window.__autoScroll._disabledByTheme) {
        try { delete window.__autoScroll._disabledByTheme; } catch (e) {}
      }
    } catch (e) {}
  }

  // Listen for the theme:applied custom event dispatched by theme.js.applyTheme
  // (or emitted earlier by other code)
  function onThemeApplied(e) {
    try {
      var theme = (e && e.detail && e.detail.theme) ? e.detail.theme : null;
      if (!theme) return;
      clearThemeDisableMarker();
      // Remove any stale clones when the theme changes so auto-scroll starts clean.
      removeAutoScrollClones();
    } catch (err) {
      console.error('onThemeApplied error', err);
    }
  }

  function watchBodyForThemeClass() {
    try {
      var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
          if (m.type === 'attributes' && m.attributeName === 'class') {
            try {
              clearThemeDisableMarker();
              removeAutoScrollClones();
            } catch (e) {}
          }
        });
      });
      observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    } catch (e) {}
  }

  // On load: if auto-scroll is disabled in localStorage, ensure clones are not left behind.
  function initRunChecks() {
    try {
      try {
        var enabled = localStorage.getItem('autoScrollEnabled');
        if (enabled === 'false') removeAutoScrollClones();
      } catch (e) {}
    } catch (e) {}
  }

  // Wire up listeners
  try {
    document.addEventListener('theme:applied', onThemeApplied, false);
  } catch (e) {}
  try { watchBodyForThemeClass(); } catch (e) {}

  // Run initial checks on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRunChecks, false);
  } else {
    setTimeout(initRunChecks, 0);
  }

  // Expose a console-friendly alias to remove clones immediately
  try { window.removeAutoScrollClones = removeAutoScrollClones; } catch (e) {}

})();

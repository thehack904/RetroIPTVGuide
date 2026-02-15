(function () {
  'use strict';
  var STORAGE_KEY = 'theme';

  // Detect system color scheme preference
  function detectSystemTheme() {
    try {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        return 'light';
      }
    } catch (e) { /* ignore */ }
    return 'light'; // default fallback
  }

  function setHtmlAndBodyTheme(name) {
    try {
      if (name) {
        document.documentElement.setAttribute('data-theme', name);
      } else {
        document.documentElement.removeAttribute('data-theme');
      }
    } catch (e) { /* ignore */ }

    try {
      // Backwards compatibility: add a body class for themes that use body.themeName selectors
      var prev = document.body.getAttribute('data-theme-class');
      if (prev) document.body.classList.remove(prev);
      if (name) {
        document.body.classList.add(name);
        document.body.setAttribute('data-theme-class', name);
      } else {
        document.body.removeAttribute('data-theme-class');
      }
    } catch (e) { /* ignore */ }
  }

  function applyTheme(name) {
    if (!name) return;
    
    // Handle 'auto' theme - detect system preference
    var actualTheme = name;
    if (name === 'auto') {
      actualTheme = detectSystemTheme();
    }
    
    setHtmlAndBodyTheme(actualTheme);
    try { localStorage.setItem(STORAGE_KEY, name); } catch (e) {} // Store user choice (including 'auto')

    // If TV Guide (Classic) selected, ensure auto-scroll is turned off and disabled.
    // We set localStorage autoScrollEnabled to 'false' and call any available auto-scroll API.
    try {
      if (name === 'tvguide1990') {
        try { localStorage.setItem('autoScrollEnabled', 'false'); } catch (e) {}
        if (window.__autoScroll) {
          try {
            // Preferred API: disable()
            if (typeof window.__autoScroll.disable === 'function') {
              window.__autoScroll.disable();
            } else if (typeof window.__autoScroll.toggle === 'function') {
              // If toggle exists and status shows enabled, toggle it off
              try {
                var status = (typeof window.__autoScroll.status === 'function') ? window.__autoScroll.status() : null;
                var pref = status && typeof status.pref !== 'undefined' ? status.pref : null;
                if (pref === null && typeof window.__autoScroll.pref === 'function') {
                  pref = window.__autoScroll.pref();
                }
                if (pref) window.__autoScroll.toggle();
              } catch (inner) { /* ignore */ }
            }
            // Mark that auto-scroll was disabled due to theme so other code can detect it
            try { window.__autoScroll._disabledByTheme = true; } catch (e) {}
          } catch (e) { /* ignore */ }
        }
      } else {
        // Leaving tvguide1990: clear the theme-disable marker (do NOT auto-enable auto-scroll)
        if (window.__autoScroll && window.__autoScroll._disabledByTheme) {
          try { delete window.__autoScroll._disabledByTheme; } catch (e) {}
        }
      }
    } catch (e) { /* ignore */ }

    // update any controls that use data-theme-selector
    try {
      document.querySelectorAll('[data-theme-selector]').forEach(function (el) {
        el.classList.toggle('active', el.getAttribute('data-theme') === name);
      });
    } catch (e) {}

    // Let other parts of the app know theme changed: mutation observers on body will also fire.
    try {
      var ev = new CustomEvent('theme:applied', { detail: { theme: name } });
      window.dispatchEvent(ev);
    } catch (e) {}
  }

  // Expose global API (keeps existing inline onclick="setTheme(...)" working).
  // If there is an existing applyTheme defined elsewhere, prefer it.
  window.setTheme = function (name) {
    if (typeof window.applyTheme === 'function' && window.applyTheme !== applyTheme) {
      try { window.applyTheme(name); return; } catch (e) { /* fall through */ }
    }
    applyTheme(name);
  };
  window.applyTheme = applyTheme;

  // Delegated click handler for elements with data-theme-selector/data-theme
  document.addEventListener('click', function (e) {
    try {
      var btn = e.target.closest && e.target.closest('[data-theme-selector]');
      if (!btn) return;
      if (e && typeof e.preventDefault === 'function') e.preventDefault();
      var t = btn.getAttribute('data-theme');
      if (t) setTheme(t);
    } catch (e) { /* ignore */ }
  }, false);

  // Restore theme on load (deferred scripts execute before DOMContentLoaded).
  document.addEventListener('DOMContentLoaded', function () {
    try {
      var saved = null;
      try { saved = localStorage.getItem(STORAGE_KEY); } catch (e) {}
      if (saved) {
        setTheme(saved);
      } else {
        // No saved preference - auto-detect system preference
        var systemTheme = detectSystemTheme();
        setHtmlAndBodyTheme(systemTheme);
      }
    } catch (e) { /* ignore */ }
  });

  // Listen for system theme changes and update if 'auto' is selected
  try {
    if (window.matchMedia) {
      var darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
      var lightModeQuery = window.matchMedia('(prefers-color-scheme: light)');
      
      var updateAutoTheme = function() {
        try {
          var saved = localStorage.getItem(STORAGE_KEY);
          if (saved === 'auto' || !saved) {
            var systemTheme = detectSystemTheme();
            setHtmlAndBodyTheme(systemTheme);
          }
        } catch (e) { /* ignore */ }
      };
      
      // Use addEventListener if available, otherwise use addListener
      if (darkModeQuery.addEventListener) {
        darkModeQuery.addEventListener('change', updateAutoTheme);
        lightModeQuery.addEventListener('change', updateAutoTheme);
      } else if (darkModeQuery.addListener) {
        darkModeQuery.addListener(updateAutoTheme);
        lightModeQuery.addListener(updateAutoTheme);
      }
    }
  } catch (e) { /* ignore */ }
})();

// mobile-nav.js - robust open/close for off-canvas mobile nav
// Includes:
//  - safe open/close/toggle for #mobileNav (original behavior)
//  - delegated click handler to ensure links inside mobile nav/settings navigate
//  - mobile submenu toggle behavior for .mobile-submenu-toggle buttons
// This file is idempotent and safe to drop in place (overwrites existing mobile-nav.js).

(function () {
  // Guard so this file can be safely included multiple times
  if (window.__mobileNavInitialized) return;
  window.__mobileNavInitialized = true;

  const BODY_OPEN_CLASS = 'mobile-nav-open';
  const NAV_OPEN_CLASS = 'open';

  function qs(sel, root = document) { try { return root.querySelector(sel); } catch (e) { return null; } }

  const mobileNav = qs('#mobileNav');
  const hamburger = qs('#mobileHamburger');
  const mobileNavClose = qs('#mobileNavClose');

  // simple re-entrancy guard
  let isClosing = false;
  let isOpening = false;

  function setAriaExpanded(el, expanded) {
    if (!el) return;
    try { el.setAttribute('aria-expanded', expanded ? 'true' : 'false'); } catch (e) {}
  }

  function openNav() {
    if (!mobileNav || isOpening) return;
    if (mobileNav.classList.contains(NAV_OPEN_CLASS)) {
      setAriaExpanded(hamburger, true);
      mobileNav.setAttribute('aria-hidden', 'false');
      document.body.classList.add(BODY_OPEN_CLASS);
      return;
    }
    isOpening = true;
    mobileNav.classList.add(NAV_OPEN_CLASS);
    mobileNav.setAttribute('aria-hidden', 'false');
    document.body.classList.add(BODY_OPEN_CLASS);
    setAriaExpanded(hamburger, true);
    // let CSS transitions finish; but dispatch resize immediately so adapters can recalc
    window.dispatchEvent(new Event('resize'));
    // clear flag after next tick (allow handlers to run)
    setTimeout(() => { isOpening = false; }, 250);
  }

  function closeNav() {
    if (!mobileNav || isClosing) return;
    if (!mobileNav.classList.contains(NAV_OPEN_CLASS)) {
      setAriaExpanded(hamburger, false);
      mobileNav.setAttribute('aria-hidden', 'true');
      document.body.classList.remove(BODY_OPEN_CLASS);
      return;
    }
    isClosing = true;
    // close visual state (don't programmatically trigger clicks that may re-enter this function)
    mobileNav.classList.remove(NAV_OPEN_CLASS);
    setAriaExpanded(hamburger, false);
    // remove the body class after a short delay to allow CSS to animate
    setTimeout(() => {
      document.body.classList.remove(BODY_OPEN_CLASS);
      mobileNav.setAttribute('aria-hidden', 'true');
      isClosing = false;
      // dispatch a resize so other scripts can recompute layout now nav is closed
      window.dispatchEvent(new Event('resize'));
    }, 220);
  }

  function toggleNav() {
    if (!mobileNav) return;
    if (mobileNav.classList.contains(NAV_OPEN_CLASS)) closeNav(); else openNav();
  }

  // Wire controls (safe: uses addEventListener and prevents duplicate wiring)
  function safeAddListener(el, type, fn) {
    if (!el) return;
    // attach a symbol on element to avoid duplicate binding if script included twice
    const key = '__bound_' + type;
    if (el[key]) return;
    el.addEventListener(type, fn);
    el[key] = true;
  }

  safeAddListener(hamburger, 'click', (e) => {
    e.preventDefault();
    toggleNav();
  });

  safeAddListener(mobileNavClose, 'click', (e) => {
    e.preventDefault();
    closeNav();
  });

  // close when clicking outside the inner nav area (if overlay exists or user clicks backdrop)
  safeAddListener(mobileNav, 'click', (e) => {
    // only close when clicking the backdrop element (not when clicking inside .mobile-nav-inner)
    if (e.target === mobileNav) {
      closeNav();
    }
  });

  // close on Escape
  safeAddListener(document, 'keydown', (e) => {
    if (e.key === 'Escape' && mobileNav && mobileNav.classList.contains(NAV_OPEN_CLASS)) {
      closeNav();
    }
  });

  // ensure hamburger aria state is initialized
  setAriaExpanded(hamburger, false);
  if (mobileNav) mobileNav.setAttribute('aria-hidden', 'true');

  // Expose small API for debugging or external control
  window.mobileNavControl = {
    open: openNav,
    close: closeNav,
    toggle: toggleNav,
    isOpen: () => mobileNav && mobileNav.classList.contains(NAV_OPEN_CLASS)
  };

})();

/* ----------------------------------------------------------------------
   Delegated mobile nav click handler (idempotent)
   - Ensures links inside #mobileNav and #settingsMenu navigate on mobile,
     even if other handlers call preventDefault or otherwise interfere.
   - Closes the mobile nav on navigation for better UX.
---------------------------------------------------------------------- */
(function () {
  if (window.__mobileNavDelegationBound) return;
  window.__mobileNavDelegationBound = true;

  function isLinkInMobileNav(a) {
    if (!a) return false;
    const mobileNav = document.getElementById('mobileNav');
    const settings = document.getElementById('settingsMenu');
    return (mobileNav && mobileNav.contains(a)) || (settings && settings.contains(a));
  }

  function delegateNavClicks(e) {
    try {
      const a = e.target && e.target.closest && e.target.closest('a');
      if (!a) return;
      if (!isLinkInMobileNav(a)) return;

      const href = (a.getAttribute('href') || '').trim();
      // Ignore anchors intended for JS handlers or toggles
      if (!href || href === '#' || href.toLowerCase().startsWith('javascript:')) return;

      // Close the mobile nav if open
      if (window.mobileNavControl && typeof window.mobileNavControl.close === 'function') {
        try { window.mobileNavControl.close(); } catch (err) {}
      } else {
        const mobileNav = document.getElementById('mobileNav');
        if (mobileNav) mobileNav.classList.remove('open');
        document.body.classList.remove('mobile-nav-open');
      }

      // Ensure navigation occurs even if other handlers prevented it.
      // Use a tiny timeout to let other handlers finish.
      setTimeout(() => {
        try {
          // only navigate if target differs from current location hash or pathname
          const dest = new URL(href, window.location.href);
          const sameOrigin = dest.origin === window.location.origin;
          const samePathAndHash = (dest.pathname === window.location.pathname && dest.hash === window.location.hash);
          if (!samePathAndHash) {
            window.location.href = dest.href;
          }
        } catch (err) {
          // if URL parsing fails, fall back to setting location directly
          try { window.location.href = href; } catch (e) {}
        }
      }, 20);
    } catch (err) {
      console.error('delegateNavClicks err', err);
    }
  }

  // Use capture phase so this runs before many listeners that may call preventDefault
  document.addEventListener('click', delegateNavClicks, true);
})();

/* ----------------------------------------------------------------------
   Mobile submenu toggle behavior (idempotent)
   - Wires .mobile-submenu-toggle buttons to expand/collapse their lists.
   - Updates aria-expanded and aria-hidden attributes and toggles .open class.
---------------------------------------------------------------------- */
(function () {
  if (window.__mobileSubmenuToggleBound) return;
  window.__mobileSubmenuToggleBound = true;

  function toggleSubmenu(button, expand) {
    try {
      if (!button) return;
      const controls = button.getAttribute('aria-controls');
      const list = controls ? document.getElementById(controls) : button.nextElementSibling;
      const parentLi = button.closest && button.closest('.mobile-submenu');
      // NOTE: use the class 'open' so it matches mobile-submenu.css expectations
      const willExpand = (typeof expand === 'boolean') ? expand : !(button.getAttribute('aria-expanded') === 'true');

      button.setAttribute('aria-expanded', willExpand ? 'true' : 'false');
      if (list) {
        list.setAttribute('aria-hidden', willExpand ? 'false' : 'true');
      }
      if (parentLi) {
        if (willExpand) parentLi.classList.add('open'); else parentLi.classList.remove('open');
      }
      // dispatch resize so other scripts can recompute layout
      window.dispatchEvent(new Event('resize'));
    } catch (err) { console.debug('submenu toggle err', err); }
  }

  // Handle click on toggle buttons
  document.addEventListener('click', function (ev) {
    try {
      const btn = ev.target && ev.target.closest && ev.target.closest('.mobile-submenu-toggle');
      if (!btn) return;
      ev.preventDefault();
      toggleSubmenu(btn);
    } catch (e) { /* ignore */ }
  });

  // Keyboard support for Enter / Space
  document.addEventListener('keydown', function (ev) {
    try {
      if (!ev || (ev.key !== 'Enter' && ev.key !== ' ' && ev.key !== 'Spacebar')) return;
      const btn = ev.target && ev.target.closest && ev.target.closest('.mobile-submenu-toggle');
      if (!btn) return;
      ev.preventDefault();
      toggleSubmenu(btn);
    } catch (e) { /* ignore */ }
  });

  // Initialize current state for any toggle buttons already in DOM
  document.addEventListener('DOMContentLoaded', () => {
    const toggles = Array.from(document.querySelectorAll('.mobile-submenu-toggle'));
    toggles.forEach(btn => {
      const controls = btn.getAttribute('aria-controls');
      const list = controls ? document.getElementById(controls) : btn.nextElementSibling;
      const expanded = (btn.getAttribute('aria-expanded') === 'true');
      if (list) list.setAttribute('aria-hidden', expanded ? 'false' : 'true');
      const parentLi = btn.closest && btn.closest('.mobile-submenu');
      if (parentLi) {
        if (expanded) parentLi.classList.add('open'); else parentLi.classList.remove('open');
      }
    });
  });
})();

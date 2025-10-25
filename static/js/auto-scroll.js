// Robust auto-scroll with runtime theme-change handling (tvguide1990).
// Replaces previous auto-scroll behavior: stops when theme becomes tvguide1990,
// reflects the stored preference, and still allows the user to re-enable via settings.

(function () {
  const PREF_KEY = 'autoScrollEnabled';
  function prefEnabled() { return localStorage.getItem(PREF_KEY) !== 'false'; }
  function setPref(v) { localStorage.setItem(PREF_KEY, v ? 'true' : 'false'); }

  const SELECTOR_PRIORITY = ['#guideOuter', '.guide-outer', '.grid-col'];
  const scrollSpeed = 1.2; // px per frame - visible
  const idleDelay = 5000; // ms

  let scroller = null;
  let rafId = null;
  let isScrolling = false;
  let lastActivity = Date.now();
  let idleInterval = null;
  let bodyObserver = null;

  function log(...args) {
    if (window && window.console && console.debug) console.debug.apply(console, ['[auto-scroll]'].concat(args));
  }

  function findBestScroller() {
    const nodes = SELECTOR_PRIORITY.map(s => Array.from(document.querySelectorAll(s))).flat();
    if (!nodes.length) return null;
    let best = null;
    nodes.forEach(n => {
      try {
        const delta = Math.max(0, n.scrollHeight - n.clientHeight);
        if (!best || delta > best.delta) best = { el: n, delta };
      } catch (e) { /* ignore */ }
    });
    if (!best && document.getElementById('guideOuter')) {
      const g = document.getElementById('guideOuter');
      return { el: g, delta: Math.max(0, g.scrollHeight - g.clientHeight) };
    }
    return best;
  }

  function ensureScrollerStyles(el) {
    try {
      const cs = getComputedStyle(el);
      if (!/(auto|scroll)/.test(cs.overflowY)) el.style.overflowY = 'auto';
      if (!el.style.maxHeight && cs.maxHeight === 'none') {
        el.style.maxHeight = 'calc(100vh - 420px)';
      }
      el.style.scrollBehavior = 'auto';
    } catch (e) { /* ignore */ }
  }

  function markClone(node) {
    try {
      node.classList.add('__auto_scroll_clone');
      node.dataset.__autoScrollClone = '1';
      node.setAttribute('aria-hidden', 'true');
      node.style.pointerEvents = 'none';
      Array.from(node.querySelectorAll('[id]')).forEach(el => el.removeAttribute('id'));
    } catch (e) { /* ignore */ }
  }

  // Generic clone-for-seamless-loop: clones enough rows from the start/end to fill visible area.
  function cloneRowsForSeamlessLoop(scrollerEl) {
    try {
      if (!scrollerEl) return;
      if (scrollerEl.dataset.__autoScrollCloned === '1') return; // already applied

      let rows = Array.from(scrollerEl.querySelectorAll('.chan-col'));
      if (!rows.length) {
        rows = Array.from(scrollerEl.children).filter(n => n.nodeType === 1);
      }
      if (!rows.length) {
        log('cloneRowsForSeamlessLoop: no rows found; skipping clone');
        scrollerEl.dataset.__autoScrollCloned = '1';
        return;
      }

      let rowHeight = rows[0].getBoundingClientRect().height || rows[0].offsetHeight || 40;
      if (!isFinite(rowHeight) || rowHeight <= 0) rowHeight = 40;
      const visibleRows = Math.max(1, Math.ceil(scrollerEl.clientHeight / rowHeight));
      const clonesPerSide = visibleRows + 1;

      const totalRows = rows.length;
      const leftClones = Math.min(clonesPerSide, totalRows);
      const rightClones = Math.min(clonesPerSide, totalRows);

      const toPrepend = [];
      for (let i = 0; i < leftClones; i++) {
        const src = rows[totalRows - 1 - i];
        if (!src) break;
        const clone = src.cloneNode(true);
        markClone(clone);
        toPrepend.push(clone);
      }
      for (let i = toPrepend.length - 1; i >= 0; i--) {
        scrollerEl.insertBefore(toPrepend[i], scrollerEl.firstChild);
      }

      for (let i = 0; i < rightClones; i++) {
        const src = rows[i];
        if (!src) break;
        const clone = src.cloneNode(true);
        markClone(clone);
        scrollerEl.appendChild(clone);
      }

      scrollerEl.dataset.__autoScrollCloned = '1';
      log('cloneRowsForSeamlessLoop: prepended', toPrepend.length, 'and appended', rightClones, '(visibleRows=' + visibleRows + ')');
    } catch (err) {
      log('cloneRowsForSeamlessLoop error', err);
    }
  }

  function startDrift() {
    if (!prefEnabled()) { log('pref disabled - not starting'); return; }
    if (!scroller) {
      const best = findBestScroller();
      if (!best) { log('no scroller found'); return; }
      scroller = best.el;
      ensureScrollerStyles(scroller);
      // If tvguide1990 is active, apply clones for seamlessness
      if (document.body.classList.contains('tvguide1990')) {
        cloneRowsForSeamlessLoop(scroller);
      }
    }
    if (isScrolling) return;
    isScrolling = true;
    if (rafId) cancelAnimationFrame(rafId);
    function frame() {
      if (!isScrolling) return;
      if (document.hidden) { rafId = requestAnimationFrame(frame); return; }
      try {
        if (scroller && scroller.scrollHeight > scroller.clientHeight) {
          scroller.scrollTop += scrollSpeed;
          if (scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 1) scroller.scrollTop = 0;
        }
      } catch (e) { /* ignore */ }
      rafId = requestAnimationFrame(frame);
    }
    rafId = requestAnimationFrame(frame);
    log('started (robust)');
  }

  function stopDrift(reason) {
    if (!isScrolling) {
      log('stop called (no-op)', reason || '');
      return;
    }
    isScrolling = false;
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    log('stopped', reason || '');
  }

  // Only treat deliberate interactions that happen inside the scroller as activity.
  function onInsidePointerDown(e) {
    try {
      const tgt = e.target;
      if (scroller && scroller.contains(tgt)) {
        lastActivity = Date.now();
        stopDrift('pointerdown-inside');
      }
    } catch (err) { /* ignore */ }
  }
  function onInsideTouchStart(e) {
    try {
      const tgt = e.target;
      if (scroller && scroller.contains(tgt)) {
        lastActivity = Date.now();
        stopDrift('touchstart-inside');
      }
    } catch (err) { /* ignore */ }
  }
  function onInsideFocusIn(e) {
    try {
      const tgt = e.target;
      if (scroller && scroller.contains(tgt)) {
        lastActivity = Date.now();
        stopDrift('focusin-inside');
      }
    } catch (err) { /* ignore */ }
  }
  function onInsideClick(e) {
    try {
      const tgt = e.target;
      if (scroller && scroller.contains(tgt)) {
        lastActivity = Date.now();
        stopDrift('click-inside');
      }
    } catch (err) { /* ignore */ }
  }

  function periodicIdle() {
    if (!isScrolling && prefEnabled() && (Date.now() - lastActivity > idleDelay)) startDrift();
  }

  function attachHandlers() {
    if (!scroller) return;
    scroller.addEventListener('pointerdown', onInsidePointerDown, { passive: true });
    scroller.addEventListener('touchstart', onInsideTouchStart, { passive: true });
    scroller.addEventListener('focusin', onInsideFocusIn);
    scroller.addEventListener('click', onInsideClick, { passive: true });
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && prefEnabled() && !isScrolling && (Date.now() - lastActivity > idleDelay)) startDrift();
    });
  }

  // React to runtime theme changes: if tvguide1990 is added, stop + set pref false (UI will show disabled).
  function observeBodyThemeChanges() {
    if (!document.body || typeof MutationObserver === 'undefined') return;
    if (bodyObserver) return; // already observing
    bodyObserver = new MutationObserver(mutations => {
      for (const m of mutations) {
        if (m.type === 'attributes' && m.attributeName === 'class') {
          const hasTV1990 = document.body.classList.contains('tvguide1990');
          if (hasTV1990) {
            // user asked that switching into tvguide1990 should stop scrolling
            try {
              log('theme changed: tvguide1990 detected -> stopping auto-scroll and setting preference=false');
              // persist the user's previous preference so we can restore if desired
              window.__autoScroll && (window.__autoScroll._previousPref = prefEnabled());
              setPref(false);
              stopDrift('theme-tvguide1990-added');
              // apply clones so visual loop is consistent if later enabled
              if (scroller) cloneRowsForSeamlessLoop(scroller);
            } catch (e) { log('theme-change handling error', e); }
          } else {
            // theme removed: if we previously recorded a previousPref restore it
            try {
              const prev = window.__autoScroll && window.__autoScroll._previousPref;
              if (typeof prev !== 'undefined') {
                setPref(!!prev);
                delete window.__autoScroll._previousPref;
                log('theme removed: restored previous preference to', prefEnabled());
                if (prefEnabled()) startDrift();
              }
            } catch (e) { log('theme-change restore error', e); }
          }
        }
      }
    });
    bodyObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    log('body theme observer installed');
  }

  function init() {
    const best = findBestScroller();
    if (best) {
      scroller = best.el;
      ensureScrollerStyles(scroller);

      // If starting while tvguide1990 is already active: stop and set pref false per requirement.
      if (document.body.classList.contains('tvguide1990')) {
        log('init: tvguide1990 active on load -> stopping auto-scroll and setting preference=false');
        window.__autoScroll && (window.__autoScroll._previousPref = prefEnabled());
        setPref(false);
        stopDrift('theme-tvguide1990-onload');
        cloneRowsForSeamlessLoop(scroller);
      } else {
        // apply clones only when the theme is tvguide1990; otherwise clones are not applied
      }

      attachHandlers();
    } else {
      log('no scroller found during init');
    }

    observeBodyThemeChanges();

    if (idleInterval) clearInterval(idleInterval);
    idleInterval = setInterval(periodicIdle, 1000);
    setTimeout(() => { if (prefEnabled() && (Date.now() - lastActivity > idleDelay)) startDrift(); }, idleDelay);

    // stable API
    window.__autoScroll = window.__autoScroll || {};
    window.__autoScroll.start = startDrift;
    window.__autoScroll.stop = stopDrift;
    window.__autoScroll.status = () => isScrolling;
    window.__autoScroll.pref = prefEnabled;
    window.__autoScroll.scrollers = () => scroller ? [scroller] : [];
    window.__autoScroll.recompute = () => { scroller = null; };

    window.__autoScroll.enable = function() {
      try {
        setPref(true);
        lastActivity = Date.now();
        startDrift();
        log('enabled via API');
      } catch (e) { log('enable error', e); }
    };
    window.__autoScroll.disable = function() {
      try {
        setPref(false);
        stopDrift('disabled-via-api');
        log('disabled via API');
      } catch (e) { log('disable error', e); }
    };
    window.__autoScroll.toggle = function() {
      try {
        if (prefEnabled()) { window.__autoScroll.disable(); } else { window.__autoScroll.enable(); }
        return prefEnabled();
      } catch (e) { log('toggle error', e); return prefEnabled(); }
    };
    window.__autoScroll.debug = function() {
      return { lastActivity, idleDelay, scrollSpeed, isScrolling, pref: prefEnabled(), scrollerInfo: scroller ? {id: scroller.id, scrollHeight: scroller.scrollHeight, clientHeight: scroller.clientHeight} : null };
    };

    try { Object.defineProperty(window.__autoScroll, 'prefValue', { get: prefEnabled, configurable: true }); } catch (e) {}
    log('minimal initialized');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

})();

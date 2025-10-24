// Auto-scroll (vertical) for guide & channels: resumes after 5s of inactivity, loops vertically.
// Drop this file into /static/js/auto-scroll.js and include it with `defer` in your template.

(function () {
  const autoScrollEnabled = true;
  if (!autoScrollEnabled) return;

  // Prefer scrolling the whole guide container; fallback to per-row .grid-col if needed
  const selectors = ['#guideOuter', '.guide-outer', '.grid-col'];
  let scrollers = [];

  const scrollSpeed = 0.6;     // px per frame; increase for testing
  const idleDelay = 5000;      // 5s before starting/resuming
  let lastInteraction = Date.now();
  let isScrolling = false;
  let rafId = null;
  let idleIntervalId = null;

  const scrollerHandlers = new WeakMap();
  let globalMouseGuardAttached = false;

  function findScrollers() {
    const nodes = selectors
      .map(sel => Array.from(document.querySelectorAll(sel)))
      .reduce((a, b) => a.concat(b), []);
    // unique & only those that can scroll (scrollHeight > clientHeight)
    scrollers = nodes.filter((el, i, arr) => arr.indexOf(el) === i && el.scrollHeight > el.clientHeight);
    console.debug('[auto-scroll] findScrollers -> selectors:', selectors, 'foundNodes:', nodes.length, 'usableScrollers:', scrollers.length);
    scrollers.forEach((s, idx) => {
      console.debug(`[auto-scroll] scroller[${idx}]`, s, 'scrollHeight:', s.scrollHeight, 'clientHeight:', s.clientHeight);
    });
    return scrollers.length;
  }

  function ensureStyles() {
    scrollers.forEach(s => {
      const style = getComputedStyle(s);
      if (!/(auto|scroll)/.test(style.overflowY)) s.style.overflowY = 'auto';
      s.style.scrollBehavior = 'auto';
    });
  }

  function attachScrollerInteractionHandlers() {
    scrollers.forEach(s => {
      if (scrollerHandlers.has(s)) return;

      const onEnter = () => {
        lastInteraction = Date.now();
        stopDrift();
      };
      const onTouchOrPointer = () => {
        lastInteraction = Date.now();
        stopDrift();
      };
      const onFocusIn = () => {
        lastInteraction = Date.now();
        stopDrift();
      };

      s.addEventListener('mouseenter', onEnter, { passive: true });
      s.addEventListener('touchstart', onTouchOrPointer, { passive: true });
      s.addEventListener('pointerdown', onTouchOrPointer, { passive: true });
      s.addEventListener('focusin', onFocusIn);

      scrollerHandlers.set(s, { onEnter, onTouchOrPointer, onFocusIn });
    });
  }

  // Minimal guard: only treat mousemove as activity if the pointer is over a scroller.
  function attachGlobalMouseMoveGuard() {
    if (globalMouseGuardAttached) return;
    globalMouseGuardAttached = true;

    document.addEventListener('mousemove', (e) => {
      try {
        if (scrollers && scrollers.some(s => s.contains(e.target))) {
          lastInteraction = Date.now();
          stopDrift();
        }
      } catch (err) { /* ignore */ }
    }, { passive: true });
  }

  function drift() {
    if (!isScrolling) return;
    if (document.hidden) {
      rafId = requestAnimationFrame(drift);
      return;
    }

    scrollers.forEach(s => {
      if (s.scrollHeight <= s.clientHeight) return;
      s.scrollTop += scrollSpeed;
      if (s.scrollTop + s.clientHeight >= s.scrollHeight - 1) {
        s.scrollTop = 0;
      }
    });

    rafId = requestAnimationFrame(drift);
  }

  function startDrift() {
    if (!isScrolling) {
      if (!scrollers.length) {
        console.debug('[auto-scroll] start requested but no scrollers available');
        return;
      }
      isScrolling = true;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(drift);
      console.debug('[auto-scroll] started (vertical)');
    }
  }

  function stopDrift() {
    if (isScrolling) {
      isScrolling = false;
      console.debug('[auto-scroll] stopped');
    }
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  // A click anywhere explicitly stops the auto-scroll
  document.addEventListener('click', () => {
    lastInteraction = Date.now();
    stopDrift();
  }, { passive: true });

  // We intentionally do not stop on global mousemove except when over a scroller (guard above)

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !isScrolling && (Date.now() - lastInteraction > idleDelay)) {
      startDrift();
    }
  });

  function periodicIdleCheck() {
    if (!isScrolling && (Date.now() - lastInteraction > idleDelay)) startDrift();
  }

  function init() {
    if (!findScrollers()) {
      // retry a few times in case elements are added later
      let tries = 0;
      const retry = setInterval(() => {
        if (findScrollers() || ++tries >= 10) {
          clearInterval(retry);
          if (!scrollers.length) {
            console.debug('[auto-scroll] no scrollable elements found after retries; auto-scroll disabled');
            return;
          }
          ensureStyles();
          attachScrollerInteractionHandlers();
          attachGlobalMouseMoveGuard();
          idleIntervalId = setInterval(periodicIdleCheck, 1000);
          setTimeout(() => { if (Date.now() - lastInteraction > idleDelay) startDrift(); }, idleDelay);
        }
      }, 300);
    } else {
      ensureStyles();
      attachScrollerInteractionHandlers();
      attachGlobalMouseMoveGuard();
      idleIntervalId = setInterval(periodicIdleCheck, 1000);
      setTimeout(() => { if (Date.now() - lastInteraction > idleDelay) startDrift(); }, idleDelay);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Dev hooks
  window.__autoScroll = {
    start: startDrift,
    stop: stopDrift,
    status: () => isScrolling,
    scrollers: () => scrollers,
    debug: () => ({ lastInteraction, idleDelay, scrollSpeed })
  };
})();

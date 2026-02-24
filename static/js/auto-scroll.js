// auto-scroll v36.3 — deterministic wrap + RAF primary with interval fallback watchdog.
// - Clone full row elements so program cells are carried with clones.
// - Deterministic immediate wrap to prep offset to avoid stop/restart races.
// - Primary animation via requestAnimationFrame; fallback watcher uses setInterval to nudge scrollTop
//   when RAF hasn't advanced (handles throttling/race across browsers).
// - Exposes status and cloneNow APIs.

(function () {
  const PREF_KEY = 'autoScrollEnabled';
  function prefEnabled() { return localStorage.getItem(PREF_KEY) !== 'false'; }
  function setPref(v) { localStorage.setItem(PREF_KEY, v ? 'true' : 'false'); }

  const SELECTOR_PRIORITY = ['#guideOuter', '.guide-outer', '.grid-col'];
  let scrollSpeed = 1.2; // px per frame (visual)
  const idleDelay = 15000; // ms initial inactivity/start delay (15s)
  const waitForContentMs = 5000; // wait up to 5s for rows to be populated before cloning
  const contentSampleCount = 3; // sample when checking readiness

  const PROGRAM_CELL_SELECTORS = [
    '.programme', '.program', '.prog', '.prog-col', '.prog-cell', '.program-cell',
    '.title', '.epg-item', '.time', '.programme-item', '.programs', '.epg'
  ];

  let scroller = null;
  let rafId = null;
  let isScrolling = false;
  let lastActivity = Date.now();
  let idleInterval = null;
  let watchdogInterval = null;

  // timestamps for watchdog: last time frameLoop actually ran
  let lastFrameTime = 0;

  let loopMode = true;
  let endReached = false;
  let endReachedAt = 0;
  let autoRestart = false;
  let autoRestartDelayMs = 30000;

  function log(...args) {
    if (window && window.console && console.debug) console.debug.apply(console, ['[auto-scroll v36.3]'].concat(args));
  }

  function findScroller() {
    const nodes = SELECTOR_PRIORITY.map(s => Array.from(document.querySelectorAll(s))).flat();
    if (!nodes.length) return null;
    let best = null;
    nodes.forEach(n => {
      try {
        const delta = Math.max(0, n.scrollHeight - n.clientHeight);
        if (!best || delta > best.delta) best = { el: n, delta };
      } catch (e) {}
    });
    return best ? best.el : null;
  }

  function ensureStyles(el) {
    try {
      const cs = getComputedStyle(el);
      if (!/(auto|scroll)/.test(cs.overflowY)) el.style.overflowY = 'auto';
      // Do NOT set maxHeight here: guide-outer is sized by flex:1 inside #appZoomRoot.
      // A hardcoded calc(100vh - 420px) would cap it at 300px regardless of display-size
      // zoom level, leaving a blank theme-coloured gap below the channel rows.
      el.style.scrollBehavior = 'auto';
    } catch (e) {}
  }

  function supportsNativeSmoothScroll() {
    try { return 'scrollBehavior' in document.documentElement.style; } catch (e) { return false; }
  }

  function smoothScrollTo(el, targetTop, duration = 650) {
    if (!el) return Promise.resolve();
    if (supportsNativeSmoothScroll()) {
      try {
        el.scrollTo({ top: targetTop, behavior: 'smooth' });
        return new Promise(resolve => setTimeout(resolve, duration));
      } catch (e) {}
    }
    return new Promise(resolve => {
      const start = el.scrollTop;
      const change = targetTop - start;
      const startTime = performance.now();
      const dur = Math.max(1, duration);
      const ease = t => (t < 0.5) ? (2 * t * t) : (-1 + (4 - 2 * t) * t);
      function step(now) {
        const elapsed = now - startTime;
        const t = Math.min(1, elapsed / dur);
        try { el.scrollTop = start + change * ease(t); } catch (e) {}
        if (t < 1) requestAnimationFrame(step);
        else resolve();
      }
      requestAnimationFrame(step);
    });
  }

  function markClone(node, srcId) {
    try {
      node.classList.add('__auto_scroll_clone');
      node.dataset.autoScrollClone = '1';
      if (srcId) node.dataset.autoScrollSrcid = srcId;
      Array.from(node.querySelectorAll('[id]')).forEach(el => el.removeAttribute('id'));
    } catch (e) {}
  }

  function getOriginalRows(sc) {
    try {
      const chanCols = Array.from(sc.querySelectorAll('.chan-col'));
      const rowsSet = new Set();
      if (chanCols.length) {
        chanCols.forEach(c => {
          const row = c.closest('.guide-row') || c.parentElement;
          if (row && row.nodeType === 1) rowsSet.add(row);
        });
      } else {
        Array.from(sc.children).forEach(ch => { if (ch && ch.nodeType === 1) rowsSet.add(ch); });
      }
      return Array.from(rowsSet).filter(r => !(r.dataset && (r.dataset.autoScrollClone === '1' || r.dataset.__autoScrollClone === '1')));
    } catch (e) {
      return [];
    }
  }

  function rowHasContent(r) {
    if (!r) return false;
    const name = r.querySelector && r.querySelector('.chan-name');
    if (name && name.textContent && name.textContent.trim().length) return true;
    for (const sel of PROGRAM_CELL_SELECTORS) {
      const el = r.querySelector(sel);
      if (el && el.textContent && el.textContent.trim().length) return true;
    }
    const txt = r.textContent || '';
    return txt.trim().length > 4;
  }

  function scrollerHasProgramInfo(sc) {
    try {
      for (const sel of PROGRAM_CELL_SELECTORS) {
        const el = sc.querySelector(sel);
        if (el && el.textContent && el.textContent.trim().length > 0) return true;
      }
      if ((sc.innerText || sc.textContent || '').trim().length > 60) return true;
    } catch (e) {}
    return false;
  }

  function waitForProgramInfo(sc, timeoutMs = 4000) {
    return new Promise(resolve => {
      const start = Date.now();
      const check = () => {
        try {
          if (scrollerHasProgramInfo(sc)) return resolve(true);
          if (Date.now() - start >= timeoutMs) return resolve(false);
        } catch (e) { return resolve(false); }
        setTimeout(check, 150);
      };
      check();
    });
  }

  function waitForContent(sc, timeoutMs = waitForContentMs, sampleCount = contentSampleCount) {
    return new Promise(resolve => {
      const start = Date.now();
      const check = () => {
        const rows = getOriginalRows(sc);
        let ok = false;
        for (let i = 0; i < Math.min(sampleCount, rows.length); i++) {
          if (rowHasContent(rows[i])) { ok = true; break; }
        }
        if (ok) return resolve(true);
        if (Date.now() - start >= timeoutMs) return resolve(false);
        setTimeout(check, 150);
      };
      check();
    });
  }

  // Clone rows (full row elements). Returns Promise resolved once clones are added and prep offset stored.
  function cloneOnce(sc) {
    return new Promise(resolve => {
      try {
        if (!sc) return resolve(0);
        if (sc.dataset.__autoScrollCloned === '1') return resolve(0);

        const originals = getOriginalRows(sc);
        if (!originals.length) { sc.dataset.__autoScrollCloned = '1'; return resolve(0); }

        originals.forEach((orig, idx) => {
          if (!orig.dataset.autoScrollSrcid) orig.dataset.autoScrollSrcid = 'asrc-' + idx + '-' + Date.now();
        });

        let rowHeight = originals[0].getBoundingClientRect().height || originals[0].offsetHeight || 40;
        if (!isFinite(rowHeight) || rowHeight <= 0) rowHeight = 40;
        const visibleRows = Math.max(1, Math.ceil(sc.clientHeight / rowHeight));
        const clonesPerSide = visibleRows + 1;

        const total = originals.length;
        const left = Math.min(clonesPerSide, total);
        const right = Math.min(clonesPerSide, total);

        const leftClones = [];
        for (let i = 0; i < left; i++) {
          const srcRow = originals[total - 1 - i];
          if (!srcRow) break;
          const cloneRow = srcRow.cloneNode(true);
          try { cloneRow.innerHTML = srcRow.innerHTML; } catch (e) {}
          markClone(cloneRow, srcRow.dataset.autoScrollSrcid);
          leftClones.push(cloneRow);
        }

        let prependedHeight = 0;
        for (let i = leftClones.length - 1; i >= 0; i--) sc.insertBefore(leftClones[i], sc.firstChild);
        for (let i = 0; i < leftClones.length; i++) {
          const h = leftClones[i].getBoundingClientRect().height || leftClones[i].offsetHeight || 0;
          prependedHeight += h;
        }

        for (let i = 0; i < right; i++) {
          const srcRow = originals[i];
          if (!srcRow) break;
          const cloneRow = srcRow.cloneNode(true);
          try { cloneRow.innerHTML = srcRow.innerHTML; } catch (e) {}
          markClone(cloneRow, srcRow.dataset.autoScrollSrcid);
          sc.appendChild(cloneRow);
        }

        if (prependedHeight > 0) {
          try { sc.scrollTop = Number(prependedHeight) || 0; } catch (e) {}
        }

        // store and mark after waiting for programs (best-effort)
        waitForProgramInfo(sc, 4000).then(found => {
          try {
            sc.dataset.__autoScrollPrependedHeight = String(prependedHeight || 0);
            sc.dataset.__autoScrollCloned = '1';
          } catch (e) {}
          log('cloneOnce: prepended', leftClones.length, 'and appended', right, 'prependedHeight=' + prependedHeight, 'programsDetected=' + !!found);
          resolve(leftClones.length + right);
        }).catch(() => {
          try {
            sc.dataset.__autoScrollPrependedHeight = String(prependedHeight || 0);
            sc.dataset.__autoScrollCloned = '1';
          } catch (e) {}
          log('cloneOnce: program wait failed; proceeding. prependedHeight=' + prependedHeight);
          resolve(leftClones.length + right);
        });

      } catch (e) {
        log('cloneOnce error', e);
        resolve(0);
      }
    });
  }

  // Dispatch synthetic events to trigger program-updaters that listen for hover/focus.
  function refreshProgramInfoForVisible(sc) {
    try {
      if (!sc) return;
      const rows = getOriginalRows(sc);
      if (!rows.length) return;
      const scRect = sc.getBoundingClientRect();
      let target = rows.find(r => {
        const rect = r.getBoundingClientRect();
        return (rect.top >= scRect.top - 2 && rect.top <= scRect.bottom + 2);
      });
      if (!target) target = rows[0];
      if (!target) return;
      ['mouseenter', 'mouseover', 'focus', 'mousemove'].forEach(type => {
        try { target.dispatchEvent(new Event(type, { bubbles: true, cancelable: true })); } catch (e) {}
      });
      try { target.dispatchEvent(new PointerEvent('pointerover', { bubbles: true })); } catch (e) {}
      log('refreshProgramInfoForVisible: dispatched events on', target.dataset && target.dataset.autoScrollSrcid ? target.dataset.autoScrollSrcid : target);
    } catch (e) { log('refreshProgramInfoForVisible error', e); }
  }

  // Start the watchdog interval that nudges scrollTop if RAF isn't advancing.
  function startWatchdog() {
    stopWatchdog();
    watchdogInterval = setInterval(() => {
      try {
        if (!isScrolling || !scroller) return;
        const now = performance.now();
        // If RAF hasn't run in last 250ms, nudge scrollTop a tiny amount
        if (now - lastFrameTime > 250) {
          try { scroller.scrollTop = (scroller.scrollTop || 0) + scrollSpeed; } catch (e) {}
          // update lastFrameTime so we don't double-nudge
          lastFrameTime = now;
        }
      } catch (e) {}
    }, 150);
  }
  function stopWatchdog() { try { if (watchdogInterval) { clearInterval(watchdogInterval); watchdogInterval = null; } } catch (e) {} }

  // frameLoop: primary RAF animation; updates lastFrameTime on each run
  function frameLoop() {
    if (!isScrolling) return;
    if (document.hidden) { rafId = requestAnimationFrame(frameLoop); return; }
    try {
      lastFrameTime = performance.now();
      if (scroller && scroller.scrollHeight > scroller.clientHeight) {
        scroller.scrollTop += scrollSpeed;
        const maxScroll = scroller.scrollHeight - scroller.clientHeight;
        if (scroller.scrollTop >= maxScroll - 0.5) {
          if (scroller.dataset.__autoScrollCloned === '1') {
            // immediate deterministic wrap to prep (avoid race)
            const prep = Number(scroller.dataset.__autoScrollPrependedHeight) || 0;
            log('wrap detected. cur', scroller.scrollTop, 'max', maxScroll, 'prep', prep);
            try { scroller.scrollTop = prep; } catch (e) {}
            // small tick then refresh and resume
            setTimeout(() => {
              try { refreshProgramInfoForVisible(scroller); } catch (e) {}
            }, 60);
            // continue RAF animation after small delay
            setTimeout(() => { if (prefEnabled()) { if (!isScrolling) isScrolling = true; rafId = requestAnimationFrame(frameLoop); } }, 120);
            return;
          } else {
            if (loopMode) {
              log('wrap reached but no clones present -> attempting cloneOnce() now');
              cloneOnce(scroller).then(() => { setTimeout(() => { if (prefEnabled()) startDrift(); }, 80); }).catch(() => { scroller.scrollTop = maxScroll; stopDrift('end-reached'); });
              return;
            } else {
              scroller.scrollTop = maxScroll;
              stopDrift('end-reached');
              return;
            }
          }
        }
      }
    } catch (e) {}
    rafId = requestAnimationFrame(frameLoop);
  }

  // Start RAF + watchdog
  function startAnimation() {
    // avoid double-start
    if (isScrolling) return;
    isScrolling = true;
    lastFrameTime = performance.now();
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(frameLoop);
    startWatchdog();
    log('animation started (RAF + watchdog)');
  }

  function stopAnimation() {
    try { if (rafId) { cancelAnimationFrame(rafId); rafId = null; } } catch (e) {}
    stopWatchdog();
    isScrolling = false;
    log('animation stopped');
  }

  // start/resume auto-scroll drift (cloning step included)
  function startDrift() {
    if (!prefEnabled()) { log('pref disabled - not starting'); return; }
    endReached = false;
    endReachedAt = 0;

    if (!scroller) {
      scroller = findScroller();
      if (!scroller) { log('no scroller found'); return; }
      ensureStyles(scroller);
    }

    if (loopMode && scroller && scroller.dataset.__autoScrollCloned !== '1') {
      waitForContent(scroller, waitForContentMs, contentSampleCount).then(() => cloneOnce(scroller)).catch(() => cloneOnce(scroller)).then(() => {
        // start animation after a tiny tick to let layout settle
        setTimeout(() => startAnimation(), 60);
      });
      return;
    }

    // clones already present or no cloning needed
    startAnimation();
  }

  function stopDrift(reason) {
    if (!isScrolling) { log('stop called (no-op)', reason || ''); return; }
    stopAnimation();
    if (reason === 'end-reached') {
      endReached = true;
      endReachedAt = Date.now();
      log('end reached: preventing auto-restart until cleared at', endReachedAt);
    }
    log('auto-scroll stopped', reason || '');
  }

  function onInsideActivity(e) {
    try {
      const tgt = e.target;
      if (scroller && scroller.contains(tgt)) {
        lastActivity = Date.now();
        stopDrift('interaction-inside');
      }
    } catch (e) {}
  }

  function periodicIdle() {
    if (endReached && autoRestart) {
      const since = Date.now() - endReachedAt;
      if (since >= autoRestartDelayMs) {
        endReached = false; endReachedAt = 0;
        if (!isScrolling && prefEnabled() && (Date.now() - lastActivity > idleDelay)) startDrift();
        return;
      }
      return;
    }
    if (!isScrolling && !endReached && prefEnabled() && (Date.now() - lastActivity > idleDelay)) startDrift();
  }

  function attachHandlers() {
    if (!scroller) return;
    scroller.addEventListener('pointerdown', onInsideActivity, { passive: true });
    scroller.addEventListener('touchstart', onInsideActivity, { passive: true });
    scroller.addEventListener('focusin', onInsideActivity);
    scroller.addEventListener('click', onInsideActivity, { passive: true });
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && prefEnabled() && !isScrolling && (Date.now() - lastActivity > idleDelay)) startDrift();
    });
  }

  function init() {
    scroller = findScroller();
    if (scroller) { ensureStyles(scroller); attachHandlers(); } else { log('no scroller found during init'); }
    if (idleInterval) clearInterval(idleInterval);
    idleInterval = setInterval(periodicIdle, 1000);
    setTimeout(() => { if (prefEnabled() && (Date.now() - lastActivity > idleDelay)) startDrift(); }, idleDelay);

    window.__autoScroll = window.__autoScroll || {};
    window.__autoScroll.start = startDrift;
    window.__autoScroll.stop = stopDrift;
    window.__autoScroll.enable = function(){ setPref(true); lastActivity = Date.now(); endReached = false; startDrift(); };
    window.__autoScroll.disable = function(){ setPref(false); stopDrift('disabled-via-api'); };
    window.__autoScroll.setLoop = function(on){ loopMode = !!on; log('setLoop ->', loopMode); };
    window.__autoScroll.getLoop = function(){ return !!loopMode; };
    window.__autoScroll.setAutoRestart = function(enabled, delayMs){ autoRestart = !!enabled; if (typeof delayMs === 'number') autoRestartDelayMs = Number(delayMs); };
    window.__autoScroll.clearEnd = function(){ endReached = false; endReachedAt = 0; };
    window.__autoScroll.recompute = function(){ scroller = null; };
    window.__autoScroll.cloneNow = function(){ if (!scroller) scroller = findScroller(); return cloneOnce(scroller); };
    window.__autoScroll.setSpeed = function(speed) {
      if (typeof speed === 'number' && speed > 0) {
        scrollSpeed = speed;
        log('setSpeed ->', scrollSpeed);
      } else {
        log('setSpeed: invalid speed', speed);
      }
    };
    window.__autoScroll.getSpeed = function(){ return scrollSpeed; };
    window.__autoScroll.status = function(){ return { isScrolling, pref: prefEnabled(), loopMode, scrollerInfo: scroller ? { id: scroller.id, scrollTop: scroller.scrollTop, scrollHeight: scroller.scrollHeight, clientHeight: scroller.clientHeight, cloned: !!scroller.dataset.__autoScrollCloned, prependedHeight: scroller.dataset.__autoScrollPrependedHeight } : null, rafId: !!rafId, watchdog: !!watchdogInterval }; };
    window.__autoScroll.debug = function(){ return { lastActivity, idleDelay, scrollSpeed, isScrolling, pref: prefEnabled(), loopMode, endReached, endReachedAt, autoRestart, autoRestartDelayMs, scrollerInfo: scroller ? { id: scroller.id, scrollTop: scroller.scrollTop, scrollHeight: scroller.scrollHeight, clientHeight: scroller.clientHeight, cloned: !!scroller.dataset.__autoScrollCloned, prependedHeight: scroller.dataset.__autoScrollPrependedHeight } : null, rafId, lastFrameTime, watchdogInterval }; };

    log('auto-scroll (conservative v36.3) initialized');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

})();

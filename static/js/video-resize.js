/**
 * video-resize.js
 * Adds drag-to-resize handles so the user can resize the video player,
 * the program-info (summary) panel, and the channel column. Sizes are
 * persisted in localStorage and restored on page load.
 */
(function () {
  'use strict';

  var MIN_VIDEO_WIDTH  = 200;
  var MIN_VIDEO_HEIGHT = 120;
  var MIN_CHAN_COL_W   = 80;

  var LS_VIDEO_W  = 'retroiptv_video_w';
  var LS_VIDEO_H  = 'retroiptv_video_h';
  var LS_CHAN_W   = 'retroiptv_chan_w';

  /* ── Recompute fixed timebar + now-line after a layout change ── */
  function reflow() {
    requestAnimationFrame(function () {
      if (typeof createOrUpdateFixedTimeBar === 'function') createOrUpdateFixedTimeBar();
      if (typeof updateNowLine === 'function') updateNowLine();
    });
  }

  /* ── Keep guide-outer height equal to remaining viewport space ── */
  function updateGuideHeight() {
    var guideOuter = document.getElementById('guideOuter');
    var playerRow  = document.getElementById('playerRow');
    var handle     = document.getElementById('playerResizeHandle');
    var header     = document.querySelector('.header');
    if (!guideOuter) return;

    var headerH = header ? header.getBoundingClientRect().height : 40;
    var playerH = playerRow ? playerRow.getBoundingClientRect().height : 0;
    var handleH = handle  ? handle.getBoundingClientRect().height  : 6;
    var guideH  = window.innerHeight - headerH - playerH - handleH;
    guideOuter.style.height = Math.max(100, Math.round(guideH)) + 'px';
  }

  /* ── Generic drag-handle helper (mouse + touch) ───────────────── */
  function makeDraggable(el, callbacks) {
    /* callbacks: { onStart(x,y) -> ctx, onMove(ctx,x,y), onEnd(ctx) } */
    el.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      var ctx = callbacks.onStart(e.clientX, e.clientY);
      if (!ctx) return;
      el.classList.add('dragging');

      function onMove(e) { callbacks.onMove(ctx, e.clientX, e.clientY); }
      function onUp() {
        el.classList.remove('dragging');
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        if (callbacks.onEnd) callbacks.onEnd(ctx);
      }
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });

    el.addEventListener('touchstart', function (e) {
      e.preventDefault();
      var t = e.touches[0];
      var ctx = callbacks.onStart(t.clientX, t.clientY);
      if (!ctx) return;
      el.classList.add('dragging');

      var rafPending = false;
      var lastX = t.clientX, lastY = t.clientY;
      function onMove(e) {
        var t = e.touches[0];
        lastX = t.clientX; lastY = t.clientY;
        if (!rafPending) {
          rafPending = true;
          requestAnimationFrame(function () {
            rafPending = false;
            callbacks.onMove(ctx, lastX, lastY);
          });
        }
      }
      function onEnd() {
        el.classList.remove('dragging');
        el.removeEventListener('touchmove', onMove);
        el.removeEventListener('touchend', onEnd);
        el.removeEventListener('touchcancel', onEnd);
        if (callbacks.onEnd) callbacks.onEnd(ctx);
      }
      el.addEventListener('touchmove', onMove, { passive: false });
      el.addEventListener('touchend', onEnd);
      el.addEventListener('touchcancel', onEnd);
    }, { passive: false });
  }

  /* ── 1. Vertical resize – player row height → guide height ─────── */
  function initVerticalResize() {
    var playerRow  = document.getElementById('playerRow');
    var guideOuter = document.getElementById('guideOuter');
    var video      = document.getElementById('video');
    if (!playerRow || !guideOuter) return;

    var handle = document.createElement('div');
    handle.id        = 'playerResizeHandle';
    handle.className = 'player-resize-handle';
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-orientation', 'horizontal');
    handle.setAttribute('title', 'Drag to resize player height');
    handle.tabIndex  = 0;
    playerRow.after(handle);

    makeDraggable(handle, {
      onStart: function (x, y) {
        return { startY: y, startH: video ? video.getBoundingClientRect().height : 350 };
      },
      onMove: function (ctx, x, y) {
        var newH = Math.max(MIN_VIDEO_HEIGHT, ctx.startH + (y - ctx.startY));
        if (video) {
          video.style.height   = newH + 'px';
          video.style.removeProperty('max-height'); /* clear any mobile-adapt constraint */
        }
        updateGuideHeight();
        reflow();
      },
      onEnd: function () {
        if (video) {
          try { localStorage.setItem(LS_VIDEO_H, video.style.height); } catch (e) {}
        }
        updateGuideHeight();
        reflow();
      }
    });
  }

  /* ── 2. Horizontal resize – video width ↔ summary width ────────── */
  function initHorizontalResize() {
    var video   = document.getElementById('video');
    var summary = document.getElementById('summary');
    if (!video || !summary) return;

    var handle = document.createElement('div');
    handle.id        = 'videoResizeHandle';
    handle.className = 'video-resize-handle';
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-orientation', 'vertical');
    handle.setAttribute('title', 'Drag to resize video width');
    handle.tabIndex  = 0;
    /* Insert between summary and video */
    video.parentNode.insertBefore(handle, video);

    makeDraggable(handle, {
      onStart: function (x, y) {
        return { startX: x, startW: video.getBoundingClientRect().width };
      },
      onMove: function (ctx, x, y) {
        var newW = Math.max(MIN_VIDEO_WIDTH, ctx.startW + (x - ctx.startX));
        video.style.width = newW + 'px';
      },
      onEnd: function () {
        try { localStorage.setItem(LS_VIDEO_W, video.style.width); } catch (e) {}
      }
    });
  }

  /* ── 3. Channel-column width resize ────────────────────────────── */
  function initChanColResize() {
    /* Attach the handle to the header chan-col (first row) */
    var headerChanCol = document.querySelector('#gridTimeRow .chan-col');
    if (!headerChanCol) return;

    var handle = document.createElement('div');
    handle.className = 'chan-col-resize-handle';
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-orientation', 'vertical');
    handle.setAttribute('title', 'Drag to resize channel column');
    handle.tabIndex  = 0;
    headerChanCol.appendChild(handle);

    makeDraggable(handle, {
      onStart: function (x, y) {
        return { startX: x, startW: headerChanCol.getBoundingClientRect().width };
      },
      onMove: function (ctx, x, y) {
        var newW = Math.max(MIN_CHAN_COL_W, ctx.startW + (x - ctx.startX));
        document.documentElement.style.setProperty('--chan-col-width', newW + 'px');
        reflow();
      },
      onEnd: function () {
        try { localStorage.setItem(LS_CHAN_W, document.documentElement.style.getPropertyValue('--chan-col-width')); } catch (e) {}
        reflow();
      }
    });
  }

  /* ── Restore previously saved sizes ───────────────────────────── */
  function restoreSizes() {
    var video = document.getElementById('video');
    try {
      var w = localStorage.getItem(LS_VIDEO_W);
      var h = localStorage.getItem(LS_VIDEO_H);
      var c = localStorage.getItem(LS_CHAN_W);
      if (video) {
        if (w) video.style.width  = w;
        if (h) { video.style.height = h; video.style.removeProperty('max-height'); }
      }
      if (c) document.documentElement.style.setProperty('--chan-col-width', c);
    } catch (e) {}
    updateGuideHeight();
    reflow();
  }

  /* ── Bootstrap ─────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initVerticalResize();
    initHorizontalResize();
    initChanColResize();
    restoreSizes();

    /* Re-sync guide height on viewport resize */
    window.addEventListener('resize', updateGuideHeight);
  });
})();

/**
 * video-resize.js
 * Adds a bottom-left corner drag handle to the video player so the user can
 * resize it in both dimensions simultaneously (width and height).
 * Also adds a channel-column width resize handle.
 * Sizes are persisted in localStorage and restored on page load.
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
    if (!guideOuter) return;

    // Read the zoom factor via the shared global helper exposed by display-size.js.
    var zoom = (typeof window.getDisplayZoom === 'function')
      ? window.getDisplayZoom()
      : 1.0;

    if (zoom < 1) {
      // BELT: set body height so the overflow:hidden clip on body.guide-page is at
      // the correct viewport bottom. Chrome resolves body{height:100%} against the raw
      // viewport instead of html.style.height under CSS zoom. display-size.js also sets
      // body.style.height, and guide.html injects a CSS rule before first paint — this
      // call is belt-and-suspenders to ensure the correct height is always active after
      // any resize or display-size change event.
      document.body.style.height = Math.ceil(window.innerHeight / zoom) + 'px';

      // SUSPENDERS: explicitly set guideOuter height so it fills to the viewport even
      // if body.style.height doesn't take effect in an edge case.
      // getBoundingClientRect() always returns visual (viewport) px, unaffected by zoom.
      // Dividing by zoom converts visual px → CSS px in the zoom coordinate space.
      var header    = document.querySelector('.header');
      var playerRow = document.getElementById('playerRow');
      var headerH   = header    ? header.getBoundingClientRect().height    : 40;
      var playerH   = playerRow ? playerRow.getBoundingClientRect().height : 0;
      var heightCSS = Math.max(80, Math.floor((window.innerHeight - headerH - playerH) / zoom));
      guideOuter.style.height    = heightCSS + 'px';
      // flex:none (flex-grow:0 flex-shrink:0 flex-basis:auto) lets the explicit
      // height take effect; the default flex:1 uses flex-basis:0 which overrides it.
      guideOuter.style.flex      = 'none';
    } else {
      // Large / 100% — restore defaults and let flex:1 + body{height:100%} handle it.
      document.body.style.height = '';
      guideOuter.style.height    = '';
      guideOuter.style.flex      = '';
    }
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

  /* ── 1. Bottom-left corner resize – aspect-ratio-locked ────────── */
  function initCornerResize() {
    var video   = document.getElementById('video');
    if (!video) return;

    /* Wrap the video in a relative-positioned container to host the handle */
    var wrapper = document.createElement('div');
    wrapper.className = 'video-wrapper';
    video.parentNode.insertBefore(wrapper, video);
    wrapper.appendChild(video);

    /* Corner handle – sits outside the video so native controls don't block it */
    var handle = document.createElement('div');
    handle.id        = 'videoCornerHandle';
    handle.className = 'video-corner-handle';
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-label', 'Drag to resize video');
    handle.setAttribute('title', 'Drag to resize video player');
    handle.tabIndex  = 0;
    wrapper.appendChild(handle);

    makeDraggable(handle, {
      onStart: function (x, y) {
        var rect = video.getBoundingClientRect();
        return {
          startX: x,
          startY: y,
          startW: rect.width,
          startH: rect.height,
          /* diagonal length of the video at drag start */
          startDiag: Math.sqrt(rect.width * rect.width + rect.height * rect.height)
        };
      },
      onMove: function (ctx, x, y) {
        var deltaX = x - ctx.startX;
        var deltaY = y - ctx.startY;
        /*
         * Aspect-ratio-locked resize from the bottom-left corner:
         *   – Right edge and top edge are fixed (anchored).
         *   – Drag SW (left+down)  → bigger.
         *   – Drag NE (right+up)   → smaller.
         *
         * We project the drag vector onto the SW-NE diagonal direction
         * (-1, +1)/√2 and use the scalar change to scale both dimensions
         * by the same factor, preserving the original aspect ratio.
         */
        var proj    = (-deltaX + deltaY) / Math.SQRT2;
        var minDiag = Math.sqrt(
          MIN_VIDEO_WIDTH  * MIN_VIDEO_WIDTH +
          MIN_VIDEO_HEIGHT * MIN_VIDEO_HEIGHT
        );
        var newDiag = Math.max(minDiag, ctx.startDiag + proj);
        var scale   = newDiag / ctx.startDiag;
        var newW    = Math.round(ctx.startW * scale);
        var newH    = Math.round(ctx.startH * scale);
        video.style.width  = newW + 'px';
        video.style.height = newH + 'px';
        video.style.removeProperty('max-height');
        updateGuideHeight();
        reflow();
      },
      onEnd: function () {
        try {
          localStorage.setItem(LS_VIDEO_W, video.style.width);
          localStorage.setItem(LS_VIDEO_H, video.style.height);
        } catch (e) {}
        updateGuideHeight();
        reflow();
      }
    });
  }

  /* ── 2. Channel-column width resize ────────────────────────────── */
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
    initCornerResize();
    initChanColResize();
    restoreSizes();

    /* Re-sync guide height on viewport resize */
    window.addEventListener('resize', updateGuideHeight);
  });

  /* Expose globally so grid-adapt.js and other modules can call the canonical
     zoom-aware guide height computation rather than clearing the style. */
  window.updateGuideHeight = updateGuideHeight;
})();

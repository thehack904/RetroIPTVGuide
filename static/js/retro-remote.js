(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function dispatchRemoteKey(key, keyCode) {
    var opts = {
      key: key,
      bubbles: true,
      cancelable: true
    };

    if (Number.isFinite(keyCode)) {
      opts.keyCode = keyCode;
      opts.which = keyCode;
    }

    var event;
    try {
      event = new KeyboardEvent('keydown', opts);
      if (Number.isFinite(keyCode) && event.keyCode !== keyCode) {
        Object.defineProperty(event, 'keyCode', { get: function () { return keyCode; } });
        Object.defineProperty(event, 'which', { get: function () { return keyCode; } });
      }
    } catch (e) {
      event = document.createEvent('Event');
      event.initEvent('keydown', true, true);
      event.key = key;
      event.keyCode = keyCode;
      event.which = keyCode;
    }

    event.__retroRemote = true;
    document.dispatchEvent(event);
  }

  ready(function () {
    var toggles = Array.from(document.querySelectorAll('#retroRemoteToggle, #mobileRetroRemoteToggle'));
    var activeToggle = toggles[0] || null;
    var overlay = document.getElementById('retroRemoteOverlay');
    var closeBtn = document.getElementById('retroRemoteClose');
    var playerRow = document.getElementById('playerRow');
    var videoWrap = document.getElementById('videoPlayerWrap');

    if (!toggles.length || !overlay || !playerRow || !videoWrap) return;

    function setOpen(open) {
      overlay.classList.toggle('is-open', open);
      toggles.forEach(function (toggle) {
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        toggle.setAttribute('aria-label', open ? 'Close remote' : 'Open remote');
      });
      if (open) positionOverlay();
    }

    function isOpen() {
      return overlay.classList.contains('is-open');
    }

    function positionOverlay() {
      var rowRect = playerRow.getBoundingClientRect();
      var videoRect = videoWrap.getBoundingClientRect();
      var overlayWidth = overlay.offsetWidth || 260;
      var gap = 12;
      var left = Math.round(videoRect.left - rowRect.left - overlayWidth - gap);

      if (window.innerWidth <= 900) {
        left = Math.round((rowRect.width - overlayWidth) / 2);
      }
      if (left < 8) left = 8;
      overlay.style.left = left + 'px';
      overlay.style.top = '8px';
    }

    function getChannels() {
      return Array.from(document.querySelectorAll('.guide-row[data-cid] .chan-name')).filter(function (el) {
        var row = el.closest('.guide-row');
        if (el.closest('.__auto_scroll_clone')) return false;
        return !row || getComputedStyle(row).display !== 'none';
      });
    }

    function playChannelElement(el) {
      if (!el) return;
      el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
      el.focus();
      if (typeof window.playChannel === 'function') {
        window.playChannel(el.dataset.url, el.dataset.cid, el.dataset.name);
      } else {
        el.click();
      }
    }

    function stepChannel(delta) {
      var channels = getChannels();
      if (!channels.length) return;

      var currentId = window.currentChannelMeta && window.currentChannelMeta.id;
      var index = currentId ? channels.findIndex(function (el) {
        return el.dataset.cid === currentId;
      }) : -1;

      if (index === -1) {
        index = channels.indexOf(document.activeElement);
      }
      if (index === -1) index = delta > 0 ? -1 : 0;

      var nextIndex = (index + delta + channels.length) % channels.length;
      playChannelElement(channels[nextIndex]);
    }

    function toggleFullscreen() {
      var vcFsBtn = document.getElementById('vcFsBtn');
      if (vcFsBtn && !vcFsBtn.hidden) {
        vcFsBtn.click();
        return;
      }

      var fullscreenEl = document.fullscreenElement || document.webkitFullscreenElement || null;
      if (fullscreenEl) {
        var exit = document.exitFullscreen || document.webkitExitFullscreen;
        if (exit) exit.call(document);
        return;
      }

      var video = document.getElementById('video');
      var target = video || videoWrap;
      var request = target.requestFullscreen || target.webkitRequestFullscreen || target.mozRequestFullscreen;
      if (request) {
        var result = request.call(target);
        if (result && result.catch) result.catch(function () {});
      }
    }

    toggles.forEach(function (toggle) {
      toggle.addEventListener('click', function (event) {
        event.preventDefault();
        activeToggle = toggle;
        setOpen(!isOpen());
      });
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        setOpen(false);
        if (activeToggle) activeToggle.focus();
      });
    }

    overlay.addEventListener('click', function (event) {
      var actionBtn = event.target.closest('[data-remote-action]');
      if (actionBtn) {
        if (actionBtn.dataset.remoteAction === 'channel-up') stepChannel(1);
        if (actionBtn.dataset.remoteAction === 'channel-down') stepChannel(-1);
        if (actionBtn.dataset.remoteAction === 'fullscreen') toggleFullscreen();
        return;
      }

      var keyBtn = event.target.closest('[data-key]');
      if (!keyBtn) return;
      var key = keyBtn.dataset.key || '';
      var code = parseInt(keyBtn.dataset.keyCode, 10);
      dispatchRemoteKey(key, Number.isFinite(code) ? code : undefined);
    });

    document.addEventListener('click', function (event) {
      if (!isOpen()) return;
      var clickedToggle = toggles.some(function (toggle) {
        return toggle.contains(event.target);
      });
      if (overlay.contains(event.target) || clickedToggle) return;
      setOpen(false);
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && isOpen() && !event.__retroRemote) setOpen(false);
    });

    window.addEventListener('resize', function () {
      if (isOpen()) positionOverlay();
    });

    window.addEventListener('orientationchange', function () {
      if (isOpen()) setTimeout(positionOverlay, 80);
    });
  });
})();

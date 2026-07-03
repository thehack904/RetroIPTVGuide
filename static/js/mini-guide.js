(function () {
  'use strict';

  var MINI_GUIDE_ROW_COUNT = 7;
  var MINI_GUIDE_AUTODISMISS_MS = 8000;
  var MINI_GUIDE_TOGGLE_KEY = 'g';

  var isOpen = false;
  var selectedIndex = 0;
  var channels = [];
  var dismissTimer = null;
  var progressTimer = null;
  var isHovering = false;
  var guideLayout = ((window.__initialUserPrefs || {}).guide_layout === 'mini') ? 'mini' : 'full';
  var pageRenderQueued = false;

  function escapeCid(cid) {
    if (typeof CSS !== 'undefined' && CSS.escape) return CSS.escape(cid);
    return String(cid || '').replace(/[^a-zA-Z0-9._-]/g, '\\$&');
  }

  function fmtTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function fmtRemaining(ms) {
    var minutes = Math.max(0, Math.round(ms / 60000));
    if (minutes < 1) return '< 1 min';
    if (minutes === 1) return '1 min';
    return minutes + ' min';
  }

  function currentChannelId() {
    if (window.currentChannelMeta && window.currentChannelMeta.id) {
      return window.currentChannelMeta.id;
    }
    return window._cibLastCid || null;
  }

  function currentProgramFor(row) {
    var now = new Date();
    var current = null;
    row.querySelectorAll('.program').forEach(function (program) {
      if (!program.dataset.start || !program.dataset.stop) return;
      var start = new Date(program.dataset.start);
      var stop = new Date(program.dataset.stop);
      if (start <= now && stop >= now) {
        current = {
          title: program.dataset.title || program.textContent.trim(),
          start: start,
          stop: stop,
          progressPct: Math.min(100, Math.max(0, ((now - start) / (stop - start)) * 100)),
          remaining: fmtRemaining(stop - now)
        };
      }
    });
    return current;
  }

  function isRowVisibleInGuide(row) {
    if (row.classList.contains('chan-search-hidden')) return false;
    if (row.classList.contains('chan-hidden') && !row.classList.contains('chan-hidden-visible')) return false;
    if (document.body.classList.contains('favorites-only') && !row.classList.contains('chan-favorite')) return false;
    return true;
  }

  function collectChannels(options) {
    options = options || {};
    channels = Array.prototype.slice.call(document.querySelectorAll('.guide-row[data-cid]')).filter(function (row) {
      return !options.visibleOnly || isRowVisibleInGuide(row);
    }).map(function (row, index) {
      var chan = row.querySelector('.chan-name');
      var program = currentProgramFor(row);
      var name = chan ? (chan.dataset.name || chan.textContent.trim()) : '';
      return {
        index: index,
        cid: row.dataset.cid || (chan ? chan.dataset.cid : ''),
        url: chan ? (chan.dataset.url || '') : '',
        name: name,
        logo: chan ? (chan.dataset.logo || '') : '',
        chanNum: chan ? (chan.dataset.chanNum || String(index + 1)) : String(index + 1),
        programTitle: program ? program.title : 'No Guide Data Available',
        timeRange: program ? (fmtTime(program.start) + ' - ' + fmtTime(program.stop)) : '',
        remaining: program ? (program.remaining + ' left') : '',
        progressPct: program ? program.progressPct : 0
      };
    });
  }

  function selectedWindow() {
    var count = Math.min(MINI_GUIDE_ROW_COUNT, channels.length);
    var start = Math.max(0, selectedIndex - Math.floor(count / 2));
    start = Math.min(start, Math.max(0, channels.length - count));
    return channels.slice(start, start + count);
  }

  function setSelectedByCurrent() {
    var cid = currentChannelId();
    var found = channels.findIndex(function (channel) { return channel.cid === cid; });
    selectedIndex = found >= 0 ? found : 0;
  }

  function clearChildren(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function buildRow(channel, options) {
    options = options || {};
    var row = document.createElement('button');
    row.type = 'button';
    row.className = 'mini-guide-row';
    row.id = (options.idPrefix || 'mg-row-') + channel.index;
    row.setAttribute('role', 'option');
    row.setAttribute('aria-selected', (!options.disableSelection && channel.index === selectedIndex) ? 'true' : 'false');
    row.dataset.index = String(channel.index);
    row.dataset.url = channel.url;
    row.dataset.cid = channel.cid;
    row.dataset.name = channel.name;

    if (!options.disableSelection && channel.index === selectedIndex) row.classList.add('is-selected');
    if (channel.cid === currentChannelId()) row.classList.add('is-current');

    var num = document.createElement('div');
    num.className = 'mg-channel-num';
    num.textContent = channel.chanNum ? 'CH ' + channel.chanNum : '';

    var logoWrap;
    if (channel.logo) {
      logoWrap = document.createElement('img');
      logoWrap.className = 'mg-logo';
      logoWrap.src = channel.logo;
      logoWrap.alt = '';
      logoWrap.onerror = function () {
        var fallback = document.createElement('div');
        fallback.className = 'mg-logo-placeholder';
        this.replaceWith(fallback);
      };
    } else {
      logoWrap = document.createElement('div');
      logoWrap.className = 'mg-logo-placeholder';
    }

    var main = document.createElement('div');
    main.className = 'mg-main';

    var top = document.createElement('div');
    top.className = 'mg-topline';

    var name = document.createElement('div');
    name.className = 'mg-channel-name';
    name.textContent = channel.name;

    var title = document.createElement('div');
    title.className = 'mg-program-title';
    title.textContent = channel.programTitle;

    top.appendChild(name);
    top.appendChild(title);

    var meta = document.createElement('div');
    meta.className = 'mg-meta';

    var time = document.createElement('span');
    time.className = 'mg-time';
    time.textContent = channel.timeRange;

    var progress = document.createElement('div');
    progress.className = 'mg-progress-wrap';
    var bar = document.createElement('div');
    bar.className = 'mg-progress-bar';
    bar.style.width = channel.progressPct + '%';
    progress.appendChild(bar);

    var remaining = document.createElement('span');
    remaining.className = 'mg-remaining';
    remaining.textContent = channel.remaining;

    meta.appendChild(time);
    meta.appendChild(progress);
    meta.appendChild(remaining);
    main.appendChild(top);
    main.appendChild(meta);

    row.appendChild(num);
    row.appendChild(logoWrap);
    row.appendChild(main);
    row.addEventListener('click', function () {
      selectedIndex = channel.index;
      tuneSelected();
    });
    row.addEventListener('mouseenter', function () {
      if (options.disableSelection) return;
      selectedIndex = channel.index;
      render();
    });

    return row;
  }

  function render() {
    var list = document.getElementById('mgChannelList');
    if (!list) return;
    collectChannels();
    if (!channels.length) {
      clearChildren(list);
      return;
    }
    if (selectedIndex < 0 || selectedIndex >= channels.length) setSelectedByCurrent();

    clearChildren(list);
    selectedWindow().forEach(function (channel) {
      list.appendChild(buildRow(channel));
    });
    list.setAttribute('aria-activedescendant', 'mg-row-' + selectedIndex);
  }

  function renderPageMiniGuide() {
    var list = document.getElementById('miniGuidePageList');
    var count = document.getElementById('miniGuidePageCount');
    if (!list) return;

    collectChannels({ visibleOnly: true });
    clearChildren(list);
    if (count) count.textContent = channels.length + (channels.length === 1 ? ' channel' : ' channels');

    if (!channels.length) {
      var empty = document.createElement('div');
      empty.className = 'mini-guide-empty';
      empty.textContent = 'No channels match the current filters.';
      list.appendChild(empty);
      return;
    }

    channels.forEach(function (channel) {
      list.appendChild(buildRow(channel, { idPrefix: 'mg-page-row-', disableSelection: true }));
    });
  }

  function schedulePageRender() {
    if (guideLayout !== 'mini' || pageRenderQueued) return;
    pageRenderQueued = true;
    requestAnimationFrame(function () {
      pageRenderQueued = false;
      renderPageMiniGuide();
    });
  }

  function syncLayoutButtons() {
    var mini = guideLayout === 'mini';
    var label = mini ? '▦ Regular Guide Layout' : '▤ Mini Guide Layout';
    ['toggleGuideLayout', 'mobileToggleGuideLayout'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.textContent = label;
      el.setAttribute('aria-pressed', mini ? 'true' : 'false');
    });
  }

  function persistGuideLayout() {
    var patch = { guide_layout: guideLayout };
    if (window.__userPrefs && typeof window.__userPrefs.save === 'function') {
      window.__userPrefs.save(patch);
      return;
    }
    fetch('/api/user_prefs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(patch)
    }).catch(function () {});
  }

  function applyGuideLayout(layout, persist) {
    guideLayout = layout === 'mini' ? 'mini' : 'full';
    var miniPage = document.getElementById('miniGuidePage');
    document.body.classList.toggle('guide-layout-mini', guideLayout === 'mini');
    if (miniPage) miniPage.hidden = guideLayout !== 'mini';
    syncLayoutButtons();

    if (guideLayout === 'mini') {
      renderPageMiniGuide();
    } else {
      requestAnimationFrame(function () {
        if (typeof window.createOrUpdateFixedTimeBar === 'function') window.createOrUpdateFixedTimeBar();
        if (typeof window.updateNowLine === 'function') window.updateNowLine();
        window.dispatchEvent(new Event('resize'));
      });
    }

    document.dispatchEvent(new CustomEvent('guide-layout:changed', { detail: { layout: guideLayout } }));

    if (persist) persistGuideLayout();
  }

  function toggleGuideLayout() {
    applyGuideLayout(guideLayout === 'mini' ? 'full' : 'mini', true);
  }

  function scheduleDismiss() {
    cancelDismiss();
    if (!isOpen || isHovering) return;
    dismissTimer = setTimeout(closeMiniGuide, MINI_GUIDE_AUTODISMISS_MS);
  }

  function cancelDismiss() {
    if (dismissTimer) {
      clearTimeout(dismissTimer);
      dismissTimer = null;
    }
  }

  function resetIdleTimer() {
    scheduleDismiss();
  }

  function openMiniGuide() {
    var panel = document.getElementById('miniGuide');
    if (!panel) return;
    collectChannels();
    setSelectedByCurrent();
    isOpen = true;
    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');
    render();
    scheduleDismiss();
    if (progressTimer) clearInterval(progressTimer);
    progressTimer = setInterval(function () {
      if (!isOpen) return;
      render();
    }, 15000);
  }

  function closeMiniGuide() {
    var panel = document.getElementById('miniGuide');
    if (!panel) return;
    isOpen = false;
    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');
    cancelDismiss();
    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }
  }

  function toggleMiniGuide() {
    if (isOpen) closeMiniGuide();
    else openMiniGuide();
  }

  function moveSelection(delta) {
    if (!channels.length) collectChannels();
    if (!channels.length) return;
    selectedIndex = Math.min(channels.length - 1, Math.max(0, selectedIndex + delta));
    render();
    resetIdleTimer();
  }

  function tuneSelected() {
    var channel = channels[selectedIndex];
    if (!channel || !channel.url || typeof window.playChannel !== 'function') return;
    window.playChannel(channel.url, channel.cid, channel.name);
    closeMiniGuide();
  }

  function shouldIgnoreShortcut(event) {
    var tag = (document.activeElement || {}).tagName || '';
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'BUTTON' || event.ctrlKey || event.metaKey || event.altKey;
  }

  function wire() {
    var button = document.getElementById('miniGuideBtn');
    var closeButton = document.getElementById('miniGuideClose');
    var panel = document.getElementById('miniGuide');

    if (button) {
      button.addEventListener('click', function (event) {
        event.stopPropagation();
        toggleMiniGuide();
      });
    }
    if (closeButton) {
      closeButton.addEventListener('click', function () {
        closeMiniGuide();
      });
    }
    if (panel) {
      panel.addEventListener('mouseenter', function () {
        isHovering = true;
        cancelDismiss();
      });
      panel.addEventListener('mouseleave', function () {
        isHovering = false;
        scheduleDismiss();
      });
      panel.addEventListener('mousemove', resetIdleTimer);
    }

    ['toggleGuideLayout', 'mobileToggleGuideLayout'].forEach(function (id) {
      var layoutToggle = document.getElementById(id);
      if (!layoutToggle) return;
      layoutToggle.addEventListener('click', function (event) {
        event.preventDefault();
        toggleGuideLayout();
      });
    });

    var guideOuter = document.getElementById('guideOuter');
    if (guideOuter && typeof MutationObserver === 'function') {
      var observer = new MutationObserver(schedulePageRender);
      observer.observe(guideOuter, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
      });
    }
    ['guideSearchInput', 'guideTypeFilter'].forEach(function (id) {
      var input = document.getElementById(id);
      if (input) input.addEventListener('input', schedulePageRender);
      if (input) input.addEventListener('change', schedulePageRender);
    });

    document.addEventListener('keydown', function (event) {
      if (shouldIgnoreShortcut(event)) return;
      if (event.key && event.key.toLowerCase() === MINI_GUIDE_TOGGLE_KEY) {
        event.preventDefault();
        toggleMiniGuide();
        return;
      }
      if (!isOpen) return;
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        moveSelection(-1);
      } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        moveSelection(1);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        tuneSelected();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        closeMiniGuide();
      }
    });

    applyGuideLayout(guideLayout, false);
  }

  window.openMiniGuide = openMiniGuide;
  window.closeMiniGuide = closeMiniGuide;
  window.toggleMiniGuide = toggleMiniGuide;
  window.setGuideLayout = function (layout, persist) { applyGuideLayout(layout, persist !== false); };
  window.toggleGuideLayout = toggleGuideLayout;
  window.renderMiniGuidePage = renderPageMiniGuide;

  document.addEventListener('DOMContentLoaded', wire);
})();

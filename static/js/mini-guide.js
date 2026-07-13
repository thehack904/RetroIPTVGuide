(function () {
  'use strict';

  var channels = [];
  var guideLayout = ((window.__initialUserPrefs || {}).guide_layout === 'mini') ? 'mini' : 'full';
  var pageRenderQueued = false;

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
    row.setAttribute('aria-selected', 'false');
    row.dataset.index = String(channel.index);
    row.dataset.url = channel.url;
    row.dataset.cid = channel.cid;
    row.dataset.name = channel.name;

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
      if (channel.url && typeof window.playChannel === 'function') {
        window.playChannel(channel.url, channel.cid, channel.name);
      }
    });

    return row;
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
      list.appendChild(buildRow(channel, { idPrefix: 'mg-page-row-' }));
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

  function wire() {
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

    applyGuideLayout(guideLayout, false);
  }

  window.setGuideLayout = function (layout, persist) { applyGuideLayout(layout, persist !== false); };
  window.toggleGuideLayout = toggleGuideLayout;
  window.renderMiniGuidePage = renderPageMiniGuide;

  document.addEventListener('DOMContentLoaded', wire);
})();

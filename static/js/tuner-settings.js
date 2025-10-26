// Tuner Settings + autoplay-from-playlist
// - Loads a playlist (.m3u), parses channels
// - Merges with EPG channels found on page
// - Renders a small settings UI (select + autoplay checkbox)
// - Persists active tuner + autoplay preference in localStorage
// - Autoplays selected tuner on guide load when autoplay enabled
//
// Usage:
// - Include this file in your page (defer).
// - Optionally call window.__tuner.init({ playlistUrl: '/your.m3u', containerSelector: '#settings-container' });
// - Or add <div id="tuner-settings"></div> to your settings markup and the module will auto-mount there.

(function () {
  const LS_KEY = 'activeTuner'; // stores { id, title, url }
  const LS_AUTOPLAY = 'autoplayTuner'; // 'true'|'false'
  const DEFAULT_PLAYLIST_URLS = ['/playlist.m3u', '/static/playlist.m3u', '/channels.m3u'];

  // public API object
  window.__tuner = window.__tuner || {};

  function log(...args) { if (window && window.console) console.debug.apply(console, ['[tuner]'].concat(args)); }

  // parse simple M3U with #EXTINF lines. Works with tvg-id="..." attributes or just " ,Name" style.
  function parseM3U(text) {
    const lines = text.split(/\r?\n/);
    const out = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      if (line.startsWith('#EXTINF')) {
        const info = line;
        // try to extract tvg-id or tvg-name
        const idMatch = info.match(/tvg-id="([^"]+)"/i);
        const nameMatch = info.match(/,(.*)$/);
        const tvgNameMatch = info.match(/tvg-name="([^"]+)"/i);
        const name = (nameMatch && nameMatch[1]) ? nameMatch[1].trim() : (tvgNameMatch ? tvgNameMatch[1] : null);
        const id = idMatch ? idMatch[1] : (tvgNameMatch ? tvgNameMatch[1] : (name || null));
        // next non-empty non-comment line is the URL
        let j = i + 1;
        let url = null;
        while (j < lines.length) {
          const candidate = lines[j].trim();
          if (!candidate) { j++; continue; }
          if (candidate.startsWith('#')) { j++; continue; }
          url = candidate;
          break;
        }
        if (url) {
          out.push({ id: id || url, name: name || id || url, url: url, raw: info });
        }
      }
    }
    return out;
  }

  async function fetchPlaylist(playlistUrlCandidates) {
    const candidates = Array.isArray(playlistUrlCandidates) ? playlistUrlCandidates : (playlistUrlCandidates ? [playlistUrlCandidates] : DEFAULT_PLAYLIST_URLS);
    for (const u of candidates) {
      try {
        const res = await fetch(u + (u.includes('?') ? '&' : '?') + '_=' + Date.now(), { credentials: 'same-origin' });
        if (!res.ok) { log('playlist fetch failed', u, res.status); continue; }
        const txt = await res.text();
        const parsed = parseM3U(txt);
        if (parsed && parsed.length) {
          log('loaded playlist', u, parsed.length, 'entries');
          return parsed;
        }
      } catch (err) {
        log('playlist fetch error', u, err);
      }
    }
    log('no playlist loaded from candidates');
    return [];
  }

  // Attempt to get EPG channels from a known global or from DOM
  function getEpgChannels() {
    // If an app-provided structure exists, use it
    try {
      if (Array.isArray(window.__epgChannels)) {
        return window.__epgChannels.map(c => ({ id: String(c.id), title: c.title || c.name || String(c.id), epg: true }));
      }
    } catch (e) { /* ignore */ }

    // Fallback: scan DOM for channel rows. Works with .chan-col or other reasonable selectors.
    const nodes = Array.from(document.querySelectorAll('.chan-col, .channel-row, .channel, .grid-col .chan-col'));
    const out = nodes.map(n => {
      // try common places for channel id/number and name
      let id = null;
      if (n.dataset && n.dataset.chanId) id = n.dataset.chanId;
      if (!id) {
        const numEl = n.querySelector('.chan-number, .channel-number, .cnum');
        if (numEl) id = numEl.textContent.trim();
      }
      if (!id) {
        // fallback: use first 6 chars of text (not ideal but usable)
        id = (n.getAttribute('data-id') || n.id || '').toString() || null;
      }
      const titleEl = n.querySelector('.chan-name, .channel-name, .cname');
      const title = titleEl ? titleEl.textContent.trim() : (n.textContent || '').trim().slice(0, 40);
      return id ? { id: String(id), title: title || String(id), epg: true } : null;
    }).filter(Boolean);

    // dedupe by id
    const map = new Map();
    out.forEach(c => map.set(String(c.id), c));
    return Array.from(map.values());
  }

  // Merge playlist channels and EPG channels into an ordered list (EPG channels kept first)
  function mergeChannels(epg, playlist) {
    const map = new Map();
    // add EPG first
    (epg || []).forEach(e => map.set(String(e.id), { id: String(e.id), title: e.title || String(e.id), epg: true }));
    // add playlist channels, attach url, add new ones
    (playlist || []).forEach(p => {
      const key = String(p.id || p.url || p.name || p);
      if (map.has(key)) {
        map.get(key).url = p.url; // attach url to EPG entry if available
      } else {
        map.set(key, { id: key, title: p.name || p.id || p.url, url: p.url, playlist: true });
      }
    });
    // return array preserving EPG ordering first, then playlist-only entries
    return Array.from(map.values());
  }

  // Simple UI creation: inject into container or auto-create a panel inside body if not found.
  function renderSettingsUI(containerSelector, channels, persisted) {
    let container = null;
    if (containerSelector) container = document.querySelector(containerSelector);
    if (!container) container = document.getElementById('tuner-settings') || document.querySelector('#settings-pane') || null;
    // If still not found, create a small floating panel (non-intrusive)
    let created = false;
    if (!container) {
      container = document.createElement('div');
      container.id = 'tuner-settings';
      container.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:9999;background:#fff;border:1px solid #ddd;padding:8px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,0.2);font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial;';
      document.body.appendChild(container);
      created = true;
    }

    container.innerHTML = ''; // clear
    const title = document.createElement('div');
    title.style.fontWeight = '600';
    title.style.marginBottom = '6px';
    title.textContent = 'Active Tuner (Autoplay)';
    container.appendChild(title);

    const select = document.createElement('select');
    select.id = 'activeTunerSelect';
    select.style.minWidth = '260px';
    select.style.marginBottom = '6px';
    // Add default option
    const autoOpt = document.createElement('option');
    autoOpt.value = '';
    autoOpt.textContent = '— Use EPG default —';
    select.appendChild(autoOpt);

    channels.forEach(ch => {
      const opt = document.createElement('option');
      opt.value = JSON.stringify({ id: ch.id, url: ch.url || '', title: ch.title || ch.id });
      let label = ch.title || ch.id;
      if (ch.playlist) label += ' (playlist)';
      if (ch.epg && !ch.url) label += ' (EPG only)';
      opt.textContent = label;
      select.appendChild(opt);
    });

    // set persisted selection
    if (persisted && persisted.id) {
      const compare = JSON.stringify({ id: persisted.id, url: persisted.url || '', title: persisted.title || persisted.id });
      const opt = Array.from(select.options).find(o => o.value === compare);
      if (opt) select.value = compare;
    }

    container.appendChild(select);

    const autop = document.createElement('label');
    autop.style.display = 'flex';
    autop.style.alignItems = 'center';
    autop.style.gap = '8px';
    autop.style.marginBottom = '8px';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = 'autoplayTuner';
    cb.checked = (localStorage.getItem(LS_AUTOPLAY) !== 'false'); // default true
    autop.appendChild(cb);
    const span = document.createElement('span');
    span.textContent = 'Autoplay on guide load';
    autop.appendChild(span);
    container.appendChild(autop);

    const btnRow = document.createElement('div');
    btnRow.style.display = 'flex';
    btnRow.style.gap = '8px';

    const saveBtn = document.createElement('button');
    saveBtn.textContent = 'Save';
    saveBtn.style.padding = '6px 10px';
    saveBtn.addEventListener('click', () => {
      const val = select.value;
      if (!val) {
        localStorage.removeItem(LS_KEY);
      } else {
        try {
          localStorage.setItem(LS_KEY, val);
        } catch (e) { log('save error', e); }
      }
      localStorage.setItem(LS_AUTOPLAY, cb.checked ? 'true' : 'false');
      log('settings saved', { active: localStorage.getItem(LS_KEY), autoplay: localStorage.getItem(LS_AUTOPLAY) });
      // If autoplay enabled and a selection exists, play immediately
      if (cb.checked && val) {
        const parsed = JSON.parse(val);
        playChannel(parsed.url, parsed);
      }
    });

    const clearBtn = document.createElement('button');
    clearBtn.textContent = 'Clear';
    clearBtn.style.padding = '6px 10px';
    clearBtn.addEventListener('click', () => {
      select.value = '';
      cb.checked = false;
      localStorage.removeItem(LS_KEY);
      localStorage.setItem(LS_AUTOPLAY, 'false');
      log('settings cleared');
    });

    btnRow.appendChild(saveBtn);
    btnRow.appendChild(clearBtn);
    container.appendChild(btnRow);

    if (created) {
      const note = document.createElement('div');
      note.style.marginTop = '8px';
      note.style.fontSize = '12px';
      note.style.color = '#666';
      note.textContent = 'You can move this panel into your settings page and call window.__tuner.init({containerSelector:"#your-settings-slot"}).';
      container.appendChild(note);
    }
  }

  // Attempt to play url using common players or <video> element
  async function playChannel(url, meta) {
    if (!url) return log('playChannel: no url');
    log('playChannel requested', url, meta || '');
    try {
      // If there's an HLS player exposed (hls.js instance) on window.hlsPlayer or window.hls
      if (window.hls && typeof window.hls.loadSource === 'function') {
        try {
          window.hls.loadSource(url);
          const video = window.hls.media || document.querySelector('video');
          if (video) {
            await video.play().catch(e => log('video.play() rejected', e));
            log('played via window.hls');
            return true;
          }
        } catch (e) { log('hls play error', e); }
      }
      // If a site-level player API exists
      if (window.player && typeof window.player.play === 'function') {
        try {
          window.player.play(url);
          log('played via window.player.play');
          return true;
        } catch (e) { log('window.player.play error', e); }
      }
      // Try to find a video/audio element
      const vid = document.querySelector('video#player, video.player, video, audio');
      if (vid) {
        if (vid.tagName.toLowerCase() === 'video' || vid.tagName.toLowerCase() === 'audio') {
          // if HLS.js is needed, user should have Hls loaded; fall back to setting src
          if (vid.canPlayType && vid.canPlayType('application/vnd.apple.mpegurl')) {
            vid.src = url;
          } else {
            // If Hls.js present, attach
            if (window.Hls && Hls.isSupported && Hls.isSupported()) {
              try {
                if (window.__tuner._hlsInstance) { window.__tuner._hlsInstance.destroy(); delete window.__tuner._hlsInstance; }
                const hls = new Hls();
                hls.loadSource(url);
                hls.attachMedia(vid);
                window.__tuner._hlsInstance = hls;
              } catch (e) { log('hls attach error', e); vid.src = url; }
            } else {
              vid.src = url;
            }
          }
          // play
          await vid.play().catch(e => log('video.play() rejected', e));
          log('played via <video>');
          return true;
        }
      }
      // Last-ditch: open in new window (useful for testing)
      // window.open(url, '_blank');
      log('playChannel: no player found to play url');
      return false;
    } catch (err) {
      log('playChannel error', err);
      return false;
    }
  }

  // Public helpers
  window.__tuner.getActive = function () {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return null; }
  };
  window.__tuner.setActive = function (obj) {
    if (!obj) { localStorage.removeItem(LS_KEY); return; }
    localStorage.setItem(LS_KEY, JSON.stringify(obj));
  };
  window.__tuner.list = async function (playlistUrl) {
    const epg = getEpgChannels();
    const pl = await fetchPlaylist(playlistUrl);
    return mergeChannels(epg, pl);
  };
  window.__tuner.playActive = async function () {
    const active = window.__tuner.getActive();
    if (!active || !active.url) { log('no active tuner set'); return false; }
    return playChannel(active.url, active);
  };

  // init: fetch playlist, build union and render UI, then autoplay if requested
  window.__tuner.init = async function (opts) {
    opts = opts || {};
    const playlistUrl = opts.playlistUrl || null;
    const containerSelector = opts.containerSelector || null;
    // fetch playlist first (non-blocking if fails)
    const [playlist, epg] = await Promise.all([fetchPlaylist(playlistUrl), Promise.resolve(getEpgChannels())]);
    const merged = mergeChannels(epg, playlist);
    // ensure stable ordering: EPG first then playlist-only items
    renderSettingsUI(containerSelector, merged, window.__tuner.getActive());

    // autoplay on load?
    const autoplay = (localStorage.getItem(LS_AUTOPLAY) !== 'false');
    const active = window.__tuner.getActive();
    if (autoplay && active && active.url) {
      // defer slightly until page settles
      setTimeout(() => {
        window.__tuner.playActive().catch(e => log('autoplay failed', e));
      }, 500);
    }

    // expose debug
    window.__tuner.debug = function () {
      return { playlistLength: playlist.length, epgLength: epg.length, active: window.__tuner.getActive(), autoplay: (localStorage.getItem(LS_AUTOPLAY) !== 'false') };
    };

    log('tuner initialized', window.__tuner.debug());
    return merged;
  };

  // auto-init when DOM ready if a target placeholder exists
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      // auto-init only if there's a visible placeholder or settings pane
      if (document.getElementById('tuner-settings') || document.querySelector('#settings-pane')) {
        window.__tuner.init();
      }
    });
  } else {
    if (document.getElementById('tuner-settings') || document.querySelector('#settings-pane')) {
      window.__tuner.init();
    }
  }
})();

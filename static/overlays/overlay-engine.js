/* Virtual Channels Overlay Engine (v1)
 * - Manages overlay lifecycle
 * - Calls renderer modules by type
 * - Handles timed refresh
 *
 * Assumptions:
 * - A root exists: #virtual-overlay-root
 * - Renderer modules register themselves via OverlayEngine.register(type, renderer)
 */

(function () {
  const rootId = "virtual-overlay-root";

  const state = {
    timer: null,
    activeType: null,
    refreshSeconds: 60,
    renderers: {},
    lastData: null,
    appearance: { textColor: '', bgColor: '' },
  };

  function rootEl() {
    const el = document.getElementById(rootId);
    if (!el) throw new Error(`Missing #${rootId} overlay root`);
    return el;
  }

  function applyAppearance(el) {
    // Apply per-channel CSS custom properties to the overlay root
    const { textColor, bgColor } = state.appearance;
    el.style.setProperty('--vc-text-color', textColor || '');
    el.style.setProperty('--vc-bg-color', bgColor || '');
  }

  function clearRoot() {
    const el = rootEl();
    el.innerHTML = "";
    el.classList.remove("hidden");
    applyAppearance(el);
  }

  function hideRoot() {
    const el = rootEl();
    el.innerHTML = "";
    el.classList.add("hidden");
    el.style.removeProperty('--vc-text-color');
    el.style.removeProperty('--vc-bg-color');
  }

  function setError(msg) {
    const el = rootEl();
    // Keep any current overlay; add an error pill.
    let err = el.querySelector(".vc-error");
    if (!err) {
      err = document.createElement("div");
      err.className = "vc-error vc-pill";
      el.appendChild(err);
    }
    err.textContent = msg;
  }

  async function tick() {
    const r = state.renderers[state.activeType];
    if (!r) return;

    try {
      const data = await r.fetch();
      state.lastData = data;
      r.render(data, rootEl());
    } catch (e) {
      console.warn("[VirtualChannels] overlay tick failed:", e);
      setError("Overlay update failed");
      // If we have prior data, keep showing it.
    }
  }

  const OverlayEngine = {
    register(type, renderer) {
      state.renderers[type] = renderer;
    },

    start({ type, refreshSeconds, textColor = '', bgColor = '' }) {
      this.stop();
      state.activeType = type;
      state.refreshSeconds = Math.max(10, Number(refreshSeconds) || 60);
      state.appearance = { textColor, bgColor };

      const r = state.renderers[type];
      if (!r) {
        clearRoot();
        setError(`No renderer for overlay_type="${type}"`);
        return;
      }

      clearRoot();
      // First render immediately
      tick();

      // Schedule refresh aligned to wall clock so all viewers see the same
      // snapshot regardless of when they tuned in.  Wait until the next
      // interval boundary (e.g. :00, :02, :05 ...) then tick on a regular
      // setInterval from that point forward.
      (function scheduleAligned() {
        const intervalMs = state.refreshSeconds * 1000;
        const delay = intervalMs - (Date.now() % intervalMs);
        state._timerIsInterval = false;
        state.timer = window.setTimeout(function () {
          if (!state.activeType) return;
          tick();
          state._timerIsInterval = true;
          state.timer = window.setInterval(tick, intervalMs);
        }, delay);
      })();
    },

    stop() {
      if (state.timer) {
        if (state._timerIsInterval) {
          window.clearInterval(state.timer);
        } else {
          window.clearTimeout(state.timer);
        }
        state.timer = null;
        state._timerIsInterval = false;
      }
      state.activeType = null;
      state.lastData = null;
      state.appearance = { textColor: '', bgColor: '' };
      hideRoot();
    },

    // Utility: simple JSON fetch with timeout
    async fetchJson(url, { timeoutMs = 6000 } = {}) {
      const controller = new AbortController();
      const t = window.setTimeout(() => controller.abort(), timeoutMs);
      try {
        const res = await fetch(url, { signal: controller.signal, credentials: "same-origin" });
        if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
        return await res.json();
      } finally {
        window.clearTimeout(t);
      }
    }
  };

  window.OverlayEngine = OverlayEngine;

  // Public helpers for renderers that manage their own cycling
  OverlayEngine.tick   = tick;
  OverlayEngine.isActive = function (type) { return state.activeType === type; };
})();

/* Status overlay renderer (v1)
 * Endpoint: GET /api/status
 * Expected response:
 * {
 *   "updated": "ISO8601",
 *   "items": [
 *     { "label": "Plex", "value": "OK", "state": "good" }
 *   ]
 * }
 */
(function () {
  const TYPE = "status";

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function buildSkeleton(root) {
    root.querySelectorAll(".vc-overlay").forEach(e => e.remove());
    root.classList.remove("hidden");

    const overlay = el("div", "vc-overlay");
    const safe = el("div", "vc-safe");

    const title = el("div", "vc-pill", "System Status");
    const stack = el("div", "vc-stack");
    stack.id = "vc-status-stack";

    safe.appendChild(title);
    safe.appendChild(stack);
    overlay.appendChild(safe);
    root.appendChild(overlay);
  }

  function render(data, root) {
    if (!root.querySelector(".vc-overlay")) buildSkeleton(root);

    const stack = root.querySelector("#vc-status-stack");
    stack.innerHTML = "";
    const items = Array.isArray(data?.items) ? data.items : [];
    items.slice(0, 8).forEach((it) => {
      const row = el("div", "vc-headline");
      const label = el("div", "vc-source", it.label || "");
      const text = el("div", null, `${it.value ?? ""} ${it.unit ?? ""}`.trim());
      row.appendChild(label);
      row.appendChild(text);
      stack.appendChild(row);
    });
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson("/api/virtual/status");
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render });
})();

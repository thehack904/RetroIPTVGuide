/* Weather overlay renderer (v1)
 * Endpoint: GET /api/weather
 * Expected minimal response shape:
 * {
 *   "updated": "ISO8601",
 *   "location": "City, ST",
 *   "now": { "temp": 72, "condition": "Cloudy" },
 *   "forecast": [
 *     { "label": "Today", "hi": 75, "lo": 61, "condition": "Rain" }
 *   ]
 * }
 */
(function () {
  const TYPE = "weather";

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

    const pill = el("div", "vc-pill");
    pill.id = "vc-weather-pill";

    const stack = el("div", "vc-stack");
    stack.id = "vc-weather-stack";

    safe.appendChild(pill);
    safe.appendChild(stack);
    overlay.appendChild(safe);
    root.appendChild(overlay);
  }

  function render(data, root) {
    if (!root.querySelector(".vc-overlay")) buildSkeleton(root);

    const pill = root.querySelector("#vc-weather-pill");
    const loc = data?.location || "Weather";
    const now = data?.now || {};
    const t = (now.temp != null) ? `${now.temp}°` : "--";
    const c = now.condition || "";
    pill.textContent = `${loc}  ${t}  ${c}`.trim();

    const stack = root.querySelector("#vc-weather-stack");
    stack.innerHTML = "";
    const fc = Array.isArray(data?.forecast) ? data.forecast : [];
    fc.slice(0, 5).forEach((d) => {
      const row = el("div", "vc-headline");
      const label = el("div", "vc-source", d.label || "");
      const text = el("div", null);
      const title = el("div", null, `${d.hi ?? "--"}° / ${d.lo ?? "--"}°  ${d.condition ?? ""}`.trim());
      text.appendChild(title);
      row.appendChild(label);
      row.appendChild(text);
      stack.appendChild(row);
    });
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson("/api/weather");
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render });
})();

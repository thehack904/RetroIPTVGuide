/* Weather overlay renderer (v2)
 * Endpoint: GET /api/weather
 * Full response shape (v2):
 * {
 *   "updated": "HH:MM AM/PM",
 *   "location": "City, ST",
 *   "now": { "temp": 72, "condition": "Partly Cloudy",
 *             "humidity": 65, "wind": "SSW 10 mph", "feels_like": 74, "icon": "partly_cloudy" },
 *   "today": [
 *     { "label": "MORNING",   "temp": 76, "condition": "Sunny",        "icon": "sunny" },
 *     { "label": "AFTERNOON", "temp": 85, "condition": "Hot & Humid",  "icon": "partly_cloudy" },
 *     { "label": "EVENING",   "temp": 68, "condition": "Partly Cloudy","icon": "partly_cloudy_night" }
 *   ],
 *   "extended": [
 *     { "dow": "TUE", "hi": 89, "lo": 70, "condition": "T-Storms", "icon": "thunderstorm" }
 *   ],
 *   "ticker": ["Severe Thunderstorms Possible Tomorrow"],
 *   "forecast": [ { "label": "Today", "hi": 75, "lo": 61, "condition": "Rain" } ]
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

    // Prefer extended outlook; fall back to legacy forecast list
    const fc = Array.isArray(data?.extended) && data.extended.length
      ? data.extended
      : (Array.isArray(data?.forecast) ? data.forecast : []);

    fc.slice(0, 5).forEach((d) => {
      const row = el("div", "vc-headline");
      const label = el("div", "vc-source", d.dow || d.label || "");
      const text = el("div", null);
      const hi = d.hi ?? "--";
      const lo = d.lo ?? "--";
      const cond = d.condition ?? "";
      const title = el("div", null, `${hi}° / ${lo}°  ${cond}`.trim());
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


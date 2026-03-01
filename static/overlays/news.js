/* News overlay renderer (v1)
 * Endpoint: GET /api/news
 * Expected response:
 * {
 *   "updated": "ISO8601",
 *   "headlines": [
 *     { "title": "...", "source": "BBC", "url": "https://...", "ts": "ISO8601" }
 *   ]
 * }
 */
(function () {
  const TYPE = "news";

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function buildSkeleton(root) {
    root.querySelectorAll(".vc-overlay, .vc-ticker").forEach(e => e.remove());
    root.classList.remove("hidden");

    const overlay = el("div", "vc-overlay");
    const safe = el("div", "vc-safe");

    const l3 = el("div", "vc-l3");
    const stack = el("div", "vc-stack");
    stack.id = "vc-news-stack";

    const ticker = el("div", "vc-ticker");
    const track = el("div", "vc-ticker__track");
    track.id = "vc-news-ticker-track";
    ticker.appendChild(track);

    l3.appendChild(stack);
    safe.appendChild(l3);
    overlay.appendChild(safe);
    overlay.appendChild(ticker);
    root.appendChild(overlay);
  }

  function render(data, root) {
    if (!root.querySelector(".vc-overlay")) buildSkeleton(root);

    const headlines = Array.isArray(data?.headlines) ? data.headlines : [];
    const top = headlines.slice(0, 5);

    const stack = root.querySelector("#vc-news-stack");
    stack.innerHTML = "";

    top.forEach((h, idx) => {
      const row = el("div", "vc-headline");
      const num = el("div", "vc-source", String(idx + 1).padStart(2, "0"));
      const text = el("div", null);
      const title = el("div", null, h.title || "(untitled)");
      const src = el("div", "vc-source", h.source ? `— ${h.source}` : "");

      text.appendChild(title);
      if (h.source) text.appendChild(src);

      row.appendChild(num);
      row.appendChild(text);
      stack.appendChild(row);
    });

    const tickerTrack = root.querySelector("#vc-news-ticker-track");
    const tickerText = headlines.slice(0, 12).map(h => h.title).filter(Boolean).join("   •   ");
    tickerTrack.textContent = tickerText || "No headlines available";
  }

  async function fetchData() {
    return await window.OverlayEngine.fetchJson("/api/news");
  }

  window.OverlayEngine.register(TYPE, { fetch: fetchData, render });
})();

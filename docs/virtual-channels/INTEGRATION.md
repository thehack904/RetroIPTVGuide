# Virtual Channels v1 — Integration Notes (Loop Video + Overlay)

This bundle provides the **frontend overlay engine + renderers** and placeholder loop assets.
Because RetroIPTVGuide repo layouts vary, this file explains *where to wire it in*.

## 1) Add overlay root above your video element
Place this *inside the same positioned container* that holds the video player:

```html
<div id="player-container" style="position:relative;">
  <video id="videoPlayer" ...></video>
  <div id="virtual-overlay-root" aria-hidden="true"></div>
</div>
```

> Requirement: `#player-container` must be `position: relative;` so the overlay can be absolutely positioned.

## 2) Include CSS
Ensure `static/css/virtual-overlays.css` is loaded after base/theme CSS.

## 3) Include overlay engine + renderers
Add these scripts near the end of your page (or via your bundler):

```html
<script src="/static/overlays/overlay-engine.js"></script>
<script src="/static/overlays/news.js"></script>
<script src="/static/overlays/weather.js"></script>
<script src="/static/overlays/status.js"></script>
```

## 4) Hook tune/play logic
In your “tune channel” function, add:

Pseudo-code:

```js
OverlayEngine.stop();

if (channel.is_virtual && channel.playback_mode === "local_loop") {
  const video = document.getElementById("videoPlayer");
  video.src = channel.loop_asset;
  video.loop = true;
  video.muted = true; // allow autoplay
  video.play().catch(()=>{});

  OverlayEngine.start({
    type: channel.overlay_type,
    refreshSeconds: channel.overlay_refresh_seconds,
  });

  return;
}

// Normal channels:
document.getElementById("virtual-overlay-root").classList.add("hidden");
```

## 5) Provide data endpoints
The included renderers expect:
- News: `GET /api/news` -> `{ updated, headlines: [{title, source, url, ts}] }`
- Weather: `GET /api/weather` -> minimal `{ updated, location, now, forecast[] }` (shape documented in `weather.js`)
- Status: `GET /api/status` -> minimal `{ updated, items: [{label, value, unit, state}] }`

If you don’t have these yet, you can start with mocked JSON or static sample responses.

## 6) Add the virtual channel rows to your channel list
Create a `get_virtual_channels()` function server-side and merge them into the channel list you render.

Example IDs:
- `virtual.news` (900)
- `virtual.weather` (901)
- `virtual.status` (902)

## Notes
- Renderers are defensive: if endpoint fails, the overlay shows a small error pill but does not break playback.
- Overlays are `pointer-events:none` by default; you can enable interactions per channel later.

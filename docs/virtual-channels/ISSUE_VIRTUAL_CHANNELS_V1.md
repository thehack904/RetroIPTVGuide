# GitHub Issue: Virtual Channels (Loop Video + Overlay Playback)

## Summary
Introduce a **Virtual Channel system (UI-only)** that allows RetroIPTVGuide to create channels that:

- Appear in the guide like tuner-based channels
- Tune inside the existing video player
- Play a **local looping video background**
- Render dynamic **HTML/CSS overlays** above the player
- Update overlay content on a timed interval to simulate “live” programming

## Goals
1. Virtual channels look and behave like regular channels in the grid.
2. Playback uses the existing `<video>` player.
3. Video background is a local looped MP4 asset.
4. Overlay layer renders dynamic content above the player.
5. Overlays update on a set interval.
6. No external app export logic required (UI-only).

## Virtual Channel Data Model
Example:

```json
{
  "id": "virtual.news",
  "number": 900,
  "name": "News Headlines",
  "logo": "/static/logos/virtual/news.png",
  "group": "Virtual",
  "is_virtual": true,
  "playback_mode": "local_loop",
  "loop_asset": "/static/loops/news.mp4",
  "overlay_type": "news",
  "overlay_refresh_seconds": 60
}
```

### Required fields
- `id`, `number`, `name`, `logo`, `group`
- `is_virtual`
- `playback_mode` (v1: `local_loop`)
- `loop_asset`
- `overlay_type`
- `overlay_refresh_seconds`

## Acceptance Criteria
- [ ] Virtual channel appears in grid.
- [ ] Tuning plays local loop video.
- [ ] Overlay renders above player.
- [ ] Overlay updates on interval.
- [ ] Switching away removes overlay.
- [ ] Display size scaling works (Large/Medium/Small).
- [ ] Does not break normal tuner channels.

## Out of Scope
- M3U export
- HLS stream generation
- Canvas captureStream (3B)
- Audio bed support

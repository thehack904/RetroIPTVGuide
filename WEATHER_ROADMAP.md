
# 🌦 RetroIPTVGuide — Weather Channel Roadmap

---

## 🎯 Vision

Channel 1 will function as a fully animated, personalized Weather Channel inside RetroIPTVGuide.

It will:

- Auto-loop like a real broadcast
- Support manual remote override (Mode D)
- Include alert interruption behavior
- Support built-in and user-uploaded music
- Be fully per-user personalized (ZIP, preferences, theme)
- Be optional and user-toggleable
- Rival paid IPTV apps in polish and functionality

---

# 🟦 Phase 1 — Weather Core

## Goal
Deliver a stable, per-user Weather Channel foundation.

---

## Features

### 1. Per-User Weather Settings

Database Fields:
- `weather_enabled` (boolean)
- `weather_zip` (string)
- `weather_units` (F/C)

Settings UI:
- Weather Channel enable/disable toggle
- ZIP code input
- Units selector

Behavior:
- Channel hidden when disabled
- Weather API not called when disabled
- Settings preserved even when disabled

---

### 2. Weather API Endpoint

Route:
/api/weather

Requirements:
- Fetch weather by ZIP
- Normalize response format
- Cache per ZIP (10–15 min TTL)
- Graceful failure handling
- Alert data included in response

---

### 3. Virtual Channel 1 Implementation

- Channel 1 is internal-only
- Tuning loads `/internal/weather`
- Does NOT use `<video>`
- Not exported to M3U initially

---

### 4. Weather Page (Initial Panels)

Panels:
- Current Conditions
- Hourly Forecast
- 7-Day Forecast

Always Visible:
- Clock
- Bottom Ticker

---

### 5. Basic Auto-Loop Engine

- Panel sequence array
- Duration per panel
- Smooth transitions
- Automatic restart
- No user interaction required

---

# 🟩 Phase 2 — Broadcast Mode

## Goal
Make Channel 1 feel alive.

---

### Motion & Animation

- Slide/fade panel transitions
- Animated weather icons
- Subtle background gradient drift
- Always-moving ticker

---

### Radar Panel

- Animated radar frames
- Frame cycling
- Static fallback if unavailable

---

### Severe Weather Alert Mode

- Alert detection from API
- Banner overlay
- Interrupt main loop
- Resume normal sequence
- Persistent alert ribbon

---

# 🟨 Phase 3 — Mode D (Auto + Manual Control)

## Goal
Combine automatic broadcast with user control.

---

### Manual Controls

- Left/Right → Change panel
- OK → Pin/unpin panel
- Inactivity timeout (20–30 seconds)
- Auto-resume loop
- Manual mode indicator

---

### Behavior

- Channel never static
- User override does not break loop
- Clean transition back to auto mode

---

# 🟧 Phase 4 — Audio System

## Goal
Add immersive background music.

---

### Default Music Library

- 5–10 royalty-free loops
- Volume normalized
- Music OFF by default
- Enable prompt on first tune
- Per-user preference saved

---

### Playback Engine

- HTML5 `<audio loop>` element
- Volume control
- Fade in/out transitions
- Track selection UI
- Shuffle mode

---

### User Music Upload

Endpoint:
/api/weather/music/upload

Requirements:
- Authenticated upload
- File validation (MP3 / OGG / AAC)
- File size limit
- Stored per user:
  `/config/weather_music/<user_id>/`
- Track metadata storage
- Playlist selection

---

# 🟪 Phase 5 — Theme Packs

## Goal
Deliver nostalgic differentiation.

---

### Theme Architecture

- CSS variable-based theme system
- Per-user theme selection
- Dynamic theme switching

---

### Initial Themes

- 90s Classic
- 2000s Digital Cable
- Modern Clean
- Severe Weather Theme

---

# 🟥 Phase 6 — Premium Enhancements

---

### Daypart Programming

- Timed broadcast structure
- Structured forecast cadence
- Optional scheduled layout mode

---

### External Tokenized Access

- Signed URL support
- Expiring tokens
- Optional inclusion in exported M3U

---

### Performance Controls

- Reduced Motion Mode
- Low CPU Mode
- Radar disable toggle
- Memory cleanup on channel exit

---

# 🔐 Enable / Disable Behavior Summary

## When Disabled

- Channel 1 hidden
- Weather API inactive
- Music system inactive
- Settings preserved

## When Enabled

- Channel 1 visible
- Weather API active
- Loop engine running
- Music system available

---

# 📊 Definition of Done

Channel 1 must:

- Be optional per user
- Auto-loop continuously
- Support manual override
- Interrupt for alerts
- Support built-in and user-uploaded music
- Run for hours without degradation
- Perform well on low-power devices
- Feel like a live broadcast, not a static webpage

---

# 🚀 Long-Term Expansion

- Travel index (UV, pollen, sunrise)
- News/sports ticker integrations
- Multi-location support
- Household shared profile
- Custom broadcast schedule builder
- Seasonal and holiday themes
- Emergency override mode

---

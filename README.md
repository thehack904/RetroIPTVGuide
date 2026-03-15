# 📺 RetroIPTVGuide

```{=html}
<p align="center">
```
`<a href="https://github.com/thehack904/RetroIPTVGuide">`{=html}
`<img src="https://img.shields.io/badge/version-v4.8.0-blue?style=for-the-badge" alt="Version">`{=html}
`</a>`{=html}
`<a href="https://github.com/thehack904/RetroIPTVGuide/pkgs/container/retroiptvguide">`{=html}
`<img src="https://img.shields.io/badge/GHCR-ghcr.io/thehack904/retroiptvguide-green?style=for-the-badge&logo=docker" alt="GHCR">`{=html}
`</a>`{=html}
`<a href="https://github.com/thehack904/RetroIPTVGuide/actions/workflows/docker-publish.yml">`{=html}
`<img src="https://img.shields.io/github/actions/workflow/status/thehack904/RetroIPTVGuide/docker-publish.yml?style=for-the-badge&logo=github" alt="Build Status">`{=html}
`</a>`{=html}
```{=html}
</p>
<p align="center">
  <img src="docs/screenshots/RetroIPTVGuide.png" width="900">
</p>
```
RetroIPTVGuide is a **self‑hosted IPTV guide interface** inspired by
classic cable television listings from the 1990s and early 2000s.

It aggregates **IPTV playlists and XMLTV program data** and presents
them in a **retro‑style channel guide** designed for home labs, media
servers, and smart TV browsers.

The project works particularly well alongside playout systems such as
**ErsatzTV**, but supports any IPTV backend that provides:

-   `.m3u` / `.m3u8` playlists\
-   XMLTV `.xml` EPG data\
-   **HLS segmented streams** for browser playback

------------------------------------------------------------------------

## 🚀 Features

• Classic **TV‑style grid guide** for IPTV playlists\
• **Virtual channels** (News, Weather, Traffic, System Status)\
• **Multiple IPTV sources** combined into a single guide\
• **Auto‑scroll channel navigation**\
• **Retro UI themes** inspired by classic TV guides\
• **TV‑optimized interface** for Android TV / Fire TV / browsers\
• **User management** and admin tools\
• **Local‑first architecture** with no cloud dependencies

------------------------------------------------------------------------

## 📦 Releases

Official builds are published through **GitHub Releases**.

https://github.com/thehack904/RetroIPTVGuide/releases

Docker images are automatically built through GitHub Actions.

------------------------------------------------------------------------

## 🐳 Quick Start (Docker)

docker pull ghcr.io/thehack904/retroiptvguide:latest docker run -d -p
5000:5000 ghcr.io/thehack904/retroiptvguide:latest

Then open:

http://`<server-ip>`{=html}:5000

Default login:

admin / strongpassword123

------------------------------------------------------------------------

## 📚 Documentation

Detailed guides are available in the repository:

-   INSTALL.md -- Installation and update instructions
-   ARCHITECTURE.md -- System architecture
-   DATA_FLOW.md -- How playlists and EPG data are processed
-   PROJECT_STRUCTURE.md -- Repository layout
-   SECURITY_MODEL.md -- Security design
-   CHANGELOG.md -- Release history
-   ROADMAP.md -- Planned features

------------------------------------------------------------------------

## IPTV Compatibility

RetroIPTVGuide requires **HLS segmented streams** for browser playback.

Many IPTV servers output **MPEG‑TS streams**, which are not directly
playable in browsers.

For best compatibility, use an IPTV backend that provides **HLS
output**, such as **ErsatzTV**.

------------------------------------------------------------------------

## 🤝 Contributing

Contributions are welcome.

1.  Open an issue describing the change
2.  Fork the repository
3.  Submit a pull request

------------------------------------------------------------------------

## Project Information

Repository: https://github.com/thehack904/RetroIPTVGuide\
License: CC BY‑NC‑SA 4.0\
Maintainer: @thehack904

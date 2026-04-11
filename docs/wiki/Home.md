# 📺 RetroIPTVGuide Wiki

Welcome to the **RetroIPTVGuide** wiki. This is the central reference for installing,
configuring, and using RetroIPTVGuide.

---

## What Is RetroIPTVGuide?

RetroIPTVGuide is a **self-hosted IPTV guide interface** inspired by classic cable
television listings from the 1990s and early 2000s. It aggregates IPTV playlists and
XMLTV program data and presents them through a retro-style channel guide optimised for
home labs, smart TV browsers, and Raspberry Pi kiosks.

RetroIPTVGuide is an **interface only**. It does not host, transcode, or distribute
any media content.

---

## Quick Start

```
docker pull ghcr.io/thehack904/retroiptvguide:latest
docker run -d -p 5000:5000 ghcr.io/thehack904/retroiptvguide:latest
```

Open `http://<server-ip>:5000` and log in with the default credentials
(`admin` / `strongpassword123`). You will be prompted to change the password
immediately.

---

## Wiki Pages

| Page | Description |
|------|-------------|
| [Installation](Installation.md) | Docker, Linux, Raspberry Pi, and Windows install guides |
| [Configuration](Configuration.md) | Tuner setup, settings, data directory, environment variables |
| [Virtual Channels](Virtual-Channels.md) | Overview of all 9 built-in virtual channels |
| [FAQ](FAQ.md) | Frequently asked questions |
| [Troubleshooting](Troubleshooting.md) | Common problems and how to fix them |

---

## Key Repository Documents

| Document | Description |
|----------|-------------|
| [README.md](../../README.md) | Project overview and quick start |
| [INSTALL.md](../../INSTALL.md) | Detailed installation instructions |
| [ARCHITECTURE.md](../../ARCHITECTURE.md) | System architecture |
| [DATA_FLOW.md](../../DATA_FLOW.md) | How playlists and EPG data are processed |
| [SECURITY_MODEL.md](../../SECURITY_MODEL.md) | Security design |
| [CHANGELOG.md](../../CHANGELOG.md) | Release history |
| [ROADMAP.md](../../ROADMAP.md) | Planned features |
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | Contribution guidelines |

---

## Links

- **Repository:** https://github.com/thehack904/RetroIPTVGuide  
- **Releases:** https://github.com/thehack904/RetroIPTVGuide/releases  
- **Issues:** https://github.com/thehack904/RetroIPTVGuide/issues  
- **Docker Image:** `ghcr.io/thehack904/retroiptvguide:latest`  
- **License:** CC BY-NC-SA 4.0

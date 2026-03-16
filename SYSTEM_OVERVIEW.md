# SYSTEM_OVERVIEW.md

This document provides a simplified overview of how RetroIPTVGuide operates.

---

## Purpose

RetroIPTVGuide provides a television‑guide style interface for IPTV playlists.

Instead of using a traditional IPTV player layout, the system recreates a classic TV guide grid interface.

---

## Core Responsibilities

RetroIPTVGuide performs the following functions:

- ingest IPTV playlists
- parse EPG data
- map channels to program listings
- render a guide interface
- launch playback streams

---

## What RetroIPTVGuide Does NOT Do

RetroIPTVGuide is intentionally lightweight.

It does not:

- transcode video streams
- host IPTV streams
- manage DRM
- replace IPTV servers

---

## Typical Deployment Architecture

Media Server
   |
   +-- IPTV Server (IPTV Source / ErsatzTV)
   |
   +-- RetroIPTVGuide
           |
           +-- Web Browser / TV Display

RetroIPTVGuide acts as the presentation layer.

---

## Typical Use Cases

Common deployments include:

- home media servers
- retro CRT television guide displays
- Raspberry Pi guide kiosks
- smart TV browser interfaces
- home theater projectors

---

## Project Philosophy

The project focuses on:

- simplicity
- compatibility
- retro aesthetics
- self‑hosted deployments
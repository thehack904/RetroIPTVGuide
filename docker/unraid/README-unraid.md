# RetroIPTVGuide – Unraid Template *BETA*

This repository contains the Unraid Docker template for **RetroIPTVGuide**.

## What this is
An Unraid-compatible XML template that pre-populates:
- Docker image (`ghcr.io/thehack904/retroiptvguide:latest`)
- WebUI port mapping
- Persistent volume mappings (`/app/config`, `/app/logs`, `/app/data`)
- Common environment variables (TZ, etc.)

#### BETA Limitations
- Not indexed by **Community Applications**
- Template fields and defaults may change
- Limited Unraid-specific testing to date
- No migration guarantees between template revisions during beta

## Install methods

### Method 1: Manual install (works immediately)
Use this method if you do **not** use Community Applications, or you want to test quickly.

1. In Unraid, go to **Docker** → **Add Container**
2. Click **Template** (or **Add Container** UI option) and locate the **Template URL** field
3. Paste the raw XML URL for this template:

   `https://raw.githubusercontent.com/thehack904/retroiptvguide-unraid/main/templates/RetroIPTVGuide.xml`

4. Apply / install
5. Review port mappings and storage paths.
6. **IMPORTANT:** Set a secure value for `SECRET_KEY` before starting the container.
7. Start the container.


Notes:
- Feedback from Unraid users is welcome and will help promote this install method out of BETA.
- Updates to the XML are not automatically “pushed” into existing installs; users typically re-apply changes manually.

### Method 2: Community Applications - Currently under development 

## Support
- Project: https://github.com/thehack904/retroiptvguide
- Issues: https://github.com/thehack904/retroiptvguide/issues


# INSTALL.md

This document provides detailed installation, update, and uninstall
instructions for RetroIPTVGuide.

------------------------------------------------------------------------

# Docker Installation (Recommended)

Pull the latest container:

docker pull ghcr.io/thehack904/retroiptvguide:latest

Run the container:

docker run -d -p 5000:5000 ghcr.io/thehack904/retroiptvguide:latest

Access the interface:

http://`<server-ip>`{=html}:5000

------------------------------------------------------------------------

# Linux Installation

Run the official installer:

curl -sSL
https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_linux.sh
\| sudo bash -s install --agree --yes

Default install location:

/home/iptv/iptv-server

------------------------------------------------------------------------

# Raspberry Pi Installation

curl -sSL
https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_rpi.sh
\| sudo bash -s install --agree --yes

Supported hardware:

-   Raspberry Pi 3
-   Raspberry Pi 4
-   Raspberry Pi 5

------------------------------------------------------------------------

# Windows Installation

Set-ExecutionPolicy Bypass -Scope Process -Force Invoke-WebRequest
https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_windows.bat
-OutFile retroiptv_windows.bat .`\retroiptv`{=tex}\_windows.bat install

------------------------------------------------------------------------

# Updating

Linux

sudo /home/iptv/iptv-server/retroiptv_linux.sh update --yes

Raspberry Pi

sudo /home/iptv/iptv-server/retroiptv_rpi.sh update --yes

Docker

docker pull ghcr.io/thehack904/retroiptvguide:latest

Restart the container after pulling the new image.

------------------------------------------------------------------------

# Uninstall

Linux

sudo /home/iptv/iptv-server/retroiptv_linux.sh uninstall --yes

Raspberry Pi

sudo /home/iptv/iptv-server/retroiptv_rpi.sh uninstall --yes

Windows

Run the installer again and select **Uninstall**.

------------------------------------------------------------------------

# Default Login

Username: admin\
Password: strongpassword123

Change the password after the first login.

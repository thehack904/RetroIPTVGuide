# INSTALL.md

This document provides detailed installation, update, and uninstall
instructions for RetroIPTVGuide.

------------------------------------------------------------------------

# Docker Installation (Recommended)

Pull the latest container:
```
docker pull ghcr.io/thehack904/retroiptvguide:latest
```
Run the container:
```
docker run -d -p 5000:5000 ghcr.io/thehack904/retroiptvguide:latest
```
Access the interface:

http://`<server-ip>`{=html}:5000

------------------------------------------------------------------------

# Linux Installation

## Option A — From a downloaded release archive (no internet required for repo files)

Download the release `.zip` or `.tar.gz` from the
[Releases page](https://github.com/thehack904/RetroIPTVGuide/releases), extract it,
then run the installer from inside the extracted directory:

```bash
# Example using v4.9.4
wget https://github.com/thehack904/RetroIPTVGuide/archive/refs/tags/v4.9.4.tar.gz
tar -xzf v4.9.4.tar.gz
cd RetroIPTVGuide-4.9.4
sudo bash retroiptv_linux.sh install --agree
```

The installer detects that `app.py` and `requirements.txt` are present alongside the
script and uses those files directly — no `git clone` is performed.

## Option B — Direct curl one-liner (clones from GitHub)

```
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_linux.sh | sudo bash -s install --agree --yes
```

If the full repository is **not** detected in the current directory the installer will
ask for confirmation before cloning from GitHub. Pass `--yes` to skip the prompt.

Default install location:

/home/iptv/iptv-server

------------------------------------------------------------------------

# Raspberry Pi Installation

## Option A — From a downloaded release archive (no internet required for repo files)

```bash
wget https://github.com/thehack904/RetroIPTVGuide/archive/refs/tags/v4.9.4.tar.gz
tar -xzf v4.9.4.tar.gz
cd RetroIPTVGuide-4.9.4
sudo bash retroiptv_rpi.sh install --agree
```

The installer detects the local release files and skips the GitHub clone step.

## Option B — Direct curl one-liner (clones from GitHub)

```
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_rpi.sh | sudo bash -s install --agree --yes
```

If the full repository is **not** detected in the current directory the installer will
ask for confirmation before cloning. Pass `--yes` to skip the prompt.

Supported hardware:

-   Raspberry Pi 3
-   Raspberry Pi 4
-   Raspberry Pi 5

------------------------------------------------------------------------

# Windows Installation

> ⚠️ **Deprecation Notice:** The Windows installer will be discontinued in **v5.0**. Docker is the recommended deployment method. See [Docker Installation](#docker-installation-recommended) above.

## Option A — From a downloaded release archive (no internet required for repo files)

Download the `.zip` from the [Releases page](https://github.com/thehack904/RetroIPTVGuide/releases),
extract it, then open PowerShell **as Administrator** in the extracted folder and run:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\retroiptv_windows.ps1 install --agree
```

The installer detects that `app.py` and `requirements.txt` are present and uses those
files directly — no `git clone` is performed.

## Option B — Download script and run (clones from GitHub if needed)

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
Invoke-WebRequest https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_windows.bat `
  -OutFile retroiptv_windows.bat
.\retroiptv_windows.bat install
```

If the full repository is **not** detected in the current directory the installer will
ask for confirmation before cloning from GitHub. Pass `--yes` to skip the prompt.
------------------------------------------------------------------------

# Updating

Linux
```
sudo /home/iptv/iptv-server/retroiptv_linux.sh update --yes
```
Raspberry Pi
```
sudo /home/iptv/iptv-server/retroiptv_rpi.sh update --yes
```
Docker
```
docker pull ghcr.io/thehack904/retroiptvguide:latest
```
Restart the container after pulling the new image.

------------------------------------------------------------------------

# Uninstall

Linux
```
sudo /home/iptv/iptv-server/retroiptv_linux.sh uninstall --yes
```
Raspberry Pi
```
sudo /home/iptv/iptv-server/retroiptv_rpi.sh uninstall --yes
```
Windows

Run the installer again and select **Uninstall**.

------------------------------------------------------------------------

# Default Login

Username: admin
Password: strongpassword123

Change the password after the first login.


------------------------------------------------------------------------

## 🔐 Admin Password Recovery

If the admin password is lost, it can be reset using the provided script.

### Reset Command

python3 /home/iptv/iptv-server/scripts/reset_admin_password.py --db /home/iptv/iptv-server/config/users.db

### Common Permission Issue

If you see a database write error, it is likely due to ownership mismatch.

Example error:
- File owned by: iptv
- Current user: anotheruser

Run the script as the correct user:

sudo -u iptv python3 /home/iptv/iptv-server/scripts/reset_admin_password.py --db /home/iptv/iptv-server/config/users.db

### Immutable File Check (Rare)

If the issue persists, check if the file is immutable:

lsattr /home/iptv/iptv-server/config/users.db

If an `i` flag is present, remove it:

sudo chattr -i /home/iptv/iptv-server/config/users.db

### Result

On success:
- Password is reset
- Admin is required to change password on next login

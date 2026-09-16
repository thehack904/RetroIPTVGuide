# INSTALL.md

This document provides detailed installation, migration, update, backup, restore,
rollback, and removal instructions for RetroIPTVGuide.

------------------------------------------------------------------------

# Docker Installation (Recommended)

Pull the latest container:
```bash
docker pull ghcr.io/thehack904/retroiptvguide:latest
```

Run the container:
```bash
docker run -d -p 5000:5000 ghcr.io/thehack904/retroiptvguide:latest
```

Access the interface:

http://`<server-ip>`{=html}:5000

------------------------------------------------------------------------

# Linux Installation

## Standard Linux filesystem layout (v4.9.9+)

Fresh Linux installs now use a dedicated service account and FHS-style paths:

- Application code and virtual environment: `/opt/retroiptvguide`
- Administrator-managed environment file: `/etc/retroiptvguide/retroiptvguide.env`
- Mutable state, databases, uploads, caches, and app logs: `/var/lib/retroiptvguide`
- Dedicated service account: `retroiptvguide`
- systemd unit: `/etc/systemd/system/retroiptvguide.service`

Expected ownership and permissions after install:

- `/opt/retroiptvguide` → root-owned, mode `755`
- `/etc/retroiptvguide` → root-owned, mode `755`
- `/etc/retroiptvguide/retroiptvguide.env` → root-owned, mode `640`
- `/var/lib/retroiptvguide` → `retroiptvguide:retroiptvguide`, mode `750`

## Fresh install

### Option A — From a downloaded release archive

Download the release `.zip` or `.tar.gz` from the
[Releases page](https://github.com/thehack904/RetroIPTVGuide/releases), extract it,
then run the installer from inside the extracted directory:

```bash
# Example using v4.9.9
wget https://github.com/thehack904/RetroIPTVGuide/archive/refs/tags/v4.9.9.tar.gz
tar -xzf v4.9.9.tar.gz
cd RetroIPTVGuide-4.9.9
sudo bash retroiptv_linux.sh install --agree
```

The installer detects that `app.py` and `requirements.txt` are present alongside the
script and uses those files directly — no `git clone` is performed.

### Option B — Direct curl one-liner

```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_linux.sh | sudo bash -s install --agree --yes
```

If the full repository is **not** detected in the current directory the installer will
ask for confirmation before cloning from GitHub. Pass `--yes` to skip the prompt.

## Dedicated service-account behavior

- The Linux installer creates the `retroiptvguide` system account if needed.
- The service runs as `retroiptvguide`, not as the legacy shared `iptv` account.
- The installer writes `RETROIPTV_DATA_DIR=/var/lib/retroiptvguide` into
  `/etc/retroiptvguide/retroiptvguide.env`.
- The systemd unit loads that environment file and starts the app from
  `/opt/retroiptvguide`.

## Upgrade from `/home/iptv/iptv-server`

Linux migration is **automatic** when the v4.9.9+ Linux installer or updater sees the
legacy RetroIPTVGuide layout.

The migration flow:

1. Detects the legacy installation and creates a timestamped pre-migration backup under
   `/var/backups/retroiptvguide-migration-*`
2. Copies legacy state from `/home/iptv/iptv-server/config` into `/var/lib/retroiptvguide`
   and moves legacy uploads and generated road/map caches into the corresponding
   `/var/lib/retroiptvguide/uploads` and `/var/lib/retroiptvguide/cache` directories
3. Preserves any conflicting legacy state files in a clearly named migration-conflicts
   directory instead of silently overwriting either version
4. Writes the dedicated-account environment and systemd configuration for
   `retroiptvguide.service`
5. Validates the migrated installation and persistent state before writing the
   `.migration_v4.9.9` success marker
6. Removes the legacy `iptv-server.service` unit **only** when it is confirmed to belong
   to RetroIPTVGuide
7. Removes `/home/iptv/iptv-server` only when the migration succeeded and shared-user /
   RetroStation MC safeguards confirm nothing else still depends on the legacy path

The migration does **not** delete sibling projects, shared `/home/iptv` directories, or
the legacy shared `iptv` account.

## Updating

Linux:
```bash
sudo /opt/retroiptvguide/retroiptv_linux.sh update --yes
```

Raspberry Pi:
```bash
sudo /home/iptv/iptv-server/retroiptv_rpi.sh update --yes
```

Docker:
```bash
docker pull ghcr.io/thehack904/retroiptvguide:latest
```

Restart the container after pulling the new image.

## Backup and restore

### Back up the Linux install

```bash
sudo systemctl stop retroiptvguide
sudo tar -C /opt -czf retroiptvguide-app.tgz retroiptvguide
sudo tar -C /etc -czf retroiptvguide-etc.tgz retroiptvguide
sudo tar -C /var/lib -czf retroiptvguide-state.tgz retroiptvguide
sudo systemctl start retroiptvguide
```

At minimum, preserve `/etc/retroiptvguide` and `/var/lib/retroiptvguide` before major
upgrades or host maintenance.

### Restore the Linux install

```bash
sudo systemctl stop retroiptvguide
sudo tar -C /opt -xzf retroiptvguide-app.tgz
sudo tar -C /etc -xzf retroiptvguide-etc.tgz
sudo tar -C /var/lib -xzf retroiptvguide-state.tgz
sudo chown -R root:root /opt/retroiptvguide
sudo chown -R retroiptvguide:retroiptvguide /var/lib/retroiptvguide
sudo systemctl daemon-reload
sudo systemctl start retroiptvguide
```

## Rollback procedure

If you need to recover after the Linux layout migration:

1. Stop the new service:
   ```bash
   sudo systemctl stop retroiptvguide
   sudo systemctl disable retroiptvguide
   ```
2. Restore the installer-created pre-migration backup from
   `/var/backups/retroiptvguide-migration-*/legacy-state.tar.gz` and any other host
   backups you maintain.
3. Reinstall or restore the older RetroIPTVGuide release from your saved archive.
4. Recreate or restore the legacy `iptv-server.service` unit before starting the legacy
   deployment.

The legacy `/home/iptv/iptv-server` tree may already have been removed if the installer
determined that no other shared-user components still depended on it, so the migration
backup is the primary rollback copy when cleanup occurs.

## systemd status, logs, and troubleshooting

Useful commands:

```bash
sudo systemctl status retroiptvguide
sudo journalctl -u retroiptvguide -n 200 --no-pager
sudo journalctl -u retroiptvguide -f
sudo cat /etc/retroiptvguide/retroiptvguide.env
sudo ls -la /opt/retroiptvguide /etc/retroiptvguide /var/lib/retroiptvguide
```

Troubleshooting checklist:

- Confirm the service account exists: `id retroiptvguide`
- Confirm the app path exists: `ls /opt/retroiptvguide`
- Confirm the data path is writable by the service account:
  `sudo -u retroiptvguide test -w /var/lib/retroiptvguide`
- Confirm the unit points to `/opt/retroiptvguide` and the dedicated account:
  `sudo systemctl cat retroiptvguide`
- The unit uses `ProtectSystem=strict`; only the state and runtime directories are
  writable. Upload and generated-cache paths are symlinked into the state directory
  during installation, so they remain writable without a systemd mount namespace.

## Safe uninstall vs explicit purge

### Safe uninstall

```bash
sudo /opt/retroiptvguide/retroiptv_linux.sh uninstall --yes
```

Safe uninstall removes:

- `retroiptvguide.service`
- `/opt/retroiptvguide`
- firewall and SELinux adjustments made by the installer

Safe uninstall retains:

- `/etc/retroiptvguide`
- `/var/lib/retroiptvguide`
- the dedicated `retroiptvguide` account
- any retained legacy `/home/iptv/iptv-server` tree that was not already cleaned up

### Explicit purge

```bash
sudo /opt/retroiptvguide/retroiptv_linux.sh purge --yes
```

Purge additionally removes:

- `/etc/retroiptvguide`
- `/var/lib/retroiptvguide`
- any retained legacy `/home/iptv/iptv-server`
- the dedicated `retroiptvguide` account and group

Purge still leaves the shared legacy `iptv` account alone so sibling projects are not
broken by RetroIPTVGuide removal.

## Coexistence with sibling projects and RetroStation Player

The v4.9.9+ Linux layout is intentionally isolated:

- RetroIPTVGuide no longer installs its code under `/home/iptv`
- RetroIPTVGuide no longer runs as the shared `iptv` account
- The installer only removes `iptv-server.service` when that legacy unit is confirmed
  to belong to RetroIPTVGuide
- The installer does not target RetroStation Player or sibling project directories

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

```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_rpi.sh | sudo bash -s install --agree --yes
```

If the full repository is **not** detected in the current directory the installer will
ask for confirmation before cloning. Pass `--yes` to skip the prompt.

Supported hardware:

- Raspberry Pi 3
- Raspberry Pi 4
- Raspberry Pi 5

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

# Default Login

Username: admin
Password: strongpassword123

Change the password after the first login.

------------------------------------------------------------------------

## 🔐 Admin Password Recovery

If the admin password is lost, it can be reset using the provided script.

### Reset command

```bash
python3 /opt/retroiptvguide/scripts/reset_admin_password.py --db /var/lib/retroiptvguide/users.db
```

### Common permission issue

If you see a database write error, it is likely due to ownership mismatch.

Example:

- Database owned by: `retroiptvguide`
- Current user: another account

Run the script as the dedicated service account:

```bash
sudo -u retroiptvguide python3 /opt/retroiptvguide/scripts/reset_admin_password.py --db /var/lib/retroiptvguide/users.db
```

### Immutable file check (rare)

If the issue persists, check if the file is immutable:

```bash
lsattr /var/lib/retroiptvguide/users.db
```

If an `i` flag is present, remove it:

```bash
sudo chattr -i /var/lib/retroiptvguide/users.db
```

### Result

On success:

- Password is reset
- Admin is required to change password on next login

# Installation Guide

## Prerequisites
- Python 3.10+
- Git
- Systemd-based Linux server

## Steps
```bash
git clone https://github.com/<your-username>/RetroIPTVGuide.git
cd RetroIPTVGuide
chmod +x install.sh
./install.sh
sudo systemctl enable iptv-server.service
sudo systemctl start iptv-server.service
```

## Updating
```bash
git pull origin main
sudo systemctl restart iptv-server.service
```

## License
Licensed under CC BY-NC-SA 4.0. See LICENSE for details.

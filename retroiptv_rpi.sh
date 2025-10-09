#!/bin/bash
# RetroIPTVGuide Raspberry Pi Manager
# Combined Installer / Uninstaller for Pi 3 & 4
# License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International

# --- Banner ---
cat <<'EOF'
░█████████                ░██                        ░██████░█████████  ░██████████░██    ░██   ░██████             ░██       ░██            
░██     ░██               ░██                          ░██  ░██     ░██     ░██    ░██    ░██  ░██   ░██                      ░██            
░██     ░██  ░███████  ░████████ ░██░████  ░███████    ░██  ░██     ░██     ░██    ░██    ░██ ░██        ░██    ░██ ░██ ░████████  ░███████  
░█████████  ░██    ░██    ░██    ░███     ░██    ░██   ░██  ░█████████      ░██    ░██    ░██ ░██  █████ ░██    ░██ ░██░██    ░██ ░██    ░██ 
░██   ░██   ░█████████    ░██    ░██      ░██    ░██   ░██  ░██             ░██     ░██  ░██  ░██     ██ ░██    ░██ ░██░██    ░██ ░█████████ 
░██    ░██  ░██           ░██    ░██      ░██    ░██   ░██  ░██             ░██      ░██░██    ░██  ░███ ░██   ░███ ░██░██   ░███ ░██        
░██     ░██  ░███████      ░████ ░██       ░███████  ░██████░██             ░██       ░███      ░█████░█  ░█████░██ ░██ ░█████░██  ░███████  
                                                                                                                                             
                                                                                                                                             
                                                                                                                                             
EOF
echo "==========================================================================="
echo "                   RetroIPTVGuide  |  Raspberry Pi Edition"
echo "==========================================================================="
echo ""

set -e

APP_DIR="/opt/RetroIPTVGuide"
SERVICE_FILE="/etc/systemd/system/retroiptvguide.service"
CONFIG_FILE="/boot/config.txt"
USER_NAME="${SUDO_USER:-$(whoami)}"

ACTION="$1"
AUTO_YES=false
if [[ "$2" == "--yes" || "$2" == "-y" ]]; then
    AUTO_YES=true
fi

#======================  FUNCTIONS  ======================#

show_usage() {
    echo ""
    echo "Usage:"
    echo "  sudo ./retroiptv_rpi.sh install"
    echo "  sudo ./retroiptv_rpi.sh uninstall [--yes|-y]"
    echo ""
    echo "Examples:"
    echo "  sudo ./retroiptv_rpi.sh install"
    echo "  sudo ./retroiptv_rpi.sh uninstall --yes"
    echo ""
    exit 1
}

#----------------------------------------------------------
install_app() {
    echo ""
    echo "============================================================"
    echo " RetroIPTVGuide Raspberry Pi Installer Agreement "
    echo "============================================================"
    echo ""
    echo "This installer will perform the following actions:"
    echo "  - Detect Raspberry Pi model (3 or 4)"
    echo "  - Install dependencies (Python3, ffmpeg, etc.)"
    echo "  - Clone or update RetroIPTVGuide into /opt/RetroIPTVGuide"
    echo "  - Configure Python virtual environment and systemd service"
    echo "  - Auto-configure GPU acceleration (KMS/Fake KMS)"
    echo "  - Optionally reboot when done"
    echo ""
    echo "By continuing, you agree that:"
    echo "  - This software should ONLY be run on internal networks."
    echo "  - It must NOT be exposed to the public Internet."
    echo "  - You accept all risks; no warranty is provided."
    echo ""

    read -p "Do you agree to these terms? (yes/no): " agreement
    if [ "$agreement" != "yes" ]; then
        echo "Installation aborted by user."
        exit 1
    fi
    echo "Agreement accepted. Continuing..."
    echo ""

    # Detect model
    PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    if echo "$PI_MODEL" | grep -q "Raspberry Pi 4"; then
        PI_TYPE="pi4"
    elif echo "$PI_MODEL" | grep -q "Raspberry Pi 3"; then
        PI_TYPE="pi3"
    else
        PI_TYPE="unknown"
    fi
    echo "Detected board: $PI_MODEL ($PI_TYPE)"
    echo ""

    # Update + deps
    sudo apt update -y && sudo apt full-upgrade -y
    sudo apt install -y git python3 python3-venv python3-pip ffmpeg mesa-utils v4l-utils raspi-config

    # Clone repo
    if [ ! -d "$APP_DIR" ]; then
        echo "Cloning RetroIPTVGuide..."
        sudo git clone https://github.com/thehack904/RetroIPTVGuide.git "$APP_DIR"
    else
        echo "Existing repo found, updating..."
        cd "$APP_DIR" && sudo git pull
    fi

    # Python venv
    cd "$APP_DIR"
    sudo python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt
    else
        pip install Flask
    fi
    deactivate

    # Systemd service
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF2
[Unit]
Description=RetroIPTVGuide Flask Server
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always
Environment=FLASK_RUN_PORT=5000
Environment=FLASK_RUN_HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF2

    sudo systemctl daemon-reload
    sudo systemctl enable retroiptvguide
    sudo systemctl restart retroiptvguide

    # GPU Acceleration
    echo "Configuring GPU acceleration..."
    sudo usermod -aG video "$USER_NAME"

    case "$PI_TYPE" in
        pi3)
            sudo raspi-config nonint do_camera 0
            sudo raspi-config nonint do_gldriver G1
            sudo raspi-config nonint do_memory_split 128
            grep -q "dtoverlay=vc4-fkms-v3d" "$CONFIG_FILE" || echo "dtoverlay=vc4-fkms-v3d" | sudo tee -a "$CONFIG_FILE"
            ;;
        pi4)
            sudo raspi-config nonint do_camera 0
            sudo raspi-config nonint do_gldriver G2
            sudo raspi-config nonint do_memory_split 256
            grep -q "dtoverlay=vc4-kms-v3d" "$CONFIG_FILE" || echo "dtoverlay=vc4-kms-v3d" | sudo tee -a "$CONFIG_FILE"
            ;;
        *)
            sudo raspi-config nonint do_memory_split 128
            ;;
    esac

    # Finish summary
    echo ""
    echo "============================================================"
    echo " Installation Complete "
    echo "============================================================"
    echo "Installation complete!"
    echo "End time: $(date)"
    echo ""
    echo "Access the server in your browser at:"
    echo "  http://$(hostname -I | awk '{print $1}'):5000"
    echo ""
    echo "Default login: admin / strongpassword123"
    echo "NOTE: This is a **BETA build**. Do not expose it directly to the public internet."
    echo ""
    echo "GPU acceleration configured for: $PI_TYPE"
    echo "Service name: retroiptvguide (managed by systemd)"
    echo ""

    read -t 10 -p "Reboot now to apply GPU settings? (Y/n, default Y in 10s): " REBOOT_CHOICE || REBOOT_CHOICE="Y"
    REBOOT_CHOICE=${REBOOT_CHOICE:-Y}
    if [[ "$REBOOT_CHOICE" =~ ^[Yy]$ ]]; then
        echo "Rebooting..."
        sleep 2
        sudo reboot
    else
        echo "Reboot skipped. Run 'sudo reboot' manually later."
    fi
}

#----------------------------------------------------------
uninstall_app() {
    echo ""
    echo "============================================================"
    echo " RetroIPTVGuide Uninstaller for Raspberry Pi "
    echo "============================================================"
    echo ""
    echo "This will stop and disable the service, remove its files and configuration."
    echo ""

    if [ "$AUTO_YES" = false ]; then
        read -p "Proceed with uninstallation? (yes/no): " confirm
        [[ "$confirm" != "yes" ]] && echo "Aborted." && exit 1
    else
        echo "[Auto-mode] Continuing uninstall..."
    fi

    # Stop & disable
    if systemctl list-units --type=service --all | grep -q "retroiptvguide.service"; then
        sudo systemctl stop retroiptvguide 2>/dev/null || true
        sudo systemctl disable retroiptvguide 2>/dev/null || true
        echo "Service stopped and disabled."
    fi

    # Remove service
    [ -f "$SERVICE_FILE" ] && sudo rm -f "$SERVICE_FILE" && sudo systemctl daemon-reload

    # Remove app directory
    if [ -d "$APP_DIR" ]; then
        if [ "$AUTO_YES" = true ]; then
            sudo rm -rf "$APP_DIR"
            echo "Application directory deleted automatically."
        else
            read -p "Delete all files under $APP_DIR? (yes/no): " del
            [[ "$del" == "yes" ]] && sudo rm -rf "$APP_DIR" && echo "Deleted." || echo "Retained."
        fi
    fi

    # Optional logs
    LOG_DIRS=("/var/log/retroiptvguide" "/tmp/retroiptvguide" "$HOME/.cache/retroiptvguide")
    for dir in "${LOG_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            if [ "$AUTO_YES" = true ]; then
                sudo rm -rf "$dir"
                echo "Removed logs: $dir"
            else
                read -p "Delete logs in $dir? (yes/no): " ans
                [[ "$ans" == "yes" ]] && sudo rm -rf "$dir" && echo "Deleted $dir."
            fi
        fi
    done

    echo ""
    echo "============================================================"
    echo " Uninstallation Complete "
    echo "============================================================"
    echo "All RetroIPTVGuide components removed."
    echo "System packages remain installed."
    echo "End time: $(date)"
    echo ""
}

#======================  MAIN  ======================#

if [[ -z "$ACTION" ]]; then
    show_usage
fi

case "$ACTION" in
    install)
        install_app
        ;;
    uninstall)
        uninstall_app
        ;;
    *)
        show_usage
        ;;
esac

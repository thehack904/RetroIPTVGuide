VERSION="3.4.0-testing"
#!/usr/bin/env bash
# RetroIPTVGuide uninstall script
# Run with sudo on Linux; run from Administrator shell on Windows


set -e

SERVICE_NAME="iptv-server"
USER_NAME="iptv"
APP_DIR_LINUX="/home/$USER_NAME/iptv-server"
LOG_DIR_LINUX="/var/log/iptv"
SYSTEMD_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# --- Detect Environment ---
if grep -qi microsoft /proc/version 2>/dev/null; then
    ENVIRONMENT="WSL"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    ENVIRONMENT="GITBASH"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ENVIRONMENT="LINUX"
else
    ENVIRONMENT="UNKNOWN"
fi

echo "Detected environment: $ENVIRONMENT"

# --- Privilege Check ---
if [[ "$ENVIRONMENT" == "LINUX" || "$ENVIRONMENT" == "WSL" ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "ERROR: This script must be run as root."
        echo "Try again with: sudo ./uninstall.sh"
        exit 1
    fi
elif [[ "$ENVIRONMENT" == "GITBASH" ]]; then
    # Git Bash doesnâ€™t expose EUID reliably, just warn the user
    echo "NOTE: On Windows, ensure Git Bash is running with Administrator privileges."
fi

# --- Linux/WSL uninstall path ---
if [[ "$ENVIRONMENT" == "LINUX" || "$ENVIRONMENT" == "WSL" ]]; then
    echo "=== Stopping IPTV service if running..."
    systemctl stop ${SERVICE_NAME}.service 2>/dev/null || true
    systemctl disable ${SERVICE_NAME}.service 2>/dev/null || true

    echo "=== Removing systemd service file..."
    if [ -f "$SYSTEMD_FILE" ]; then
        rm -f "$SYSTEMD_FILE"
        systemctl daemon-reload
        echo "Removed: $SYSTEMD_FILE"
    fi

    echo "=== Deleting IPTV logs..."
    if [ -d "$LOG_DIR_LINUX" ]; then
        rm -rf "$LOG_DIR_LINUX"
        echo "Removed: $LOG_DIR_LINUX"
    fi

    echo "=== Deleting IPTV user..."
    if id "$USER_NAME" &>/dev/null; then
        userdel -r "$USER_NAME"
        echo "Removed user: $USER_NAME"
    fi

# --- Windows (Git Bash) uninstall path ---
elif [[ "$ENVIRONMENT" == "GITBASH" ]]; then
    echo "=== Windows Git Bash uninstall ==="
    APP_DIR_WIN="$(pwd)"

    echo "Stopping any running Flask app..."
    pkill -f "python app.py" 2>/dev/null || true

    echo "Deleting Python virtual environment..."
    if [ -d "$APP_DIR_WIN/venv" ]; then
        rm -rf "$APP_DIR_WIN/venv"
        echo "Removed: $APP_DIR_WIN/venv"
    fi
else
    echo "Unsupported environment: $OSTYPE"
    exit 1
fi

echo "=== Uninstall complete! ==="
echo "NOTE: To fully remove RetroIPTVGuide, you must manually delete the project folder."


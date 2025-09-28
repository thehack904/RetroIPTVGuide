#!/usr/bin/env bash
# install.sh - Installer for RetroIPTVGuide
# Detects environment, creates venv, ensures pip is up-to-date only if needed.

set -e

echo "=== RetroIPTVGuide Installer ==="

# Detect environment
if grep -qi "microsoft" /proc/version 2>/dev/null; then
    ENVIRONMENT="WSL"
elif [ -n "$WINDIR" ] && [ -x "/bin/bash" ] && uname -s | grep -qi "mingw"; then
    ENVIRONMENT="GITBASH"
else
    ENVIRONMENT="LINUX"
fi

echo "Environment detected: $ENVIRONMENT"

# Ensure Python is available
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "Python is not installed. Please install Python 3 and rerun."
    exit 1
fi

# Pick python executable
if command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

# Create virtual environment
if [ "$ENVIRONMENT" = "GITBASH" ]; then
    $PY -m venv venv
    PYTHON_BIN="$PWD/venv/Scripts/python.exe"
else
    $PY -m venv venv
    PYTHON_BIN="$PWD/venv/bin/python"
fi

# Upgrade pip only if needed
CURRENT_PIP=$($PYTHON_BIN -m pip --version | awk '{print $2}')
LATEST_PIP=$(curl -s https://pypi.org/pypi/pip/json | grep -oP '"version":\s*"\K[0-9.]+' | head -1)

if [ "$CURRENT_PIP" != "$LATEST_PIP" ] && [ -n "$LATEST_PIP" ]; then
    echo "Upgrading pip from $CURRENT_PIP to $LATEST_PIP..."
    $PYTHON_BIN -m pip install --upgrade pip
else
    echo "pip is already up-to-date ($CURRENT_PIP)"
fi

# Install requirements
$PYTHON_BIN -m pip install -r requirements.txt

echo "=== Installation complete. Activate venv with ==="
if [ "$ENVIRONMENT" = "GITBASH" ]; then
    echo "source venv/Scripts/activate"
else
    echo "source venv/bin/activate"
fi

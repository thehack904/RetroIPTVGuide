<# 
RetroIPTVGuide Windows Installer/Uninstaller
Filename: retroiptv_windows.ps1
Version: 4.3.0

License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
https://creativecommons.org/licenses/by-nc-sa/4.0/

Usage:
  .\retroiptv_windows.ps1 install   [--yes|-y] [--agree|-a]
  .\retroiptv_windows.ps1 uninstall [--yes|-y]

This script:
 - Auto-installs Chocolatey (if missing), then Python, Git, NSSM
 - Creates a Python venv and installs requirements.txt
 - Registers and starts a Windows service via NSSM named "RetroIPTVGuide"
 - Verifies service status and checks the web UI on http://127.0.0.1:5000
 - Uninstall mode stops/deletes the service and cleans local files (with confirmation)

#>

param(
  [Parameter(Mandatory=$false)]
  [ValidateSet('install','uninstall')]
  [string] $Action,

  [switch] $yes,
  [switch] $y,
  [switch] $agree,
  [switch] $a
)

# --- Elevation check with confirmation ---
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host ""
    Write-Host "[ELEVATION] This installer needs administrator rights to continue." -ForegroundColor Yellow
    $resp = Read-Host "Do you want to relaunch as Administrator? (yes/no)"
    if ($resp -match '^(y|yes)$') {
        Write-Host "?? Relaunching with elevated privileges..."
        Start-Process -FilePath "powershell.exe" `
            -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
            -Verb RunAs
        exit
    } else {
        Write-Host "? Operation cancelled Ñ administrator rights required." -ForegroundColor Red
        exit 1
    }
}



# -------------------------------
# Globals & Paths
# -------------------------------
$ErrorActionPreference = 'Stop'
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

$VERSION = "4.3.0"
$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Timestamp = (Get-Date -Format "yyyy-MM-dd_HH-mm-ss")
$logFile = Join-Path $ScriptDir ("install_{0}.log" -f $Timestamp)

$ServiceName = "RetroIPTVGuide"
$Port = 5000
$Url = "http://127.0.0.1:$Port"
$VenvDir = Join-Path $ScriptDir "venv"
$VenvPy  = Join-Path $VenvDir "Scripts\python.exe"
$NssmExe = "nssm.exe"   # rely on PATH from Chocolatey

# -------------------------------
# Helpers (colored output)
# -------------------------------
function Write-Title($text)    { Write-Host $text -ForegroundColor Cyan }
function Write-Info($text)     { Write-Host $text -ForegroundColor White }
function Write-Warn($text)     { Write-Host $text -ForegroundColor Yellow }
function Write-ErrorMsg($text) { Write-Host $text -ForegroundColor Red }
function Write-Ok($text)       { Write-Host $text -ForegroundColor Green }

function Confirm-YesNo($Prompt) {
  if ($yes -or $y) { return $true }
  $resp = Read-Host "$Prompt (yes/no)"
  return ($resp -eq 'yes')
}

function Add-Log($text) {
  Write-Host $text
}


# -------------------------------
# Environment guard (Windows only)
# -------------------------------
if (-not $env:OS -or $env:OS -notmatch 'Windows_NT') {
  Write-ErrorMsg "Unsupported environment. Please run this on Windows PowerShell."
  exit 1
}

# -------------------------------
# Start transcript & Banner
# -------------------------------
try { Start-Transcript -Path $logFile -Append | Out-Null } catch {}

""
$banner = @"
¦¦¦¦¦¦¦¦¦¦                ¦¦¦                        ¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦¦¦¦¦¦    ¦¦¦   ¦¦¦¦¦¦¦             ¦¦¦       ¦¦¦            
¦¦¦     ¦¦¦               ¦¦¦                          ¦¦¦  ¦¦¦     ¦¦¦     ¦¦¦    ¦¦¦    ¦¦¦  ¦¦¦   ¦¦¦                      ¦¦¦            
¦¦¦     ¦¦¦  ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦ ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦    ¦¦¦  ¦¦¦     ¦¦¦     ¦¦¦    ¦¦¦    ¦¦¦ ¦¦¦        ¦¦¦    ¦¦¦ ¦¦¦ ¦¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦  
¦¦¦¦¦¦¦¦¦¦  ¦¦¦    ¦¦¦    ¦¦¦    ¦¦¦¦     ¦¦¦    ¦¦¦   ¦¦¦  ¦¦¦¦¦¦¦¦¦¦      ¦¦¦    ¦¦¦    ¦¦¦ ¦¦¦  ¦¦¦¦¦ ¦¦¦    ¦¦¦ ¦¦¦¦¦¦    ¦¦¦ ¦¦¦    ¦¦¦ 
¦¦¦   ¦¦¦   ¦¦¦¦¦¦¦¦¦¦    ¦¦¦    ¦¦¦      ¦¦¦    ¦¦¦   ¦¦¦  ¦¦¦             ¦¦¦     ¦¦¦  ¦¦¦  ¦¦¦     ¦¦ ¦¦¦    ¦¦¦ ¦¦¦¦¦¦    ¦¦¦ ¦¦¦¦¦¦¦¦¦¦ 
¦¦¦    ¦¦¦  ¦¦¦           ¦¦¦    ¦¦¦      ¦¦¦    ¦¦¦   ¦¦¦  ¦¦¦             ¦¦¦      ¦¦¦¦¦¦    ¦¦¦  ¦¦¦¦ ¦¦¦   ¦¦¦¦ ¦¦¦¦¦¦   ¦¦¦¦ ¦¦¦        
¦¦¦     ¦¦¦  ¦¦¦¦¦¦¦¦      ¦¦¦¦¦ ¦¦¦       ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦¦             ¦¦¦       ¦¦¦¦      ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦ ¦¦¦ ¦¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦  
"@

try {
    # Set console width/height (character columns x lines)
    $cols = 145
    $lines = 45
    mode con: cols=$cols lines=$lines | Out-Null

    Start-Sleep -Milliseconds 200

    # Move/resize only if running under classic PowerShell console
    $hwnd = (Get-Process -Id $PID).MainWindowHandle
    if ($hwnd -ne 0) {
        Add-Type @"
        using System;
        using System.Runtime.InteropServices;
        public static class Win32 {
            [DllImport("user32.dll")]
            public static extern bool MoveWindow(IntPtr hwnd, int x, int y, int width, int height, bool repaint);
        }
"@
    }
} catch {
    Write-Host "[WARN] Could not resize PowerShell window: $($_.Exception.Message)" -ForegroundColor Yellow
}


Write-Host $banner -ForegroundColor Cyan
Write-Title "==========================================================================="
Write-Title "                 RetroIPTVGuide  |  Windows Edition (Headless)"
Write-Title "==========================================================================="
Write-Info ""
Write-Info "=== RetroIPTVGuide Unified Script (v$VERSION) ==="
Write-Info ("Start time: {0}" -f (Get-Date))
Write-Info ("Log file: {0}" -f $logFile)
Write-Info ""

# -------------------------------
# Agreement text (shared style)
# -------------------------------
$needAgree = -not ($agree -or $a)
$AgreementText = @"
============================================================
 RetroIPTVGuide Installer Agreement
============================================================

This installer will perform the following actions:
  - Verify and install dependencies (Chocolatey, Python, Git, NSSM)
  - Create and configure a Python virtual environment
  - Upgrade pip and install requirements
  - Register and start the RetroIPTVGuide Windows service (NSSM)

By continuing, you acknowledge and agree that:
  - This software should ONLY be run on internal networks.
  - It must NOT be exposed to the public Internet.
  - You accept all risks; the author provides NO WARRANTY.
  - The author is NOT responsible for any damage, data loss,
    or security vulnerabilities created by this installation.

"@

# -------------------------------
# Dependency helpers
# -------------------------------
function Ensure-Choco {
  Write-Info "Checking for Chocolatey..."
  if (-not (Get-Command choco.exe -ErrorAction SilentlyContinue)) {
    Write-Warn "Chocolatey not found. Installing..."
    # Allow TLS 1.2
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Set-ExecutionPolicy Bypass -Scope Process -Force
    try {
      Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
      Write-Ok "Chocolatey installed."
    } catch {
      Write-ErrorMsg "Failed to install Chocolatey. $_"
      throw
    }
  } else {
    Write-Ok "Chocolatey already installed."
  }
}

function Ensure-ChocoPkg($pkgName) {
  if (-not (choco list --local-only | Select-String -Quiet ("^{0} " -f [regex]::Escape($pkgName)))) {
    Write-Info "Installing $pkgName via Chocolatey..."
    choco install $pkgName -y | Out-Null
    Write-Ok "$pkgName installed."
  } else {
    Write-Ok "$pkgName already installed."
  }
}

function Resolve-Python {
  # Prefer the Python launcher if available
  $py = Get-Command py.exe -ErrorAction SilentlyContinue
  if ($py) { return "py.exe" }

  $python = Get-Command python.exe -ErrorAction SilentlyContinue
  if ($python) { return "python.exe" }

  return $null
}

function New-Venv {
  param([string] $VenvPath)

  if (Test-Path $VenvPy) {
    Write-Ok "Existing virtual environment detected."
    return
  }

  $pyCmd = Resolve-Python
  if (-not $pyCmd) {
    Write-ErrorMsg "Python not found in PATH even after install."
    throw "PythonNotFound"
  }

  Write-Info "Setting up Python virtual environment..."
  if ($pyCmd -eq "py.exe") {
    & $pyCmd -3 -m venv $VenvPath
  } else {
    & $pyCmd -m venv $VenvPath
  }
  Write-Ok "Virtual environment created at $VenvPath"
}

function Upgrade-PipAndInstallReqs {
  if (-not (Test-Path $VenvPy)) {
    Write-ErrorMsg "Virtual environment Python not found: $VenvPy"
    throw "VenvMissing"
  }
  Write-Info "Upgrading pip..."
  & $VenvPy -m pip install --upgrade pip
  Write-Info "Installing requirements..."
  $req = Join-Path $ScriptDir "requirements.txt"
  if (-not (Test-Path $req)) {
    Write-Warn "requirements.txt not found in $ScriptDir; skipping package install."
  } else {
    & $VenvPy -m pip install -r $req
  }
  Write-Ok "Python dependencies installed."
}

# -------------------------------
# NSSM service helpers
# -------------------------------
function Ensure-Service {
  param([string] $Name)

  # Install NSSM if missing
  Ensure-ChocoPkg "nssm"

  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if ($svc) {
    Write-Warn "Service '$Name' already exists. It will be updated to use the current directory."
    # stop first
    try { Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue } catch {}
    # reconfigure below
  } else {
    Write-Info "Creating Windows service '$Name' (NSSM)..."
    & $NssmExe install $Name $VenvPy "app.py"
  }

  # Configure AppDirectory / stdout / stderr / start type
  & $NssmExe set $Name AppDirectory $ScriptDir | Out-Null
  & $NssmExe set $Name Start SERVICE_AUTO_START | Out-Null

  $logDir = Join-Path $ScriptDir "logs"
  if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
  & $NssmExe set $Name AppStdout (Join-Path $logDir "service_stdout.log") | Out-Null
  & $NssmExe set $Name AppStderr (Join-Path $logDir "service_stderr.log") | Out-Null
  & $NssmExe set $Name AppStopMethodConsole 1500 | Out-Null
  & $NssmExe set $Name AppKillProcessTree 1   | Out-Null

  Write-Ok "Service '$Name' configured."
  Write-Info "Starting service..."
  & $NssmExe start $Name | Out-Null
  Start-Sleep -Seconds 1
  Write-Ok "Service start issued."
}

function Remove-ServiceSafe {
  param([string] $Name)
  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if ($svc) {
    Write-Info "Stopping service '$Name'..."
    try { & $NssmExe stop $Name | Out-Null } catch {}
    Start-Sleep -Seconds 1
    Write-Info "Removing service '$Name'..."
    try { & $NssmExe remove $Name confirm | Out-Null } catch {}
    Write-Ok "Service '$Name' removed."
  } else {
    Write-Warn "Service '$Name' not found. Skipping."
  }
}

# -------------------------------
# HTTP verification (mirrors Linux)
# -------------------------------
function Verify-ServiceAndHttp {
    param(
        [int]$MaxWaitSeconds = 60,
        [int]$PollIntervalSeconds = 2
    )

    Write-Info ""
    Write-Info "Verifying service status..."
    Start-Sleep -Seconds 2

    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc -or $svc.Status -ne 'Running') {
        Write-ErrorMsg "- Service not active. Run: Get-Service -Name $ServiceName | Format-List *"
        return
    }

    Write-Ok "- Service is active."
    Write-Info "Waiting for TCP port $Port to accept connections..."

    $end = (Get-Date).AddSeconds($MaxWaitSeconds)
    $tcpConnected = $false

    while ((Get-Date) -lt $end) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $ar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
            if ($ar.AsyncWaitHandle.WaitOne(1500, $false)) {
                $client.EndConnect($ar)
                $client.Close()
                $tcpConnected = $true
                Write-Ok "- TCP port $Port is accepting connections."
                break
            }
            $client.Close()
        } catch { }
        Start-Sleep -Seconds $PollIntervalSeconds
    }

    if (-not $tcpConnected) {
        Write-Warn "--  Port $Port did not open within $MaxWaitSeconds s."
        return
    }

    # optional lightweight HTTP confirmation
    Write-Info "Confirming HTTP response..."
    try {
        $req = [Net.WebRequest]::Create("http://127.0.0.1:$Port/")
        $req.Timeout = 3000
        $resp = $req.GetResponse()
        Write-Ok "- HTTP responded: $($resp.StatusDescription)"
        $resp.Close()
        Add-Log "- HTTP verified on port $Port"
    } catch {
        Write-Warn "--  TCP open but HTTP verification failed likely still initializing Flask."
        Add-Log "--  TCP open but HTTP verification failed."
    }
}


# -------------------------------
# INSTALL
# -------------------------------
function Do-Install {
  # Agreement
  Write-Info $AgreementText
  if ($needAgree) {
    if (-not (Confirm-YesNo "Do you agree to these terms?")) {
      Write-Warn "Installation aborted by user."
      exit 1
    }
  } else {
    Write-Info "License auto-accepted via --agree."
  }

  # Dependencies
  Ensure-Choco
  Ensure-ChocoPkg "python"
  Ensure-ChocoPkg "git"
  Ensure-ChocoPkg "nssm"

  # Python & venv
  New-Venv -VenvPath $VenvDir
  Upgrade-PipAndInstallReqs

  # Service
  Ensure-Service -Name $ServiceName

  # Verify & Summary
  Verify-ServiceAndHttp

  Write-Title ""
  Write-Title "============================================================"
  Write-Title " Installation Complete"
  Write-Title "============================================================"
  Write-Info  ("End time: {0}" -f (Get-Date))
  Write-Info  ("Access in browser: http://{0}:{1}" -f $env:COMPUTERNAME, $Port)
  Write-Info  ("Default login: admin / strongpassword123")
  Write-Info  ("Log file: {0}" -f $logFile)
  Write-Title "============================================================"
}

# -------------------------------
# UNINSTALL
# -------------------------------
function Do-Uninstall {
    Write-Host ""
    Write-Title "============================================================"
    Write-Title " RetroIPTVGuide Uninstaller"
    Write-Title "============================================================"
    Write-Info  ("Start time: {0}" -f (Get-Date))
    Write-Host ""

    if (-not ($yes -or $y)) {
        if (-not (Confirm-YesNo "Proceed with uninstall of RetroIPTVGuide service and local environment?")) {
            Write-Warn "Uninstall aborted by user."
            Write-Host ""
            Write-Host "Press ENTER to close this window..." -ForegroundColor Yellow
            Read-Host
            exit 1
        }
    } else {
        Write-Info "Auto-confirmed via --yes."
    }

	# Make sure nssm is callable, quietly
	try {
		if (-not (Get-Command nssm.exe -ErrorAction SilentlyContinue)) {
			choco install nssm -y | Out-Null
		}
	} catch {}
	Remove-ServiceSafe -Name $ServiceName


    # Remove venv & optional artifacts
    if (Test-Path $VenvDir) {
        Write-Info "Removing virtual environment ($VenvDir)..."
        try { Remove-Item -Recurse -Force $VenvDir } catch {}
    }

    # Optionally offer to clean logs
    $logsDir = Join-Path $ScriptDir "logs"
    if ((Test-Path $logsDir) -and -not ($yes -or $y)) {
        if (Confirm-YesNo "Remove log files in '$logsDir'?") {
            try { Remove-Item -Recurse -Force $logsDir } catch {}
            Write-Ok "Logs removed."
        }
    }

    Write-Host ""
    Write-Title "============================================================"
    Write-Title " Uninstallation Complete"
    Write-Title "============================================================"
    Write-Ok    "All requested components removed."
    Write-Info  ("End time: {0}" -f (Get-Date))
    Write-Title "============================================================"
    Write-Host ""
    Write-Host "RetroIPTVGuide has been successfully removed from this system." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press ENTER to close this window..." -ForegroundColor Yellow
    Read-Host
}


if (-not $Action) {
    Write-Host ""
    Write-Host "RetroIPTVGuide Windows Installer Menu" -ForegroundColor Cyan
    Write-Host "==========================================================="
    Write-Host "[1] Install RetroIPTVGuide"
    Write-Host "[2] Uninstall RetroIPTVGuide"
    Write-Host "[3] Exit"
    Write-Host "==========================================================="
    $choice = Read-Host "Select an option (1-3)"
    switch ($choice) {
        '1' { $Action = 'install' }
        '2' { $Action = 'uninstall' }
        '3' { Write-Host "Exiting..." ; exit }
        default { Write-Host "Invalid selection." ; exit }
    }
}


# -------------------------------
# Dispatch
# -------------------------------
try {
    switch ($Action) {
        'install'   { Do-Install }
        'uninstall' { Do-Uninstall }
    }
} catch {
    Write-ErrorMsg "- An error occurred: $($_.Exception.Message)"
    exit 1
} finally {
    try {
        Stop-Transcript | Out-Null
        Start-Sleep -Milliseconds 200
    } catch {}

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "RetroIPTVGuide process complete." -ForegroundColor Green
    Write-Host "You may review the log above or press ENTER to close this window." -ForegroundColor Yellow
    Write-Host "============================================================"
    Read-Host
}
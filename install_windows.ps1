<#  install_windows.ps1
    Windows bootstrap for RetroIPTVGuide
    - Prefer WSL if installed
    - Else fallback to Git Bash
    - Check/install Git + Python if missing
    - Force Git Bash to cd into script root before cloning
    - All output logged to file
#>

$LogDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
$TimeStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "install_$TimeStamp.log"

Start-Transcript -Path $LogFile -Force

# Elevation check
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Host "Re-launching with Administrator privileges..." -ForegroundColor Yellow
    Stop-Transcript
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "=== RetroIPTVGuide Windows Installer Bootstrap ===" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date)"
Write-Host "Log file: $LogFile"
Write-Host "OS: $([System.Environment]::OSVersion.VersionString)"

# Elevation check
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $IsAdmin) {
  Write-Host "Re-launching with Administrator privileges..." -ForegroundColor Yellow
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}
# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path $pythonExe -Parent   # <-- this gives Scripts
$pythonRoot = Split-Path $pythonDir -Parent  # <-- this gives Python312 folder
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonRoot"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
  Stop-Transcript
  Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
  exit
}

function CmdExists($name) { Get-Command $name -ErrorAction SilentlyContinue | Out-Null }

# Step 1: Prefer WSL
$HasWslExe = CmdExists "wsl.exe"
if ($HasWslExe) {
  $distros = & wsl.exe -l -q 2>$null
  if ($LASTEXITCODE -eq 0 -and $distros -and $distros.Trim().Length -gt 0) {
    Write-Host "WSL distribution detected. Installing inside WSL..." -ForegroundColor Cyan
    wsl.exe -- bash -lc "git clone -b windows https://github.com/thehack904/RetroIPTVGuide.git && cd RetroIPTVGuide && chmod +x install.sh && ./install.sh"
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}
# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path (Split-Path $pythonExe -Parent) -Parent  # parent folder of Scripts
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonDir"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
    Stop-Transcript
    exit $LASTEXITCODE
  } else {
    Write-Host "WSL present but no Linux distro installed." -ForegroundColor Yellow
    try {
      wsl.exe --install -d Ubuntu
      Write-Host "Ubuntu installation initiated. Please reboot when prompted, then re-run this script." -ForegroundColor Green
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}
# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path (Split-Path $pythonExe -Parent) -Parent  # parent folder of Scripts
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonDir"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
      Stop-Transcript
      exit 0
    } catch {
      Write-Warning "Automatic WSL install failed. Install WSL manually, then rerun."
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}
# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path (Split-Path $pythonExe -Parent) -Parent  # parent folder of Scripts
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonDir"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
      Stop-Transcript
      exit 1
    }
  }
}

# Step 2: Fallback to Git Bash
Write-Host "WSL not available. Falling back to Git Bash..." -ForegroundColor Yellow
$GitBashPath = "$Env:ProgramFiles\Git\bin\bash.exe"
if (-not (Test-Path $GitBashPath)) { $GitBashPath = "$Env:ProgramFiles(x86)\Git\bin\bash.exe" }

if (-not (Test-Path $GitBashPath)) {
  Write-Host "Git for Windows not found. Attempting to install..." -ForegroundColor Yellow

  if (CmdExists "winget") {
    winget install -e --id Git.Git --silent
  } elseif (CmdExists "choco") {
    choco install git -y
  } else {
    # Fallback: direct download + silent install
    try {
      $Installer = "$env:TEMP\GitInstaller.exe"
      Write-Host "Downloading Git for Windows installer..." -ForegroundColor Cyan
      Invoke-WebRequest -Uri "https://github.com/git-for-windows/git/releases/download/v2.47.0.windows.1/Git-2.47.0-64-bit.exe" -OutFile $Installer
      Write-Host "Running Git installer silently..." -ForegroundColor Cyan
      Start-Process -FilePath $Installer -ArgumentList "/VERYSILENT","/NORESTART" -Wait
    } catch {
      Write-Error "Automatic Git install failed. Please install Git manually: https://git-scm.com/download/win"
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}
# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path (Split-Path $pythonExe -Parent) -Parent  # parent folder of Scripts
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonDir"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
      Stop-Transcript
      exit 1
    }
  }

  # Re-check after install
  $GitBashPath = "$Env:ProgramFiles\Git\bin\bash.exe"
  if (-not (Test-Path $GitBashPath)) { $GitBashPath = "$Env:ProgramFiles(x86)\Git\bin\bash.exe" }
  if (-not (Test-Path $GitBashPath)) {
    Write-Error "Git Bash still not found after install attempt."
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}
# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path (Split-Path $pythonExe -Parent) -Parent  # parent folder of Scripts
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonDir"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
    Stop-Transcript
    exit 1
  }
}

# Step 3: Ensure Python exists
function PythonExists {
  (CmdExists "python") -or (CmdExists "py") -or (CmdExists "python3")
}

if (-not (PythonExists)) {
  Write-Host "Python not found. Attempting to install..." -ForegroundColor Yellow
  if (CmdExists "winget") {
    winget install -e --id Python.Python.3.12
  } elseif (CmdExists "choco") {
    choco install python -y
  } else {
    try {
      $PyInstaller = "$env:TEMP\PythonInstaller.exe"
      Write-Host "Downloading Python installer..." -ForegroundColor Cyan
      Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe" -OutFile $PyInstaller
      Write-Host "Running Python installer silently..." -ForegroundColor Cyan
      Start-Process -FilePath $PyInstaller -ArgumentList "/quiet","InstallAllUsers=1","PrependPath=1","Include_test=0" -Wait
    } catch {
      Write-Error "Python install failed. Please install manually: https://www.python.org/downloads/"
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}
# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path (Split-Path $pythonExe -Parent) -Parent  # parent folder of Scripts
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonDir"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
      Stop-Transcript
      exit 1
    }
  }
}

# Step 4: Run RetroIPTVGuide installer under Git Bash (force cd into script root)
Write-Host "Running installer under Git Bash..." -ForegroundColor Cyan
& "$GitBashPath" -lc "cd '$PSScriptRoot' && git clone -b windows https://github.com/thehack904/RetroIPTVGuide.git && cd RetroIPTVGuide && chmod +x install.sh && ./install.sh"
# --- PATCH BLOCK 1: Activation instructions ---
if ($env:ComSpec -like "*cmd.exe") {
    $activation = ".\venv\Scripts\activate.bat"
} elseif ($PSVersionTable.PSEdition -eq "Core" -or $host.Name -like "*PowerShell*") {
    $activation = ".\venv\Scripts\Activate.ps1"
} else {
    $activation = "source venv/Scripts/activate"
}
Write-Host "=== Installation complete. Activate venv with ===" -ForegroundColor Green
Write-Host $activation -ForegroundColor Cyan

# --- PATCH BLOCK 2: NSSM service setup ---
$nssmPath = "C:\nssm\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    try {
        Write-Host "Downloading nssm..." -ForegroundColor Yellow
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
        Expand-Archive $nssmZip -DestinationPath "C:\nssm" -Force
        $nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"
    } catch {
        Write-Warning "Failed to download/extract nssm automatically. Install from https://nssm.cc/ and rerun service setup."
        $nssmPath = $null
    }
}

if ($nssmPath -and (Test-Path $nssmPath)) {
    $TargetDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
    $pythonExe = Join-Path $TargetDir "venv\Scripts\python.exe"
    $appPath = Join-Path $TargetDir "app.py"

    Write-Host "Setting up RetroIPTVGuide Windows Service..." -ForegroundColor Yellow
    & $nssmPath install RetroIPTVGuide $pythonExe $appPath
    & $nssmPath set RetroIPTVGuide Start SERVICE_AUTO_START
    & $nssmPath start RetroIPTVGuide
    Write-Host "RetroIPTVGuide service installed and started." -ForegroundColor Green
} else {
    Write-Warning "NSSM not available. Skipping service setup."
}

# --- PATCH: Open firewall port for RetroIPTVGuide ---
Write-Host "Opening Windows Firewall port 5000 for RetroIPTVGuide..." -ForegroundColor Yellow
netsh advfirewall firewall add rule name="RetroIPTVGuide" dir=in action=allow protocol=TCP localport=5000 | Out-Null

# --- END PATCH ---
# --- PATCH: Record Python version and path ---
$pythonExe = (Get-Command python.exe).Source
$pythonDir = Split-Path (Split-Path $pythonExe -Parent) -Parent  # parent folder of Scripts
$pythonVer = (& $pythonExe --version).Split()[1]

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$verFile = Join-Path $logDir "python_version.txt"

"Version=$pythonVer" | Out-File $verFile -Encoding ascii
"Path=$pythonDir"   | Out-File $verFile -Encoding ascii -Append
# --- END PATCH ---
Stop-Transcript
Write-Host "Press any key to exit..." -ForegroundColor Cyan
Pause

exit $LASTEXITCODE
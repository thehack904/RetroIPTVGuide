<# 
RetroIPTVGuide Windows Installer
Clean version with only prerequisite checks and service setup
#>

# === Start Transcript ===
$logDir = "$PSScriptRoot\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$logFile = Join-Path $logDir ("install_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
Start-Transcript -Path $logFile -Append
Write-Host "=== RetroIPTVGuide Windows Installer ===" -ForegroundColor Cyan
Write-Host "Log file: $logFile" -ForegroundColor Gray

# --- Ensure Admin Privileges ---
# Elevation check
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Host "Re-launching with Administrator privileges..." -ForegroundColor Yellow
    Stop-Transcript
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host " RetroIPTVGuide Installer Agreement " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "This installer will perform the following actions:" -ForegroundColor White
Write-Output "  - Bootstraps / Installs Chocolatey"
Write-Output "  - Installs dependencies: python, git, nssm"
Write-Output "  - Registers Windows App Paths for python/python3"
Write-Output "  - Adds Python to Git Bash (~/.bashrc)"
Write-Output "  - Clones RetroIPTVGuide into the same folder as the installer"
Write-Output "  - Runs install.sh via Git Bash"
Write-Output "  - Creates an NSSM service to run venv\\Scripts\\python.exe app.py"
Write-Output "  - Open Windows Firewall port 5000 for RetroIPTVGuide Service"
Write-Output "  - Starts the RetroIPTVGuide service"
Write-Host ""
Write-Host "By continuing, you acknowledge and agree that:" -ForegroundColor White
Write-Output "  - This software should ONLY be run on internal networks."
Write-Output "  - It must NOT be exposed to the public Internet."
Write-Output "  - You accept all risks; the author provides NO WARRANTY."
Write-Output "  - The author is NOT responsible for any damage, data loss,"
Write-Output "    or security vulnerabilities created by this installation."
Write-Host ""
Write-Host "Do you agree to these terms? (yes/no)" -ForegroundColor Yellow

$agreement = Read-Host "Type yes or no"
Write-Output "User response to agreement: $agreement"

if ($agreement.ToLower() -ne "yes") {
    Write-Host "Installation aborted by user." -ForegroundColor Red
    Stop-Transcript
    exit 1
}

# --- Chocolatey ---
Write-Host "Checking for Chocolatey..." -ForegroundColor Cyan
$choco = Get-Command choco -ErrorAction SilentlyContinue
if (-not $choco) {
    Write-Host "Installing Chocolatey..." -ForegroundColor Yellow
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine")
}

# --- Python ---
Write-Host "Checking for Python..." -ForegroundColor Cyan
if (choco list | Select-String -Pattern "^python3 ") {
    Write-Host "Python3 is installed"
} else {
    Write-Host "Python3 not found, installing..."
    choco install python3 -y
}

# --- Fix Python alias stubs from Microsoft Store ---
$aliases = @(
  "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe",
  "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.exe",
  "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.*.exe"
)

foreach ($alias in $aliases) {
    if (Test-Path $alias) {
        try {
            Remove-Item $alias -Force
            Write-Host "Removed Microsoft Store alias: $alias" -ForegroundColor Yellow
        } catch {
            Write-Warning "Failed to remove alias ${alias}: $_"
        }
    }
}

# --- Ensure Chocolatey shims directory comes first in PATH ---
$chocoBin = "C:\ProgramData\chocolatey\bin"
$currentPath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")

if (-not ($currentPath -split ";" | ForEach-Object { $_.Trim() } | Where-Object { $_ -eq $chocoBin })) {
    $newPath = "$chocoBin;$currentPath"
    [System.Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")
    Write-Host "Updated PATH to prioritize Chocolatey bin: $chocoBin" -ForegroundColor Green
} else {
    Write-Host "Chocolatey bin already in PATH." -ForegroundColor Green
}

# --- Add registry App Paths aliases for python/python3 ---
try {
    $pythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) {
        $pythonExe = "C:\Python313\python.exe"  # fallback if not resolved via PATH
    }

    if (Test-Path $pythonExe) {
        New-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python.exe" -Force | Out-Null
        Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python.exe" -Name "(Default)" -Value $pythonExe

        New-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python3.exe" -Force | Out-Null
        Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python3.exe" -Name "(Default)" -Value $pythonExe

        Write-Host "Registered App Path aliases: python, python3 -> $pythonExe" -ForegroundColor Green
    } else {
        Write-Warning "Python executable not found for alias registration."
    }
} catch {
    Write-Warning "Failed to register python/python3 aliases in App Paths: $_"
}


# --- Ensure Chocolatey is installed ---
if (-not (Get-Command choco.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..." -ForegroundColor Cyan
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
} else {
    Write-Host "Chocolatey already installed." -ForegroundColor Green
}

# --- Ensure dependencies ---
$packages = @("python3", "nssm", "git")

foreach ($pkg in $packages) {
    $installed = choco list --limit-output | Select-String -Pattern "^$pkg "
    if (-not $installed) {
        Write-Host "Installing $pkg..." -ForegroundColor Cyan
        choco install $pkg -y | Out-Null
    } else {
        Write-Host "$pkg already installed." -ForegroundColor Green
    }
}

Write-Host "All dependencies installed." -ForegroundColor Green

# --- Ensure Python aliases point to correct installed version ---
try {
    $pythonExePath = (Get-Command python3.exe -ErrorAction SilentlyContinue).Source
    if (-not $pythonExePath) {
        $pythonExePath = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    }

    if ($pythonExePath) {
        Write-Host "Found Python executable at $pythonExePath" -ForegroundColor Cyan

        # Persist App Path so Windows resolves python/python3 correctly
        $aliases = @("python.exe", "python3.exe")
        foreach ($alias in $aliases) {
            $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\$alias"
            if (-not (Test-Path $regPath)) {
                New-Item -Path $regPath -Force | Out-Null
            }
            Set-ItemProperty -Path $regPath -Name "(Default)" -Value $pythonExePath
            Set-ItemProperty -Path $regPath -Name "Path" -Value (Split-Path $pythonExePath)
        }

        Write-Host "Registered App Path aliases: python, python3 -> $pythonExePath" -ForegroundColor Green
    } else {
        Write-Warning "Python executable not found in PATH. Aliases not created."
    }
} catch {
    Write-Warning "Failed to configure Python aliases: $_"
}

# --- Ensure Python aliases point to correct installed version ---
try {
    # Look up Python installation folder from Chocolatey
    $pythonPkg = choco list | Select-String -Pattern "^python3 "
    if ($pythonPkg) {
        # Most choco python3 installs under C:\Python3xx
        $pythonDir = Get-ChildItem "C:\Python*" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $pythonExePath = Join-Path $pythonDir.FullName "python.exe"

        if (Test-Path $pythonExePath) {
            Write-Host "Found Python executable at $pythonExePath" -ForegroundColor Cyan

            # Persist App Path so Windows resolves python/python3 correctly
            $aliases = @("python.exe", "python3.exe")
            foreach ($alias in $aliases) {
                $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\$alias"
                if (-not (Test-Path $regPath)) {
                    New-Item -Path $regPath -Force | Out-Null
                }
                Set-ItemProperty -Path $regPath -Name "(Default)" -Value $pythonExePath
                Set-ItemProperty -Path $regPath -Name "Path" -Value $pythonDir.FullName
            }

            Write-Host "Registered App Path aliases: python, python3 -> $pythonExePath" -ForegroundColor Green

            # --- Add Python to Git Bash PATH via ~/.bashrc ---
            $gitBashHome = Join-Path $env:USERPROFILE ".bashrc"
            $bashrcLine = "export PATH=""/c/$($pythonDir.Name):/c/$($pythonDir.Name)/Scripts:`$PATH"""

            if (Test-Path $gitBashHome) {
                if (-not (Select-String -Path $gitBashHome -Pattern $pythonDir.Name -Quiet)) {
                    Add-Content -Path $gitBashHome -Value $bashrcLine
                    Write-Host "Added Python to Git Bash PATH in .bashrc" -ForegroundColor Yellow
                }
            } else {
                Set-Content -Path $gitBashHome -Value $bashrcLine
                Write-Host "Created .bashrc and added Python PATH for Git Bash" -ForegroundColor Yellow
            }

        } else {
            Write-Warning "Python executable not found in expected location."
        }
    } else {
        Write-Warning "Python not installed by Chocolatey, skipping alias setup."
    }
} catch {
    Write-Warning "Failed to configure Python aliases: $_"
}





# --- Clone RetroIPTVGuide ---
$installDir = "$PSScriptRoot\RetroIPTVGuide"
if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir }
# Resolve Git path
$gitExe = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
if (-not $gitExe) { $gitExe = "C:\Program Files\Git\bin\git.exe" }
if (-not (Test-Path $gitExe)) { $gitExe = "C:\Program Files (x86)\Git\bin\git.exe" }

if (-not (Test-Path $gitExe)) {
    Write-Error "Git executable not found even after installation. Please verify Git installation."
    exit 1
}

# Clone the repository
#& $gitExe clone -b windows https://github.com/thehack904/RetroIPTVGuide.git $installDir

# --- Run install.sh using Git Bash ---
try {
    $gitBash = "C:\Program Files\Git\bin\bash.exe"
    #$repoDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
	$repoDir = $PSScriptRoot

    if (Test-Path $gitBash -PathType Leaf) {
        if (Test-Path (Join-Path $repoDir "install.sh")) {
            Write-Host "Running install.sh with Git Bash..." -ForegroundColor Cyan
            & "$gitBash" --login -i -c "cd '$repoDir' && chmod +x install.sh && ./install.sh"
        } else {
            Write-Warning "install.sh not found in $repoDir"
        }
    } else {
        Write-Warning "Git Bash not found at $gitBash. Skipping install.sh"
    }
} catch {
    Write-Warning "Failed to run install.sh in Git Bash: $_"
}

# --- PATCH: Open firewall port for RetroIPTVGuide ---
Write-Host "Opening Windows Firewall port 5000 for RetroIPTVGuide..." -ForegroundColor Yellow
netsh advfirewall firewall add rule name="RetroIPTVGuide" dir=in action=allow protocol=TCP localport=5000 | Out-Null

# --- Configure NSSM service for RetroIPTVGuide ---
try {
    $nssm = "C:\ProgramData\chocolatey\bin\nssm.exe"
    #$repoDir = Join-Path $PSScriptRoot "RetroIPTVGuide"
	$repoDir = $PSScriptRoot
    $venvPython = Join-Path $repoDir "venv\Scripts\python.exe"
    $appPy = Join-Path $repoDir "app.py"

    if ((Test-Path $nssm -PathType Leaf) -and (Test-Path $venvPython) -and (Test-Path $appPy)) {
        Write-Host "Setting up NSSM service for RetroIPTVGuide..." -ForegroundColor Cyan

        # Install the service to directly run venv python + app.py
        & $nssm install RetroIPTVGuide $venvPython $appPy

        # Set service parameters
        & $nssm set RetroIPTVGuide Start SERVICE_AUTO_START
        & $nssm set RetroIPTVGuide AppDirectory $repoDir

        Write-Host "NSSM service 'RetroIPTVGuide' installed successfully." -ForegroundColor Green

        # Start the service right away
        Start-Service RetroIPTVGuide
        Write-Host "Service 'RetroIPTVGuide' started." -ForegroundColor Green
    } else {
        Write-Warning "NSSM, venv python, or app.py not found. Could not create service."
    }
} catch {
    Write-Warning "Failed to configure NSSM service: $_"
}

echo ""
Write-Host "Installation complete!" -ForegroundColor Cyan
echo "End time: $(date)"
echo "Access the server in your browser at: http://<your-server-ip>:5000"
echo "Default login: admin / strongpassword123"
echo "NOTE: This is a **BETA build**. Do not expose it directly to the public internet."
echo ""

# === Done ===
Stop-Transcript
pause

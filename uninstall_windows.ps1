$VERSION = "3.3.0"
# RetroIPTVGuide Windows Uninstaller
# ==================================



# Setup logging
$LogDir = "$PSScriptRoot\logs"
if (!(Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = "$LogDir\uninstall_$Timestamp.log"

Start-Transcript -Path $LogFile -Force
Write-Host "=== RetroIPTVGuide Windows Uninstaller ===" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date)" -ForegroundColor Cyan
Write-Host "Log file: $LogFile" -ForegroundColor Cyan

# Elevation check
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Host "Re-launching with Administrator privileges..." -ForegroundColor Yellow
    Stop-Transcript
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

# Stop and remove RetroIPTVGuide service via NSSM
$serviceName = "RetroIPTVGuide"
try {
    if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        Write-Host "Stopping service $serviceName..." -ForegroundColor Yellow
        Stop-Service $serviceName -Force -ErrorAction SilentlyContinue
        Write-Host "Removing service $serviceName..." -ForegroundColor Yellow
        & nssm remove $serviceName confirm
    } else {
        Write-Host "Service $serviceName not found." -ForegroundColor DarkYellow
    }
} catch {
    Write-Warning "Error while removing $serviceName service: $_"
}

# Remove firewall rule
try {
    Write-Host "Removing Windows Firewall port rule for RetroIPTVGuide..." -ForegroundColor Yellow
    netsh advfirewall firewall delete rule name="RetroIPTVGuide"
} catch {
    Write-Warning "Could not remove firewall rule: $_"
}

# Remove RetroIPTVGuide installation folder
#$installDir = "$PSScriptRoot"
#if (Test-Path $installDir) {
#    Write-Host "Removing install directory $installDir..." -ForegroundColor Yellow
#    try {
#        Remove-Item -Recurse -Force $installDir
#        Write-Host "Install directory removed." -ForegroundColor Green
#    } catch {
#        Write-Warning "Could not remove ${installDir}: $_"
#    }
#} else {
#    Write-Host "Install directory not found: $installDir" -ForegroundColor DarkYellow
#}

## Optional cleanup of dependencies installed by Chocolatey
#function Uninstall-ChocoPackage($pkgName) {
#    if (Get-Command choco.exe -ErrorAction SilentlyContinue) {
#        $installed = choco list | Select-String -Pattern "^$pkgName"
#        if ($installed) {
#            Write-Host "Uninstalling $pkgName via Chocolatey..." -ForegroundColor Yellow
#            choco uninstall $pkgName -y | Out-Null
#        } else {
#            Write-Host "$pkgName not found in Chocolatey, skipping." -ForegroundColor DarkYellow
#        }
#    } else {
#        Write-Host "Chocolatey not found, cannot uninstall $pkgName." -ForegroundColor DarkYellow
#    }
#}
#
#Uninstall-ChocoPackage "python"
#Uninstall-ChocoPackage "python3"
#Uninstall-ChocoPackage "nssm"
#Uninstall-ChocoPackage "git"
#Uninstall-ChocoPackage "git.install"

# Improved Chocolatey uninstall function
function Uninstall-ChocoPackagePrefix($pkgPrefix) {
    if (Get-Command choco.exe -ErrorAction SilentlyContinue) {
        $installed = choco list | ForEach-Object { ($_ -split ' ')[0] } | Where-Object { $_ -like "$pkgPrefix*" }
        if ($installed) {
            foreach ($pkg in $installed) {
                Write-Host "Uninstalling $pkg via Chocolatey..." -ForegroundColor Yellow
                choco uninstall $pkg -y | Out-Null
            }
        } else {
            Write-Host "No packages found with prefix '$pkgPrefix', skipping." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "Chocolatey not found, cannot uninstall packages with prefix '$pkgPrefix'." -ForegroundColor DarkYellow
    }
}

# Remove all Python variants + NSSM + Git
Uninstall-ChocoPackagePrefix "python"
Uninstall-ChocoPackagePrefix "nssm"
Uninstall-ChocoPackagePrefix "git"


# --- Remove registry App Paths aliases for python/python3 ---
try {
    if (Test-Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python.exe") {
        Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python.exe" -Recurse -Force
        Write-Host "Removed App Path alias: python.exe" -ForegroundColor Yellow
    }
    if (Test-Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python3.exe") {
        Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\python3.exe" -Recurse -Force
        Write-Host "Removed App Path alias: python3.exe" -ForegroundColor Yellow
    }
} catch {
    Write-Warning "Failed to remove python/python3 App Path aliases: $_"
}

# --- Optionally restore Microsoft Store stubs (App Execution Aliases) ---
$windowsApps = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
$stubTargets = @(
    "python.exe",
    "python3.exe"
)

foreach ($stub in $stubTargets) {
    $stubPath = Join-Path $windowsApps $stub
    if (-not (Test-Path $stubPath)) {
        try {
            # Recreate as a zero-byte placeholder to mimic default behavior
            New-Item -Path $stubPath -ItemType File -Force | Out-Null
            Write-Host "Restored Microsoft Store alias stub: $stubPath" -ForegroundColor Yellow
        } catch {
            Write-Warning "Failed to restore Store alias ${stub}: $_"
        }
    }
}

Write-Host ""
Write-Host "Would you like to completely uninstall ALL remaining Chocolatey packages and Chocolatey itself?" -ForegroundColor Yellow
$fullUninstall = Read-Host "Type yes or no"
Write-Output "User response to full uninstall prompt: $fullUninstall"

if ($fullUninstall.ToLower() -eq "yes") {
    try {
        Write-Host ""
        Write-Host "Proceeding with full removal of all Chocolatey packages..." -ForegroundColor Red

        # Capture installed packages
        $rawInstalled = & choco list 2>$null
        if ($rawInstalled -is [string]) { $rawInstalled = $rawInstalled -split "`r?`n" }

        $installed = $rawInstalled | Where-Object {
            ($_ -notmatch "^Chocolatey v") -and
            ($_ -notmatch "Did you know Pro") -and
            ($_ -notmatch "Features\? Learn more") -and
            ($_ -notmatch "Package Synchronizer") -and
            ($_ -notmatch "packages installed") -and
            ($_ -ne "")
        }

        # Extract package names (first token of each line)
        $pkgNames = $installed | ForEach-Object { ($_ -split " ")[0] }

        if ($pkgNames) {
            foreach ($pkg in $pkgNames) {
                Write-Host "Uninstalling $pkg ..." -ForegroundColor Cyan
                choco uninstall -y $pkg | Out-Null
            }
        }

        # Finally uninstall Chocolatey itself
        Write-Host "Uninstalling Chocolatey..." -ForegroundColor Cyan
        choco uninstall -y chocolatey | Out-Null

        Write-Host "Full Chocolatey removal complete." -ForegroundColor Green
        Write-Output "Full Chocolatey removal complete."
    } catch {
        Write-Warning "Failed to completely remove all Chocolatey packages: $_"
    }
} else {
    Write-Host "Leaving remaining Chocolatey packages and Chocolatey itself installed." -ForegroundColor Cyan
}

Stop-Transcript
Write-Host "=== Uninstallation complete ===" -ForegroundColor Cyan
pause

<# uninstall_windows.ps1
    Complete uninstaller for RetroIPTVGuide
    - Stops and removes Windows Service
    - Removes RetroIPTVGuide repo + venv
    - Removes Git Bash (if installed)
    - Removes Python (if installed)
    - Removes logs after transcript
#>

$LogDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
$TimeStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "uninstall_$TimeStamp.log"

Start-Transcript -Path $LogFile -Force

# Elevation check
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Host "Re-launching with Administrator privileges..." -ForegroundColor Yellow
# --- PATCH: Corrected Python uninstall using version + path file ---
$pythonVerFile = Join-Path $PSScriptRoot "logs\python_version.txt"
if (Test-Path $pythonVerFile) {
    $lines = Get-Content $pythonVerFile
    $pythonVersion = ($lines | Where-Object { $_ -like "Version=*" }) -replace "Version=", ""
    $pythonPath    = ($lines | Where-Object { $_ -like "Path=*" }) -replace "Path=", ""

    Write-Host "Attempting to uninstall Python $pythonVersion from $pythonPath..." -ForegroundColor Yellow

    $uninstaller = Join-Path $pythonPath "uninstall.exe"
    if (Test-Path $uninstaller) {
        & $uninstaller /quiet | Out-Null
        Write-Host "Python $pythonVersion uninstalled successfully." -ForegroundColor Green
    } else {
        Write-Warning "Uninstaller not found at $uninstaller. Trying registry lookup..."
        $uninstallKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        $pythonKey = Get-ChildItem $uninstallKey | Where-Object {
            $_.GetValue("DisplayName") -like "Python $pythonVersion*"
        } | Select-Object -First 1
        if ($pythonKey) {
            $uninstallString = $pythonKey.GetValue("UninstallString", $null)
            if ($uninstallString) {
                Write-Host "Running registry uninstall for Python $pythonVersion..." -ForegroundColor Yellow
                & cmd.exe /c $uninstallString /quiet | Out-Null
                Write-Host "Python $pythonVersion uninstalled successfully." -ForegroundColor Green
            } else {
                Write-Warning "Registry entry found but no uninstall string for Python $pythonVersion."
            }
        } else {
            Write-Warning "No registry entry found for Python $pythonVersion."
        }
    }
} else {
    Write-Host "No python_version.txt found, falling back to existing uninstall logic..." -ForegroundColor Yellow
}
# --- END PATCH ---
# --- PATCH: Corrected Python uninstall with cleanup ---
$pythonVerFile = Join-Path $PSScriptRoot "logs\python_version.txt"
if (Test-Path $pythonVerFile) {
    $lines = Get-Content $pythonVerFile
    $pythonVersion = ($lines | Where-Object { $_ -like "Version=*" }) -replace "Version=", ""
    $pythonPath    = ($lines | Where-Object { $_ -like "Path=*" }) -replace "Path=", ""

    Write-Host "Attempting to uninstall Python $pythonVersion from $pythonPath..." -ForegroundColor Yellow

    $uninstaller = Join-Path $pythonPath "uninstall.exe"
    if (Test-Path $uninstaller) {
        & $uninstaller /quiet | Out-Null
        Write-Host "Python $pythonVersion uninstalled successfully." -ForegroundColor Green
    } else {
        Write-Warning "Uninstaller not found at $uninstaller. Trying registry lookup..."
        $uninstallKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        $pythonKey = Get-ChildItem $uninstallKey | Where-Object {
            $_.GetValue("DisplayName") -like "Python $pythonVersion*"
        } | Select-Object -First 1
        if ($pythonKey) {
            $uninstallString = $pythonKey.GetValue("UninstallString", $null)
            if ($uninstallString) {
                Write-Host "Running registry uninstall for Python $pythonVersion..." -ForegroundColor Yellow
                & cmd.exe /c $uninstallString /quiet | Out-Null
                Write-Host "Python $pythonVersion uninstalled successfully." -ForegroundColor Green
                if (Test-Path $pythonPath) {
                    try {
                        Remove-Item -Recurse -Force $pythonPath
                        Write-Host "Removed leftover Python directory: $pythonPath" -ForegroundColor Green
                    } catch {
                        Write-Warning "Could not remove Python directory $pythonPath: $_"
                    }
                }
            } else {
                Write-Warning "Registry entry found but no uninstall string for Python $pythonVersion."
            }
        } else {
            Write-Warning "No registry entry found for Python $pythonVersion."
        }
    }
} else {
    Write-Host "No python_version.txt found, falling back to existing uninstall logic..." -ForegroundColor Yellow
}
# --- END PATCH ---
    Stop-Transcript
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host "=== RetroIPTVGuide Complete Uninstaller ===" -ForegroundColor Cyan
Write-Host "Timestamp: $(Get-Date)"
Write-Host "Log file: $LogFile"

# Stop and remove service
$service = Get-Service -Name "RetroIPTVGuide" -ErrorAction SilentlyContinue
if ($service) {
    try {
        if ($service.Status -eq "Running") {
            Stop-Service -Name "RetroIPTVGuide" -Force
        }
        $nssmPath = "C:\nssm\nssm.exe"
        if (Test-Path $nssmPath) {
            & $nssmPath remove RetroIPTVGuide confirm
            Write-Host "RetroIPTVGuide service removed." -ForegroundColor Green
        } else {
            sc.exe delete RetroIPTVGuide | Out-Null
            Write-Host "RetroIPTVGuide service removed via sc.exe." -ForegroundColor Green
        }
    } catch {
        Write-Warning "Could not remove RetroIPTVGuide service automatically."
    }
} else {
    Write-Host "RetroIPTVGuide service not found." -ForegroundColor Yellow
}

# Candidate paths
$CandidateDirs = @(
    (Join-Path $PSScriptRoot "RetroIPTVGuide"),
    (Join-Path $env:USERPROFILE "RetroIPTVGuide"),
    (Join-Path ($env:HOMEDRIVE + $env:HOMEPATH) "RetroIPTVGuide"),
    (Join-Path $env:USERPROFILE "Desktop\RetroIPTVGuide"),
    "C:\RetroIPTVGuide"
)

foreach ($dir in $CandidateDirs) {
    if (Test-Path $dir) {
        try {
            Remove-Item -Recurse -Force $dir
            Write-Host "Removed RetroIPTVGuide folder: $dir" -ForegroundColor Green
            break
        } catch {
            Write-Error "Failed to remove $dir"
        }
    }
}

# Remove venv
$venvDirs = @(
    (Join-Path $PSScriptRoot "venv"),
    (Join-Path $env:USERPROFILE "venv"),
    (Join-Path ($env:HOMEDRIVE + $env:HOMEPATH) "venv")
)
foreach ($vdir in $venvDirs) {
    if (Test-Path $vdir) {
        try {
            Remove-Item -Recurse -Force $vdir
            Write-Host "Removed venv: $vdir" -ForegroundColor Green
        } catch {
            Write-Error "Failed to remove venv: $vdir"
        }
    }
}

# Attempt to remove Git Bash
$gitUninstall = Get-ChildItem "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall" -ErrorAction SilentlyContinue |
    Get-ItemProperty | Where-Object { $_.DisplayName -like "Git*" }
if ($gitUninstall -and $gitUninstall.UninstallString) {
    try {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c",$gitUninstall.UninstallString,"/VERYSILENT","/NORESTART" -Wait
        Write-Host "Git Bash uninstalled." -ForegroundColor Green
    } catch {
        Write-Warning "Could not uninstall Git Bash automatically."
    }
} else {
    Write-Host "Git Bash not found." -ForegroundColor Yellow
}

# Attempt to remove Python
$pyUninstall = Get-ChildItem "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall" -ErrorAction SilentlyContinue |
    Get-ItemProperty | Where-Object { $_.DisplayName -like "Python*" }
if ($pyUninstall -and $pyUninstall.UninstallString) {
    try {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c",$pyUninstall.UninstallString,"/quiet" -Wait
        Write-Host "Python uninstalled." -ForegroundColor Green
    } catch {
        Write-Warning "Could not uninstall Python automatically."
    }
} else {
    Write-Host "Python not found." -ForegroundColor Yellow
}

# --- PATCH: Stop and remove RetroIPTVGuide service, firewall rule, and NSSM ---
if (Get-Service RetroIPTVGuide -ErrorAction SilentlyContinue) {
    Write-Host "Stopping RetroIPTVGuide service..." -ForegroundColor Yellow
    Stop-Service RetroIPTVGuide -Force -ErrorAction SilentlyContinue
}

$nssmPath = "C:\nssm\nssm.exe"
if (Test-Path $nssmPath) {
    Write-Host "Removing RetroIPTVGuide service..." -ForegroundColor Yellow
    & $nssmPath remove RetroIPTVGuide confirm
}

Write-Host "Removing Windows Firewall port rule for RetroIPTVGuide..." -ForegroundColor Yellow
netsh advfirewall firewall delete rule name="RetroIPTVGuide" | Out-Null

if (Test-Path "C:\nssm") {
    Write-Host "Removing NSSM installation..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "C:\nssm"
}

# --- PATCH: Stop and remove RetroIPTVGuide service, firewall rule, and NSSM ---
if (Get-Service RetroIPTVGuide -ErrorAction SilentlyContinue) {
    Write-Host "Stopping RetroIPTVGuide service..." -ForegroundColor Yellow
    Stop-Service RetroIPTVGuide -Force -ErrorAction SilentlyContinue
}

# Try NSSM first
$nssmPath = "C:\nssm\nssm.exe"
if (Test-Path $nssmPath) {
    Write-Host "Removing RetroIPTVGuide service via NSSM..." -ForegroundColor Yellow
    & $nssmPath remove RetroIPTVGuide confirm
}

# Always try SC as a fallback to ensure service deletion
Write-Host "Ensuring RetroIPTVGuide service is deleted..." -ForegroundColor Yellow
sc.exe delete RetroIPTVGuide | Out-Null

Write-Host "Removing Windows Firewall port rule for RetroIPTVGuide..." -ForegroundColor Yellow
netsh advfirewall firewall delete rule name="RetroIPTVGuide" | Out-Null

if (Test-Path "C:\nssm") {
    Write-Host "Removing NSSM installation..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "C:\nssm"
}
# --- END PATCH ---

# --- END PATCH ---
# --- PATCH: Python uninstall using version + path file ---
$pythonVerFile = Join-Path $PSScriptRoot "logs\python_version.txt"
if (Test-Path $pythonVerFile) {
    $lines = Get-Content $pythonVerFile
    $pythonVersion = ($lines | Where-Object { $_ -like "Version=*" }) -replace "Version=", ""
    $pythonPath    = ($lines | Where-Object { $_ -like "Path=*" }) -replace "Path=", ""

    Write-Host "Attempting to uninstall Python $pythonVersion from $pythonPath..." -ForegroundColor Yellow

	$uninstaller = Join-Path $pythonPath "uninstall.exe"
	if (-not (Test-Path $uninstaller)) {
		# fallback: use Modify/Repair entry in registry if uninstall.exe missing
		$uninstallKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
		$pythonKey = Get-ChildItem $uninstallKey | Where-Object {
			$_.GetValue("DisplayName") -like "Python $pythonVersion*"
		}
		if ($pythonKey) {
			$uninstallString = $pythonKey.GetValue("UninstallString", $null)
			if ($uninstallString) {
				Write-Host "Running registry uninstall for Python $pythonVersion..." -ForegroundColor Yellow
				& cmd.exe /c $uninstallString /quiet | Out-Null
			}
		}
	}

} else {
    Write-Host "No python_version.txt found, falling back to existing uninstall logic..." -ForegroundColor Yellow
}
# --- END PATCH ---
# --- PATCH: Corrected Python uninstall using version + path file ---
$pythonVerFile = Join-Path $PSScriptRoot "logs\python_version.txt"
if (Test-Path $pythonVerFile) {
    $lines = Get-Content $pythonVerFile
    $pythonVersion = ($lines | Where-Object { $_ -like "Version=*" }) -replace "Version=", ""
    $pythonPath    = ($lines | Where-Object { $_ -like "Path=*" }) -replace "Path=", ""

    Write-Host "Attempting to uninstall Python $pythonVersion from $pythonPath..." -ForegroundColor Yellow

    $uninstaller = Join-Path $pythonPath "uninstall.exe"
    if (Test-Path $uninstaller) {
        & $uninstaller /quiet | Out-Null
        Write-Host "Python $pythonVersion uninstalled successfully." -ForegroundColor Green
    } else {
        Write-Warning "Uninstaller not found at $uninstaller. Trying registry lookup..."
        $uninstallKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        $pythonKey = Get-ChildItem $uninstallKey | Where-Object {
            $_.GetValue("DisplayName") -like "Python $pythonVersion*"
        } | Select-Object -First 1
        if ($pythonKey) {
            $uninstallString = $pythonKey.GetValue("UninstallString", $null)
            if ($uninstallString) {
                Write-Host "Running registry uninstall for Python $pythonVersion..." -ForegroundColor Yellow
                & cmd.exe /c $uninstallString /quiet | Out-Null
                Write-Host "Python $pythonVersion uninstalled successfully." -ForegroundColor Green
            } else {
                Write-Warning "Registry entry found but no uninstall string for Python $pythonVersion."
            }
        } else {
            Write-Warning "No registry entry found for Python $pythonVersion."
        }
    }
} else {
    Write-Host "No python_version.txt found, falling back to existing uninstall logic..." -ForegroundColor Yellow
}
# --- END PATCH ---
Stop-Transcript
Write-Host "Press any key to exit..." -ForegroundColor Cyan
Pause

# Clean logs after transcript ends
#if (Test-Path $LogDir) {
#    try {
#        Remove-Item -Recurse -Force $LogDir
#        Write-Host "Removed logs folder: $LogDir" -ForegroundColor Green
#    } catch {
#        Write-Warning "Failed to remove logs folder: $LogDir"
#    }
#}

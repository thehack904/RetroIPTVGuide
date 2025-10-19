rem @echo off
rem powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
@echo off
mode con: cols=160 lines=50

REM ============================================================
REM RetroIPTVGuide Windows Unified Installer / Uninstaller
REM Version: 3.4.0-testing
REM License: Creative Commons BY-NC-SA 4.0
REM ============================================================

:: ============================================================
::  Ask to Restart CMD as Administrator (bulletproof version)
:: ============================================================

:: Check admin rights
net session >nul 2>&1
if %errorlevel%==0 (
    echo Running as Administrator.
    goto :continue
)

echo.
echo WARNING: This install script is NOT running as Administrator.
set /p choice=Do you want to restart this script as Administrator? (Y/N): 
if /i "%choice%"=="Y" (
    echo Relaunching with elevated privileges...
    powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c cd /d \"%CD%\" && \"%~f0\"' -Verb RunAs"
    exit /b
) else (
    echo Continuing without elevation...
)

:continue
setlocal
set "VERSION=3.4.0-testing"
set "REPO_URL=https://github.com/thehack904/RetroIPTVGuide.git"
set "ZIP_URL=https://github.com/thehack904/RetroIPTVGuide/archive/refs/heads/testing.zip"
set "INSTALL_DIR=%~dp0RetroIPTVGuide"
set "PS1_FILE=%INSTALL_DIR%\retroiptv_windows.ps1"

title RetroIPTVGuide Windows Installer
color 0A
cls

echo.
echo.
echo ¦¦¦¦¦¦¦¦¦¦                ¦¦¦                        ¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦¦¦¦¦¦    ¦¦¦   ¦¦¦¦¦¦¦             ¦¦¦       ¦¦¦
echo ¦¦¦     ¦¦¦               ¦¦¦                          ¦¦¦  ¦¦¦     ¦¦¦     ¦¦¦    ¦¦¦    ¦¦¦  ¦¦¦   ¦¦¦                      ¦¦¦
echo ¦¦¦     ¦¦¦  ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦ ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦    ¦¦¦  ¦¦¦     ¦¦¦     ¦¦¦    ¦¦¦    ¦¦¦ ¦¦¦        ¦¦¦    ¦¦¦ ¦¦¦ ¦¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦
echo ¦¦¦¦¦¦¦¦¦¦  ¦¦¦    ¦¦¦    ¦¦¦    ¦¦¦¦     ¦¦¦    ¦¦¦   ¦¦¦  ¦¦¦¦¦¦¦¦¦¦      ¦¦¦    ¦¦¦    ¦¦¦ ¦¦¦  ¦¦¦¦¦ ¦¦¦    ¦¦¦ ¦¦¦¦¦¦    ¦¦¦ ¦¦¦    ¦¦¦
echo ¦¦¦   ¦¦¦   ¦¦¦¦¦¦¦¦¦¦    ¦¦¦    ¦¦¦      ¦¦¦    ¦¦¦   ¦¦¦  ¦¦¦             ¦¦¦     ¦¦¦  ¦¦¦  ¦¦¦     ¦¦ ¦¦¦    ¦¦¦ ¦¦¦¦¦¦    ¦¦¦ ¦¦¦¦¦¦¦¦¦¦
echo ¦¦¦    ¦¦¦  ¦¦¦           ¦¦¦    ¦¦¦      ¦¦¦    ¦¦¦   ¦¦¦  ¦¦¦             ¦¦¦      ¦¦¦¦¦¦    ¦¦¦  ¦¦¦¦ ¦¦¦   ¦¦¦¦ ¦¦¦¦¦¦   ¦¦¦¦ ¦¦¦
echo ¦¦¦     ¦¦¦  ¦¦¦¦¦¦¦¦      ¦¦¦¦¦ ¦¦¦       ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦¦             ¦¦¦       ¦¦¦¦      ¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦¦ ¦¦¦ ¦¦¦¦¦¦¦¦¦  ¦¦¦¦¦¦¦¦
echo.
echo ============================================================
echo   RetroIPTVGuide  ^|  Windows Edition (Headless Installer)
echo   Version %VERSION%
echo ============================================================
echo.
echo  This launcher prepares your Windows environment to safely run
echo  the RetroIPTVGuide PowerShell installer.
													 
echo.
echo  It will do the following:
echo   * Set PowerShell ExecutionPolicy to RemoteSigned (CurrentUser)
echo   * Download the latest retroiptv_windows.ps1 from the testing branch
echo   * Start the PowerShell installer or uninstaller
echo.
echo  This change affects only your current Windows user account and
echo  can be reverted anytime with:
echo     powershell Set-ExecutionPolicy Restricted -Scope CurrentUser
echo.
echo ===================================================================
echo.

set /p agree=Do you agree to proceed with a one-time ExecutionPolicy bypass? (Y/N): 
if /I not "%agree%"=="Y" if /I not "%agree%"=="y" (
  echo.
  echo Aborted by user.
  pause
  exit /b
)

REM ------------------------------------------------------------
REM  Step 1: Check if RetroIPTVGuide repo or folder exists
REM ------------------------------------------------------------
if not exist "%INSTALL_DIR%" (
  echo.
  echo ============================================================
  echo   RetroIPTVGuide not found in "%~dp0".
  echo   Attempting to obtain files from GitHub...
  echo ============================================================
  echo.

  REM ------------------------------------------------------------
  REM  Ensure Git is available (install via Chocolatey if missing)
  REM ------------------------------------------------------------
  where git >nul 2>&1
  if errorlevel 1 (
    echo Git not found. Checking for Chocolatey...
    where choco >nul 2>&1
    if errorlevel 1 (
      echo Installing Chocolatey...
      powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Set-ExecutionPolicy Bypass -Scope Process -Force; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    )
    echo Installing Git via Chocolatey...
    choco install -y git >nul 2>&1
    REM Refresh PATH so git.exe becomes immediately visible
    set "PATH=%PATH%;C:\ProgramData\chocolatey\bin"
  )

  REM ------------------------------------------------------------
  REM  Attempt to clone using Git; if it fails, use ZIP fallback
  REM ------------------------------------------------------------
  echo Cloning repository from GitHub...
  git clone --branch testing --depth 1 "%REPO_URL%" "%INSTALL_DIR%" >nul 2>&1

  if exist "%INSTALL_DIR%\retroiptv_windows.ps1" (
    echo Repository cloned successfully.
  ) else (
    echo Clone failed or incomplete. Attempting ZIP download instead...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP%\RetroIPTVGuide.zip' -UseBasicParsing"
    if exist "%TEMP%\RetroIPTVGuide.zip" (
      echo Extracting ZIP...
      powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Expand-Archive -Path '%TEMP%\RetroIPTVGuide.zip' -DestinationPath '%~dp0' -Force"
      ren "%~dp0RetroIPTVGuide-testing" "RetroIPTVGuide" >nul 2>&1
      del "%TEMP%\RetroIPTVGuide.zip" >nul 2>&1
      if exist "%INSTALL_DIR%\retroiptv_windows.ps1" (
        echo Repository extracted successfully.
      ) else (
        echo Extraction failed. Please verify GitHub structure or try again.
        pause
        exit /b
      )
    ) else (
      echo Failed to download ZIP file from GitHub.
      pause
      exit /b
    )
  )
)


REM ------------------------------------------------------------
REM  Step 2: Verify that PS1 file exists now
REM ------------------------------------------------------------
if not exist "%PS1_FILE%" (
  echo ? retroiptv_windows.ps1 not found even after download.
  echo Please verify that the repository structure is correct.
  pause
  exit /b
)


REM Optional: warn if not elevated
net session >nul 2>&1
if errorlevel 1 (
  echo.
  echo     Not running as Administrator. The installer needs elevation,
  echo     right-click this .bat and choose "Run as administrator".
  echo.
  pause
  exit
)

:menu
echo.
echo ============================================================
echo   RetroIPTVGuide Windows Installer Menu  (v%VERSION%)
echo ============================================================
echo [1] Install RetroIPTVGuide
echo [2] Uninstall RetroIPTVGuide
echo [3] Exit
echo ============================================================
set /p choice=Select an option (1-3): 
echo.

if "%choice%"=="1" (
  echo Launching PowerShell installer...
  echo.
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1_FILE%" install
  echo.
  echo Installation process complete. Review log output above for details.
  pause
  exit /b
)
if "%choice%"=="2" (
  echo Launching PowerShell uninstaller...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1_FILE%" uninstall
  echo.
  echo Uninstallation process complete. Review log output above for details.
  pause
  exit /b
)
if "%choice%"=="3" (
  echo Exiting RetroIPTVGuide installer. Goodbye!
  pause
  exit /b
)

echo Invalid selection. Please choose 1, 2, or 3.
echo.
goto menu

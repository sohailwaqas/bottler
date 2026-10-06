@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Bottler - Windows Launcher
echo ============================================
echo.

REM --- 1. Check Python is installed and on PATH ---------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on your PATH.
    echo.
    echo Install Python 3.10 or later from https://www.python.org/downloads/
    echo IMPORTANT: on the install screen, check the box that says
    echo            "Add python.exe to PATH" before clicking Install.
    echo.
    pause
    exit /b 1
)

REM --- 2. Create the virtual environment on first run ---------------------
if not exist "venv\Scripts\activate.bat" (
    echo Creating a virtual environment in .\venv ...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create the virtual environment. See the message above.
        pause
        exit /b 1
    )
)

call "venv\Scripts\activate.bat"

REM --- 3. Keep dependencies in sync with requirements.txt on every launch --
REM     (A stale venv from an older copy of this app could otherwise linger
REM      with an incompatible package version even after files are updated -
REM      merely checking "is streamlit importable at all" was not enough,
REM      and caused real bugs when width='stretch' was used against an old
REM      Streamlit that only accepted integer pixel widths. `pip install`
REM      is fast when everything already matches, so just always run it.)
echo.
echo Checking dependencies are up to date...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed. Re-running without -q for details:
    python -m pip install -r requirements.txt
    echo.
    echo If it mentions a package needing "Microsoft Visual C++ Build Tools",
    echo make sure you're using the requirements.txt shipped with this app -
    echo it deliberately avoids that dependency.
    pause
    exit /b 1
)

REM --- 4. Launch --------------------------------------------------------------
echo.
echo Starting Bottler... your browser will open automatically.
echo (Leave this window open while using the app. Press Ctrl+C here to stop it.)
echo.
streamlit run app.py

pause

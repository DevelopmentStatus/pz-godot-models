@echo off
REM ---------------------------------------------------------------------
REM  Installs the community 3D models into a pz-godot checkout.
REM
REM  The normal way: drag this one file into your pz-godot folder (next to
REM  project.godot) and double-click it. It finds the checkout on its own,
REM  and fetches its own installer script if it isn't sitting next to one.
REM
REM  Also works:
REM    - Drag your pz-godot folder onto this file instead.
REM    - Run it with the path:  install-models.bat C:\path\to\pz-godot
REM
REM  The models contain NO Project Zomboid art. Each names the sprite it
REM  wants pixels from, and the game textures it at runtime from the atlas
REM  YOU generated from YOUR OWN copy of the game. Run pz-godot's setup.bat
REM  first, or the models render in flat colours.
REM
REM  Safe to re-run and safe to undo. Only models that actually changed are
REM  downloaded, each is checked against its SHA-256 before being written,
REM  and --prune removes exactly what was installed - putting back any model
REM  or mesh_overrides.json rule of your own that it had to move aside.
REM ---------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo   ERROR: Python is not on your PATH.
    echo.
    echo   Install Python 3 from https://www.python.org/downloads/ and tick
    echo   "Add python.exe to PATH" in the installer, then run this again.
    echo   ^(pz-godot's own setup.bat needs it too.^)
    echo.
    pause
    exit /b 1
)

set SCRIPT=pz_models_install.py
if not exist "%SCRIPT%" (
    REM Dragged in on its own, with no pz_models_install.py beside it - fetch
    REM the one it belongs with rather than making the user keep a folder
    REM together. Cached in TEMP so a re-run does not need a connection twice.
    set SCRIPT=%TEMP%\pz_models_install.py
    where curl >nul 2>nul
    if errorlevel 1 (
        echo.
        echo   ERROR: pz_models_install.py is not next to this file, and curl
        echo   is not available to fetch it.
        echo.
        echo   Get the full install\ folder from
        echo   https://github.com/DevelopmentStatus/pz-godot-models instead.
        echo.
        pause
        exit /b 1
    )
    echo   Fetching the installer script...
    curl -fsSL -o "!SCRIPT!" "https://raw.githubusercontent.com/DevelopmentStatus/pz-godot-models/main/install/pz_models_install.py"
    if errorlevel 1 (
        echo.
        echo   ERROR: could not download pz_models_install.py. Check your
        echo   connection and try again.
        echo.
        pause
        exit /b 1
    )
)

if "%~1"=="" (
    REM No path given - let the script walk up from here looking for
    REM project.godot, which works when this file sits inside a checkout.
    python "%SCRIPT%"
) else (
    python "%SCRIPT%" --repo-root "%~1"
)
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% NEQ 0 (
    echo.
    echo   Finished with errors - see above.
    echo.
    echo   If it could not find your pz-godot checkout, drag the folder onto
    echo   this .bat file, or run:
    echo       install-models.bat C:\path\to\pz-godot
) else (
    echo.
    echo   Done. Launch the game to see them.
)
echo.
pause
exit /b %EXITCODE%

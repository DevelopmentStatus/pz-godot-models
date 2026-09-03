@echo off
REM ---------------------------------------------------------------------
REM  Installs the community 3D models into a pz-godot checkout.
REM
REM  Three ways to use this:
REM
REM    1. Drag your pz-godot folder onto this file.
REM    2. Run it with the path:  install-models.bat C:\path\to\pz-godot
REM    3. Drop this whole install\ folder inside a pz-godot checkout and
REM       double-click it - it will find the checkout on its own.
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
setlocal
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

if "%~1"=="" (
    REM No path given - let the script walk up from here looking for
    REM project.godot, which works when this folder sits inside a checkout.
    python pz_models_install.py
) else (
    python pz_models_install.py --repo-root "%~1"
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

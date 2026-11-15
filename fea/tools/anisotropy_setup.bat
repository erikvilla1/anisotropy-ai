@echo off
rem Set this PC up for Anisotropy, once: the menu in Abaqus/CAE and the links of the site. README.txt says what it does.
cd /d "%~dp0"
if not exist anisotropy_setup.py (
  echo This was started from inside the zip, where its other files are not beside it.
  echo Unzip first: right-click anisotropy-connector.zip and choose Extract All.
  echo Then double-click "Set up Anisotropy" in the folder that opens.
  echo.
  pause
  exit /b 1
)
where abaqus >nul 2>nul
if errorlevel 1 (
  echo The command abaqus was not found on this PC.
  echo Open an Abaqus Command window, go to this folder, and run:  abaqus python anisotropy_setup.py
  echo.
  pause
  exit /b 1
)
echo Setting this PC up for Anisotropy. This takes up to a minute...
echo.
call abaqus python anisotropy_setup.py --box
echo.
echo The setup has ended. Press any key to close this window.
pause >nul

@echo off
rem Set this PC up for Anisotropy, once: the menu in Abaqus/CAE and the links of the site. README.txt says what it does.
cd /d "%~dp0"
where abaqus >nul 2>nul
if errorlevel 1 (
  echo The command abaqus was not found on this PC.
  echo Open an Abaqus Command window, go to this folder, and run:  abaqus python anisotropy_setup.py
  echo.
  pause
  exit /b 1
)
call abaqus python anisotropy_setup.py
echo.
pause

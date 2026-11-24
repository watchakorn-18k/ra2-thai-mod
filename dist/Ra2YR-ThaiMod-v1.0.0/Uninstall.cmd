@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Manage-Mod.ps1" -Mode Uninstall
pause

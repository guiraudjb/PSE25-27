@echo off
rem Lance la page de revision de ce depot sur un serveur web local (autohebergement, sans Internet).
rem Double-cliquer ce fichier : il execute serveur-local.ps1 (PowerShell, inclus dans Windows) et ouvre
rem le navigateur. Fermer la fenetre (ou Q / Echap) arrete le serveur.
rem Options transmises au script, par exemple : lancer-site-local.bat -Port 9000 -SansNavigateur
setlocal
for %%I in ("%~dp0.") do set "DEPOT=%%~nxI"
title Revision %DEPOT% - serveur local
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0serveur-local.ps1" %*
if errorlevel 1 pause
endlocal

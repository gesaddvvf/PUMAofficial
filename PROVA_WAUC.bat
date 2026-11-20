@echo off
rem Perche WAUC non trova una persona? Mostra sedi interrogate, risposte e ricerca per email e cognome (serve FortiClient VPN).
setlocal
cd /d "%~dp0"
title P.U.M.A. - diagnosi WAUC
call :python || goto fine
%PY% manage.py diagnosi-wauc
goto fine

:python
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo  Python non trovato su questo PC.
  echo  Installalo da https://www.python.org/downloads/ - versione 3.9 o successiva -
  echo  e durante l'installazione spunta la casella "Add python.exe to PATH".
  exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1
if errorlevel 1 (
  echo.
  echo  Serve Python 3.9 o successivo. Aggiornalo da https://www.python.org/downloads/
  exit /b 1
)
exit /b 0

:fine
echo.
pause

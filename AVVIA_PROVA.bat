@echo off
rem P.U.M.A. - modalita PROVA: utenti fittizi, password "dev", WAUC simulato, db separato in data_prova\. Nessuna VPN.
setlocal
cd /d "%~dp0"
title P.U.M.A. - MODALITA PROVA
call :python || goto fine
set PUMA_MODALITA=prova
set PUMA_APRI_BROWSER=1
echo.
echo  ==== P.U.M.A. - MODALITA PROVA - utenti fittizi, nessun dato reale ====
echo  Il browser si apre da solo: scegli un utente di prova. Per fermare PUMA chiudi questa finestra.
echo.
%PY% app.py
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

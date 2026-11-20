@echo off
rem P.U.M.A. - avvio REALE IN RETE: come AVVIA.bat, ma PUMA si apre anche dagli altri PC della stessa rete
rem (link http://<indirizzo di questo PC>:8080). Il PC deve restare acceso con questa finestra aperta.
setlocal
cd /d "%~dp0"
title P.U.M.A. - accesso reale IN RETE
call :python || goto fine
set PUMA_APRI_BROWSER=1
set PUMA_HOST=0.0.0.0
echo.
echo  ==== P.U.M.A. - accesso reale IN RETE (anche dagli altri PC) ====
echo.
echo  [1/3] Verifica del collegamento alla rete VVF - FortiClient VPN...
%PY% manage.py verifica-vpn
if errorlevel 1 (
  echo.
  echo  ATTENZIONE: la rete VVF non risponde. Collega FortiClient VPN e riavvia questo file,
  echo  oppure premi un tasto per avviare comunque PUMA.
  pause >nul
)
echo.
echo  [2/3] Controllo dell'amministratore...
%PY% manage.py primo-admin
echo.
echo  [3/3] Avvio di PUMA - il browser si apre da solo. Per fermarlo chiudi questa finestra.
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

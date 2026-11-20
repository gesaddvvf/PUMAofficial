@echo off
rem Cancella i dati della modalita prova (cartella data_prova). I dati reali in data\ NON vengono toccati.
setlocal
cd /d "%~dp0"
if not exist data_prova (
  echo  Non ci sono dati di prova da cancellare.
  goto fine
)
echo  Verranno cancellati SOLO i dati di prova - cartella data_prova. I dati reali restano.
choice /c SN /m "Confermi"
if errorlevel 2 goto fine
rmdir /s /q data_prova
echo  Fatto: al prossimo AVVIA_PROVA.bat i dati di prova vengono ricreati da zero.
:fine
echo.
pause

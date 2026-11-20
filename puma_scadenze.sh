#!/usr/bin/env bash
# P.U.M.A.: invia gli alert di scadenza (utente + ROP). Va pianificato una volta al giorno, es. con cron:
#   0 7 * * *  /percorso/del/portale/puma_scadenze.sh >> /percorso/del/portale/data/puma_scadenze.log 2>&1
# Servono PUMA_SMTP_HOST (e, se richiesti, PUMA_SMTP_PORT/TLS/USER/PASS, PUMA_MAIL_FROM): vedi GUIDA_PUMA.md.
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && { echo "Python 3.9+ non trovato."; exit 1; }
[ -f ./puma.env ] && { set -a; . ./puma.env; set +a; }   # opzionale: file con le variabili PUMA_*
exec "$PY" manage.py puma-scadenze

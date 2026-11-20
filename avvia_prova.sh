#!/usr/bin/env bash
# P.U.M.A. - modalita PROVA: utenti fittizi, password "dev", WAUC simulato, db separato in data_prova/. Nessuna VPN.
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && { echo "Python 3.9+ non trovato (es. sudo apt install python3)."; exit 1; }
export PUMA_MODALITA=prova PUMA_APRI_BROWSER="${PUMA_APRI_BROWSER:-1}"
exec "$PY" app.py

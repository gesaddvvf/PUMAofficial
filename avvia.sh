#!/usr/bin/env bash
# P.U.M.A. - avvio REALE: credenziali dipartimentali e dati WAUC. Serve FortiClient VPN collegata (o la rete VVF).
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && { echo "Python 3.9+ non trovato (es. sudo apt install python3)."; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)' || { echo "Serve Python 3.9 o superiore (trovato: $("$PY" -V))."; exit 1; }
echo "[1/3] Verifica del collegamento alla rete VVF (FortiClient VPN)..."
if ! "$PY" manage.py verifica-vpn; then
  echo; read -r -p "La rete VVF non risponde. Collega la VPN e riprova, oppure premi INVIO per avviare comunque... " _
fi
echo "[2/3] Controllo dell'amministratore..."
"$PY" manage.py primo-admin
echo "[3/3] Avvio di PUMA (CTRL+C per fermarlo)"
export PUMA_APRI_BROWSER="${PUMA_APRI_BROWSER:-1}"
exec "$PY" app.py

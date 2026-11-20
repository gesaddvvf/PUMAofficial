#!/usr/bin/env bash
# Prova le credenziali dipartimentali sul server di posta e mostra la risposta esatta (serve FortiClient VPN).
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
exec "$PY" manage.py prova-login "$@"

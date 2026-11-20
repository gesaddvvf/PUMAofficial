#!/usr/bin/env bash
# Controlla che posta dipartimentale e WAUC siano raggiungibili, cioe che FortiClient VPN sia collegata.
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
exec "$PY" manage.py verifica-vpn

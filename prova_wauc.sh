#!/usr/bin/env bash
# Perche WAUC non trova una persona? (serve FortiClient VPN)
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
exec "$PY" manage.py diagnosi-wauc "$@"

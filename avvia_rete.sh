#!/usr/bin/env bash
# P.U.M.A. - avvio REALE IN RETE: come avvia.sh, ma raggiungibile anche dagli altri PC della stessa rete.
cd "$(dirname "$0")" || exit 1
export PUMA_HOST=0.0.0.0
exec ./avvia.sh

#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Smoke test recipe after building Accel-Sim with the overlay:

  export SGRAM_BACKEND=fixed
  export SGRAM_FIXED_LATENCY=100

Then run a tiny Accel-Sim benchmark and check stdout for:

  SGRAM fixed-latency backend enabled

and final stats:

  sgram_fixed_backend[*]_pushes
  sgram_fixed_backend[*]_returns

This script will become executable smoke automation once a canonical tiny
Accel-Sim benchmark command is selected.
EOF

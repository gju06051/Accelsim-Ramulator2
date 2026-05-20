#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  cat >&2 <<'USAGE'
Usage:
  run_nvbit_row_opportunity.sh <name> <output-dir> -- <command> [args...]

Creates:
  <output-dir>/<name>.nvbit.raw.log
  <output-dir>/<name>.mem.trace
  <output-dir>/<name>.row_opp.csv
USAGE
  exit 2
fi

NAME="$1"
OUT_DIR="$2"
shift 2

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
"${ROOT}/gpu_benchmark/scripts/run_with_nvbit_mem_trace.sh" "${NAME}" "${OUT_DIR}" "$@"

"${ROOT}/tools/row_sector_opportunity.py" \
  "${OUT_DIR}/${NAME}.mem.trace" \
  --row-size "${ROW_SIZE:-2048}" \
  --baseline-atom "${BASELINE_ATOM:-32}" \
  --granularities "${GRANULARITIES:-32,16,8}" \
  --lookahead "${LOOKAHEAD:-32}" \
  --csv "${OUT_DIR}/${NAME}.row_opp.csv"

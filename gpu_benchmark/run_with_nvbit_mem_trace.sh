#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  cat >&2 <<'USAGE'
Usage:
  run_with_nvbit_mem_trace.sh <name> <output-dir> -- <command> [args...]

Example:
  ./gpu_benchmark/run_with_nvbit_mem_trace.sh graphbig_bfs traces -- \
    ./gpu_benchmark/suites/graphBIG/gpu_bench/gpu_BFS/bfs_topo_frontier \
    --dataset ./gpu_benchmark/suites/graphBIG/dataset/small --root 31
USAGE
  exit 2
fi

NAME="$1"
OUT_DIR="$2"
shift 2
if [[ "${1:-}" != "--" ]]; then
  echo "expected -- before command" >&2
  exit 2
fi
shift

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NVBIT_TOOL="${ROOT}/tools/nvbit_release_x86_64/tools/mem_trace/mem_trace.so"
PARSER="${ROOT}/tools/nvbit_memtrace_to_trace.py"
RUN_WORKDIR="${RUN_WORKDIR:-}"

mkdir -p "${OUT_DIR}"
RAW_LOG="${OUT_DIR}/${NAME}.nvbit.raw.log"
TRACE="${OUT_DIR}/${NAME}.mem.trace"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export LD_PRELOAD="${NVBIT_TOOL}${LD_PRELOAD:+:${LD_PRELOAD}}"
export ACK_CTX_INIT_LIMITATION="${ACK_CTX_INIT_LIMITATION:-1}"
export NOBANNER="${NOBANNER:-1}"

if [[ -n "${RUN_WORKDIR}" ]]; then
  cd "${RUN_WORKDIR}"
fi

"$@" >"${RAW_LOG}" 2>&1
"${PARSER}" "${RAW_LOG}" -o "${TRACE}"

echo "raw_log=${RAW_LOG}"
echo "trace=${TRACE}"

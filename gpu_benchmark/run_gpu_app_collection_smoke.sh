#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT}/traces/run_logs/gpu_app_collection_smoke"
mkdir -p "${OUT_DIR}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

if [[ "${BUILD:-1}" != "0" ]]; then
  "${ROOT}/build_gpu_app_collection.sh" polybench ispass-2009
fi
# shellcheck source=/dev/null
source "${ROOT}/setup_gpu_app_collection_env.sh" >/dev/null

run_one() {
  local name="$1"
  shift
  local log="${OUT_DIR}/${name}.log"

  echo "== ${name} =="
  {
    echo "## ${name}"
    date
    "${BINDIR}/${BINSUBDIR}/${name}" "$@"
  } >"${log}" 2>&1
  tail -n 5 "${log}"
}

POLYBENCH=(
  polybench-atax
  polybench-bicg
  polybench-gemm
  polybench-gesummv
  polybench-mvt
)

ISPASS_NOARG=(
  ispass-2009-LIB
  ispass-2009-LPS
  ispass-2009-NQU
  ispass-2009-STO
)

for bench in "${POLYBENCH[@]}"; do
  run_one "${bench}"
done

for bench in "${ISPASS_NOARG[@]}"; do
  run_one "${bench}"
done

run_one ispass-2009-RAY 256 256

echo "logs=${OUT_DIR}"

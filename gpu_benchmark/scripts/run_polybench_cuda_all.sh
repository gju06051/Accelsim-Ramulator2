#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/traces/run_logs/polybench_cuda"
mkdir -p "${OUT_DIR}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

"${ROOT}/scripts/build_gpu_app_collection.sh" polybench
# shellcheck source=/dev/null
source "${ROOT}/scripts/setup_gpu_app_collection_env.sh" >/dev/null

mapfile -t BENCHMARKS < <("${ROOT}/scripts/list_gpu_app_binaries.sh" | awk '/^polybench-/')

for bench in "${BENCHMARKS[@]}"; do
  log="${OUT_DIR}/${bench}.log"
  echo "== ${bench} =="
  {
    echo "## ${bench}"
    date
    "${BINDIR}/${BINSUBDIR}/${bench}"
  } >"${log}" 2>&1
  tail -n 5 "${log}"
done

echo "logs=${OUT_DIR}"

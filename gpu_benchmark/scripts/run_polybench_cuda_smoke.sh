#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCHMARKS=(polybench-atax polybench-bicg polybench-gemm polybench-gesummv polybench-mvt)

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

"${ROOT}/scripts/build_gpu_app_collection.sh" polybench
# shellcheck source=/dev/null
source "${ROOT}/scripts/setup_gpu_app_collection_env.sh" >/dev/null

for bench in "${BENCHMARKS[@]}"; do
  echo "== ${bench} =="
  "${BINDIR}/${BINSUBDIR}/${bench}"
done

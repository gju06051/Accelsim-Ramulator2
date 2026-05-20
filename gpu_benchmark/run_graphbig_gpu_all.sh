#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GPU_ROOT="${ROOT}/suites/graphBIG/gpu_bench"
DATASET="${GRAPHBIG_DATASET:-${ROOT}/suites/graphBIG/dataset/small}"
OUT_DIR="${ROOT}/traces/run_logs/graphbig_gpu"
mkdir -p "${OUT_DIR}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

BENCH_DIRS=(
  gpu_BFS
  gpu_BetweennessCentr
  gpu_ConnectedComp
  gpu_DegreeCentr
  gpu_GraphColoring
  gpu_SSSP
  gpu_TriangleCount
  gpu_kCore
)

for bench in "${BENCH_DIRS[@]}"; do
  bench_dir="${GPU_ROOT}/${bench}"
  log="${OUT_DIR}/${bench}.log"
  echo "== ${bench} =="
  {
    echo "## ${bench}"
    date
    make -C "${bench_dir}" clean
    make -C "${bench_dir}"
    target="$(awk -F= '/^TARGET=/{gsub(/[ \t]/, "", $2); print $2; exit}' "${bench_dir}/Makefile")"
    run_args="$(awk -F= '/^RUN_ARGS=/{sub(/^[ \t]+/, "", $2); print $2; exit}' "${bench_dir}/Makefile")"
    run_args="${run_args//\$(ROOT)/${ROOT}/suites/graphBIG}"
    run_args="${run_args//\${ROOT}/${ROOT}/suites/graphBIG}"
    run_args="${run_args//--dataset ${ROOT}\/suites\/graphBIG\/dataset\/small/--dataset ${DATASET}}"
    # shellcheck disable=SC2086
    "${bench_dir}/${target}" ${run_args}
  } >"${log}" 2>&1
  tail -n 8 "${log}"
done

echo "logs=${OUT_DIR}"

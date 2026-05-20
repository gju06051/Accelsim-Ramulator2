#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT}/traces/run_logs/available_benchmarks"
SUMMARY="${OUT_DIR}/summary.tsv"
TIMEOUT="${BENCH_TIMEOUT:-60s}"
mkdir -p "${OUT_DIR}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

# shellcheck source=/dev/null
source "${ROOT}/setup_gpu_app_collection_env.sh" >/dev/null

printf "suite\tbenchmark\tstatus\texit_code\tlog\tcommand\n" >"${SUMMARY}"

record() {
  local suite="$1"
  local name="$2"
  local status="$3"
  local code="$4"
  local log="$5"
  shift 5
  printf "%s\t%s\t%s\t%s\t%s\t" "${suite}" "${name}" "${status}" "${code}" "${log}" >>"${SUMMARY}"
  printf "%q " "$@" >>"${SUMMARY}"
  printf "\n" >>"${SUMMARY}"
}

run_case() {
  local suite="$1"
  local name="$2"
  shift 2
  local log="${OUT_DIR}/${suite}_${name}.log"

  echo "== ${suite}/${name} =="
  set +e
  timeout "${TIMEOUT}" "$@" >"${log}" 2>&1
  local code=$?
  set -e

  if [[ ${code} -eq 0 ]]; then
    record "${suite}" "${name}" "PASS" "${code}" "${log}" "$@"
  elif [[ ${code} -eq 124 ]]; then
    record "${suite}" "${name}" "TIMEOUT" "${code}" "${log}" "$@"
  else
    record "${suite}" "${name}" "FAIL" "${code}" "${log}" "$@"
  fi
  tail -n 5 "${log}" || true
}

for bench in \
  polybench-2DConvolution \
  polybench-2mm \
  polybench-3DConvolution \
  polybench-3mm \
  polybench-atax \
  polybench-bicg \
  polybench-correlation \
  polybench-covariance \
  polybench-fdtd2d \
  polybench-gemm \
  polybench-gesummv \
  polybench-gramschmidt \
  polybench-mvt \
  polybench-syr2k \
  polybench-syrk
do
  run_case gpu-app-collection "${bench}" "${BINDIR}/${BINSUBDIR}/${bench}"
done

run_case gpu-app-collection ispass-2009-BFS "${BINDIR}/${BINSUBDIR}/ispass-2009-BFS"
run_case gpu-app-collection ispass-2009-LIB "${BINDIR}/${BINSUBDIR}/ispass-2009-LIB"
run_case gpu-app-collection ispass-2009-LPS "${BINDIR}/${BINSUBDIR}/ispass-2009-LPS"
run_case gpu-app-collection ispass-2009-NN "${BINDIR}/${BINSUBDIR}/ispass-2009-NN"
run_case gpu-app-collection ispass-2009-NQU "${BINDIR}/${BINSUBDIR}/ispass-2009-NQU"
run_case gpu-app-collection ispass-2009-RAY "${BINDIR}/${BINSUBDIR}/ispass-2009-RAY" 256 256
run_case gpu-app-collection ispass-2009-STO "${BINDIR}/${BINSUBDIR}/ispass-2009-STO"

GRAPHBIG_ROOT="${ROOT}/suites/graphBIG"
GRAPHBIG_GPU="${GRAPHBIG_ROOT}/gpu_bench"
GRAPHBIG_DATA="${GRAPHBIG_ROOT}/dataset/small"

run_case graphBIG bfs_topo_frontier \
  "${GRAPHBIG_GPU}/gpu_BFS/bfs_topo_frontier" --dataset "${GRAPHBIG_DATA}" --root 31
run_case graphBIG betweenness \
  "${GRAPHBIG_GPU}/gpu_BetweennessCentr/betweenness" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG connected_comp \
  "${GRAPHBIG_GPU}/gpu_ConnectedComp/connected_comp" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG degree_centr \
  "${GRAPHBIG_GPU}/gpu_DegreeCentr/degree_centr" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG gc_data_thread_centric \
  "${GRAPHBIG_GPU}/gpu_GraphColoring/gc_data_thread_centric" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG gc_data_warp_centric \
  "${GRAPHBIG_GPU}/gpu_GraphColoring/gc_data_warp_centric" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG gc_topo_thread_centric \
  "${GRAPHBIG_GPU}/gpu_GraphColoring/gc_topo_thread_centric" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG gc_topo_warp_centric \
  "${GRAPHBIG_GPU}/gpu_GraphColoring/gc_topo_warp_centric" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG sssp_data_thread_centric \
  "${GRAPHBIG_GPU}/gpu_SSSP/sssp_data_thread_centric" --dataset "${GRAPHBIG_DATA}" --root 31
run_case graphBIG sssp_data_warp_centric \
  "${GRAPHBIG_GPU}/gpu_SSSP/sssp_data_warp_centric" --dataset "${GRAPHBIG_DATA}" --root 31
run_case graphBIG sssp_topo_thread_centric \
  "${GRAPHBIG_GPU}/gpu_SSSP/sssp_topo_thread_centric" --dataset "${GRAPHBIG_DATA}" --root 31
run_case graphBIG sssp_topo_warp_centric \
  "${GRAPHBIG_GPU}/gpu_SSSP/sssp_topo_warp_centric" --dataset "${GRAPHBIG_DATA}" --root 31
run_case graphBIG triangle_count \
  "${GRAPHBIG_GPU}/gpu_TriangleCount/triangle_count" --dataset "${GRAPHBIG_DATA}"
run_case graphBIG kcore \
  "${GRAPHBIG_GPU}/gpu_kCore/kcore" --dataset "${GRAPHBIG_DATA}"

echo "summary=${SUMMARY}"

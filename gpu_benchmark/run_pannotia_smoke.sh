#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT}/traces/run_logs/pannotia_smoke"
SUMMARY="${OUT_DIR}/summary.tsv"
TIMEOUT="${BENCH_TIMEOUT:-120s}"
BUILD="${BUILD:-0}"

mkdir -p "${OUT_DIR}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

# shellcheck source=/dev/null
source "${ROOT}/setup_gpu_app_collection_env.sh" >/dev/null

if [[ "${BUILD}" == "1" ]]; then
  make -C "${GPUAPPS_ROOT}/src" pannotia -i -j"${JOBS:-4}"
fi

GPUAPPS_ROOT_ABS="$(cd "${GPUAPPS_ROOT}" && pwd)"
BIN="$(cd "${BINDIR}/${BINSUBDIR}" && pwd)"
DATA="${GPUAPPS_ROOT_ABS}/data_dirs/pannotia"

printf "benchmark\tstatus\texit_code\tseconds\tlog\tcommand\n" >"${SUMMARY}"

record() {
  local name="$1"
  local status="$2"
  local code="$3"
  local seconds="$4"
  local log="$5"
  shift 5
  printf "%s\t%s\t%s\t%s\t%s\t" "${name}" "${status}" "${code}" "${seconds}" "${log}" >>"${SUMMARY}"
  printf "%q " "$@" >>"${SUMMARY}"
  printf "\n" >>"${SUMMARY}"
}

run_case() {
  local name="$1"
  shift
  local log="${OUT_DIR}/${name}.log"
  local start end seconds code status

  echo "== pannotia/${name} =="
  start=$(date +%s)
  set +e
  timeout "${TIMEOUT}" "$@" >"${log}" 2>&1
  code=$?
  set -e
  end=$(date +%s)
  seconds=$((end - start))

  if [[ "${code}" -eq 0 ]]; then
    status="PASS"
  elif [[ "${code}" -eq 124 ]]; then
    status="TIMEOUT"
  else
    status="FAIL"
  fi

  record "${name}" "${status}" "${code}" "${seconds}" "${log}" "$@"
  tail -n 5 "${log}" || true
}

run_case bc "${BIN}/bc" "${DATA}/bc/data/1k_128k.gr"
run_case color_max "${BIN}/color_max" "${DATA}/color_max/data/G3_circuit.graph" 1
run_case color_maxmin "${BIN}/color_maxmin" "${DATA}/color_maxmin/data/G3_circuit.graph" 1
run_case fw "${BIN}/fw" "${DATA}/fw/data/256_16384.gr"
run_case fw_block "${BIN}/fw_block" "${DATA}/fw_block/data/256_16384.gr"
run_case mis "${BIN}/mis" "${DATA}/mis/data/G3_circuit.graph" 1
run_case pagerank "${BIN}/pagerank" "${DATA}/pagerank/data/coAuthorsDBLP.graph" 1
run_case pagerank_spmv "${BIN}/pagerank_spmv" "${DATA}/pagerank_spmv/data/coAuthorsDBLP.graph" 1
run_case sssp "${BIN}/sssp" "${DATA}/sssp/data/USA-road-d.NY.gr" 0
run_case sssp_ell "${BIN}/sssp_ell" "${DATA}/sssp_ell/data/USA-road-d.NY.gr" 0

echo "summary=${SUMMARY}"

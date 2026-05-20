#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NOARG_SUMMARY="${ROOT}/traces/run_logs/gpu_app_collection_all_noarg/summary.tsv"
OUT_DIR="${ROOT}/traces/run_logs/gpu_app_collection_usage_args"
SUMMARY="${OUT_DIR}/summary.tsv"
TIMEOUT="${BENCH_TIMEOUT:-10s}"
mkdir -p "${OUT_DIR}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

# shellcheck source=/dev/null
source "${ROOT}/scripts/setup_gpu_app_collection_env.sh" >/dev/null

printf "benchmark\tstatus\texit_code\targs\tlog\n" >"${SUMMARY}"

run_with_args() {
  local bench="$1"
  shift
  local log="${OUT_DIR}/${bench}.log"
  echo "== ${bench} $* =="
  set +e
  timeout --kill-after=2s "${TIMEOUT}" "${BINDIR}/${BINSUBDIR}/${bench}" "$@" >"${log}" 2>&1
  local code=$?
  set -e
  if [[ ${code} -eq 0 ]]; then
    status="PASS"
  elif [[ ${code} -eq 124 || ${code} -eq 137 ]]; then
    status="TIMEOUT"
  else
    status="FAIL"
  fi
  printf "%s\t%s\t%s\t" "${bench}" "${status}" "${code}" >>"${SUMMARY}"
  printf "%q " "$@" >>"${SUMMARY}"
  printf "\t%s\n" "${log}" >>"${SUMMARY}"
}

while IFS=$'\t' read -r bench status code log; do
  [[ "${bench}" == "benchmark" ]] && continue
  [[ "${status}" == "PASS" ]] && continue
  [[ ! -f "${log}" ]] && continue

  if grep -q '#iterations #cores' "${log}"; then
    run_with_args "${bench}" 1 1
  elif grep -q '#iterations' "${log}"; then
    run_with_args "${bench}" 1
  elif grep -q '<max_rows/max_cols> <penalty>' "${log}"; then
    run_with_args "${bench}" 64 10
  elif grep -q 'Usage: .*rayTracing <WIDTH> <HEIGHT>' "${log}"; then
    run_with_args "${bench}" 256 256
  fi
done <"${NOARG_SUMMARY}"

echo "summary=${SUMMARY}"

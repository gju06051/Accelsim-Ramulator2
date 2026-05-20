#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT}/traces/run_logs/gpu_app_collection_all_noarg"
SUMMARY="${OUT_DIR}/summary.tsv"
TIMEOUT="${BENCH_TIMEOUT:-5s}"
mkdir -p "${OUT_DIR}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

# shellcheck source=/dev/null
source "${ROOT}/setup_gpu_app_collection_env.sh" >/dev/null

printf "benchmark\tstatus\texit_code\tlog\n" >"${SUMMARY}"

mapfile -t BINS < <(find "${BINDIR}/${BINSUBDIR}" -maxdepth 1 -type f -perm /111 -printf '%f\n' | sort)
for bench in "${BINS[@]}"; do
  log="${OUT_DIR}/${bench}.log"
  echo "== ${bench} =="
  set +e
  timeout --kill-after=2s "${TIMEOUT}" "${BINDIR}/${BINSUBDIR}/${bench}" >"${log}" 2>&1
  code=$?
  set -e

  if [[ ${code} -eq 0 ]]; then
    status="PASS"
  elif [[ ${code} -eq 124 || ${code} -eq 137 ]]; then
    status="TIMEOUT"
  else
    status="FAIL"
  fi
  printf "%s\t%s\t%s\t%s\n" "${bench}" "${status}" "${code}" "${log}" >>"${SUMMARY}"
done

echo "summary=${SUMMARY}"

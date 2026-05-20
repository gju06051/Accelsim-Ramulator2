#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT}/traces/run_logs/gpu_app_collection_target_sweep"
SUMMARY="${OUT_DIR}/summary.tsv"
TARGET_TIMEOUT="${TARGET_TIMEOUT:-300s}"
JOBS="${JOBS:-4}"
mkdir -p "${OUT_DIR}"

# shellcheck source=/dev/null
source "${ROOT}/setup_gpu_app_collection_env.sh" >/dev/null

TARGETS=("$@")
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  TARGETS=(
    GPU_Microbenchmark
    microbench
    custom_apps
    proxy-apps
    pannotia
    parboil
    rodinia-3.1
    lonestargpu-2.0
    shoc
    accelwattch_ubench
  )
fi

printf "target\tstatus\texit_code\tbinaries_before\tbinaries_after\tnew_binaries\tlog\n" >"${SUMMARY}"

bin_list() {
  find "${BINDIR}/${BINSUBDIR}" -maxdepth 1 -type f -perm /111 -printf '%f\n' 2>/dev/null | sort
}

for target in "${TARGETS[@]}"; do
  log="${OUT_DIR}/${target}.log"
  before="$(mktemp)"
  after="$(mktemp)"
  bin_list >"${before}"

  echo "== build ${target} =="
  set +e
  timeout "${TARGET_TIMEOUT}" make -C "${GPUAPPS_ROOT}/src" "${target}" -i -j"${JOBS}" >"${log}" 2>&1
  code=$?
  set -e

  bin_list >"${after}"
  new_bins="$(comm -13 "${before}" "${after}" | paste -sd ',' -)"
  before_n="$(wc -l <"${before}")"
  after_n="$(wc -l <"${after}")"

  if [[ ${code} -eq 0 ]]; then
    status="DONE"
  elif [[ ${code} -eq 124 ]]; then
    status="TIMEOUT"
  else
    status="FAIL"
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "${target}" "${status}" "${code}" "${before_n}" "${after_n}" "${new_bins}" "${log}" >>"${SUMMARY}"
  tail -n 20 "${log}" || true
  rm -f "${before}" "${after}"
done

echo "summary=${SUMMARY}"
echo "bin_dir=${BINDIR}/${BINSUBDIR}"

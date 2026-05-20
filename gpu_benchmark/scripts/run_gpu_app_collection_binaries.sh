#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATTERN="${1:-.*}"
OUT_DIR="${ROOT}/traces/run_logs/gpu_app_collection"
mkdir -p "${OUT_DIR}"

# shellcheck source=/dev/null
source "${ROOT}/scripts/setup_gpu_app_collection_env.sh" >/dev/null

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

mapfile -t BINS < <(find "${BINDIR}/${BINSUBDIR}" -maxdepth 1 -type f -perm /111 -printf '%f\n' | sort | grep -E "${PATTERN}" || true)
if [[ ${#BINS[@]} -eq 0 ]]; then
  echo "No binaries matched pattern: ${PATTERN}" >&2
  exit 1
fi

for bin in "${BINS[@]}"; do
  log="${OUT_DIR}/${bin}.log"
  echo "== ${bin} =="
  {
    echo "## ${bin}"
    date
    "${BINDIR}/${BINSUBDIR}/${bin}"
  } >"${log}" 2>&1 || {
    echo "FAILED ${bin}; see ${log}" >&2
    tail -n 20 "${log}" >&2
    continue
  }
  tail -n 5 "${log}"
done

echo "logs=${OUT_DIR}"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS=("${@:-}")
if [[ ${#TARGETS[@]} -eq 0 || -z "${TARGETS[0]}" ]]; then
  TARGETS=(ispass-2009 parboil polybench rodinia-3.1 pannotia lonestargpu-2.0)
fi

# shellcheck source=/dev/null
source "${ROOT}/setup_gpu_app_collection_env.sh" >/dev/null

mkdir -p "${BINDIR}/${BINSUBDIR}"

for target in "${TARGETS[@]}"; do
  echo "== build ${target} =="
  make -C "${GPUAPPS_ROOT}/src" "${target}" -i -j"${JOBS:-4}"
done

echo "bin_dir=${BINDIR}/${BINSUBDIR}"
find "${BINDIR}/${BINSUBDIR}" -maxdepth 1 -type f -perm /111 -printf '%f\n' | sort

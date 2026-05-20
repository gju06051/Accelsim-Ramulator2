#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPUAPPS="${ROOT}/gpu-app-collection"
MEDIA_DATA="/media/1/gju06051/Comp/Sectored-Access-DRAM-traces/gpu-app-collection/data_dirs"

mkdir -p "$(dirname "${MEDIA_DATA}")"
mkdir -p "${MEDIA_DATA}"
if [[ ! -e "${GPUAPPS}/data_dirs" && ! -L "${GPUAPPS}/data_dirs" ]]; then
  ln -s "${MEDIA_DATA}" "${GPUAPPS}/data_dirs"
fi

bash "${GPUAPPS}/get_data.sh"
echo "data_dirs=$(readlink -f "${GPUAPPS}/data_dirs")"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RODINIA_ROOT="${ROOT}/gpu-app-collection/src/cuda/rodinia/3.1"
NN_DIR="${RODINIA_ROOT}/cuda/nn"
LUD_TOOLS_DIR="${RODINIA_ROOT}/cuda/lud/tools"
LUD_DIM="${LUD_DIM:-64}"

mkdir -p "${RODINIA_ROOT}/data/nn"
mkdir -p "${RODINIA_ROOT}/data/lud"

if [[ -e "${NN_DIR}/data" && ! -L "${NN_DIR}/data" ]]; then
  echo "Refusing to replace existing non-symlink: ${NN_DIR}/data" >&2
  exit 1
fi

ln -sfn ../../data/nn "${NN_DIR}/data"

if [[ ! -x "${NN_DIR}/hurricane_gen" || "${NN_DIR}/hurricane_gen.c" -nt "${NN_DIR}/hurricane_gen" ]]; then
  gcc -g -O3 -Wall -o "${NN_DIR}/hurricane_gen" "${NN_DIR}/hurricane_gen.c" -lm
fi

(
  cd "${NN_DIR}"
  ./gen_dataset.sh
)

make -C "${LUD_TOOLS_DIR}" gen_input
(
  cd "${RODINIA_ROOT}/data/lud"
  "${LUD_TOOLS_DIR}/gen_input" "${LUD_DIM}"
)

echo "Generated Rodinia 3.1 local inputs:"
echo "  ${RODINIA_ROOT}/data/nn/cane4_*.db"
echo "  ${RODINIA_ROOT}/data/lud/${LUD_DIM}.dat"

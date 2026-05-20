#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ACCELSIM_DIR="${ACCELSIM_DIR:-${REPO_DIR}/../gpgpu-sim_distribution}"
RAMULATOR_DIR="${RAMULATOR_DIR:-${REPO_DIR}/../ramulator2}"

echo "Integration repo: ${REPO_DIR}"
echo "Accel-Sim dir:    ${ACCELSIM_DIR}"
echo "Ramulator2 dir:   ${RAMULATOR_DIR}"

if [[ -f "${ACCELSIM_DIR}/Makefile" ]]; then
  echo "Run the Accel-Sim/GPGPU-Sim build from ${ACCELSIM_DIR} after applying overlay."
  echo "This wrapper intentionally does not guess your CUDA/toolchain environment yet."
else
  echo "error: Accel-Sim Makefile not found" >&2
  exit 1
fi

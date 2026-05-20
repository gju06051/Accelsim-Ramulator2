#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ACCELSIM_DIR="${ACCELSIM_DIR:-${REPO_DIR}/../gpgpu-sim_distribution}"
PATCH="${REPO_DIR}/overlay/accelsim/accelsim_external_backend.patch"

echo "Accel-Sim dir: ${ACCELSIM_DIR}"

if ! git -C "${ACCELSIM_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: Accel-Sim repo not found at ${ACCELSIM_DIR}" >&2
  exit 1
fi

if git -C "${ACCELSIM_DIR}" apply -R --check "${PATCH}"; then
  git -C "${ACCELSIM_DIR}" apply -R "${PATCH}"
  echo "Removed Accel-Sim external backend overlay patch."
else
  echo "Overlay patch was not applied or cannot be reversed cleanly."
fi

rm -f "${ACCELSIM_DIR}/src/gpgpu-sim/sgram_backend.h"
rm -f "${ACCELSIM_DIR}/src/gpgpu-sim/sgram_backend.cc"
echo "Removed copied bridge files."

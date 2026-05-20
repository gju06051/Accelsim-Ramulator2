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

cp "${REPO_DIR}/bridge/sgram_backend.h" \
   "${ACCELSIM_DIR}/src/gpgpu-sim/sgram_backend.h"
cp "${REPO_DIR}/bridge/sgram_backend.cc" \
   "${ACCELSIM_DIR}/src/gpgpu-sim/sgram_backend.cc"

if git -C "${ACCELSIM_DIR}" apply --check "${PATCH}"; then
  git -C "${ACCELSIM_DIR}" apply "${PATCH}"
  echo "Applied Accel-Sim external backend overlay."
else
  echo "Overlay patch does not apply cleanly. It may already be applied or the Accel-Sim tree changed." >&2
  exit 1
fi

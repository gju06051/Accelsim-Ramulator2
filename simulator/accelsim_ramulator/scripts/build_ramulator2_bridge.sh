#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RAMULATOR2_DIR="${RAMULATOR2_DIR:-${REPO_DIR}/../ramulator2}"
BUILD_DIR="${BUILD_DIR:-${REPO_DIR}/build/ramulator2_bridge}"

if [[ ! -f "${RAMULATOR2_DIR}/libramulator.so" ]]; then
  echo "error: ${RAMULATOR2_DIR}/libramulator.so not found" >&2
  echo "build Ramulator2 first, then rerun this script" >&2
  exit 1
fi

cmake -S "${REPO_DIR}/bridge" -B "${BUILD_DIR}" \
  -DRAMULATOR2_DIR="${RAMULATOR2_DIR}" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build "${BUILD_DIR}" -j"$(nproc)"

echo "built ${BUILD_DIR}/libsgram_ramulator2_bridge.so"
echo "smoke: ${BUILD_DIR}/sgram_ramulator2_bridge_smoke <ramulator2-yaml>"

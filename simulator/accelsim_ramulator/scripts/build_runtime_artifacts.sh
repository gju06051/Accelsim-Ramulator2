#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTEGRATION_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SIMULATOR_DIR="$(cd "${INTEGRATION_DIR}/.." && pwd)"
GPGPU_ROOT="${SGRAM_GPGPU_ROOT:-${SIMULATOR_DIR}/gpgpu-sim_distribution}"
RAMULATOR2_ROOT="${SGRAM_RAMULATOR2_ROOT:-${SIMULATOR_DIR}/ramulator2}"
GPGPU_BUILD="${SGRAM_GPGPU_BUILD:-${GPGPU_ROOT}/build/sgram_fixed}"
BRIDGE_BUILD="${SGRAM_BRIDGE_BUILD:-${INTEGRATION_DIR}/build/ramulator2_bridge}"
JOBS="${JOBS:-$(nproc)}"
BUILD_GPGPU=1
BUILD_RAMULATOR2=1
BUILD_BRIDGE=1

usage() {
  cat <<'USAGE'
Build the local runtime shared libraries that are intentionally not tracked:
  - simulator/gpgpu-sim_distribution/build/sgram_fixed/libcudart.so
  - simulator/ramulator2/libramulator.so
  - simulator/accelsim_ramulator/build/ramulator2_bridge/libsgram_ramulator2_bridge.so

Usage:
  build_runtime_artifacts.sh [options]

Options:
  --jobs N             Parallel build jobs. Default: nproc or $JOBS.
  --cuda PATH          CUDA toolkit root, for example /usr/local/cuda-12.3.
  --skip-gpgpu         Do not rebuild AccelSim/GPGPU-Sim libcudart.so.
  --skip-ramulator2    Do not rebuild Ramulator2 libramulator.so.
  --skip-bridge        Do not rebuild the AccelSim-Ramulator2 bridge.
  -h, --help           Show this help.

Environment overrides:
  SGRAM_GPGPU_ROOT, SGRAM_RAMULATOR2_ROOT, SGRAM_GPGPU_BUILD, SGRAM_BRIDGE_BUILD
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jobs)
      JOBS="$2"
      shift 2
      ;;
    --cuda)
      export CUDA_INSTALL_PATH="$2"
      shift 2
      ;;
    --skip-gpgpu)
      BUILD_GPGPU=0
      shift
      ;;
    --skip-ramulator2)
      BUILD_RAMULATOR2=0
      shift
      ;;
    --skip-bridge)
      BUILD_BRIDGE=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_dir() {
  local path="$1"
  local label="$2"
  if [[ ! -d "${path}" ]]; then
    echo "error: ${label} not found: ${path}" >&2
    exit 1
  fi
}

require_dir "${GPGPU_ROOT}" "GPGPU-Sim root"
require_dir "${RAMULATOR2_ROOT}" "Ramulator2 root"

if [[ "${BUILD_GPGPU}" -eq 1 ]]; then
  if [[ -z "${CUDA_INSTALL_PATH:-}" ]]; then
    if command -v nvcc >/dev/null 2>&1; then
      CUDA_INSTALL_PATH="$(cd "$(dirname "$(command -v nvcc)")/.." && pwd)"
      export CUDA_INSTALL_PATH
    elif [[ -d /usr/local/cuda ]]; then
      export CUDA_INSTALL_PATH=/usr/local/cuda
    else
      echo "error: CUDA_INSTALL_PATH is not set and nvcc was not found" >&2
      echo "       pass --cuda /path/to/cuda or export CUDA_INSTALL_PATH" >&2
      exit 1
    fi
  fi

  echo "[1/3] Building AccelSim/GPGPU-Sim runtime in ${GPGPU_BUILD}"
  cmake -S "${GPGPU_ROOT}" -B "${GPGPU_BUILD}" -DCMAKE_BUILD_TYPE=Release
  cmake --build "${GPGPU_BUILD}" -j"${JOBS}" --target cudart
  ln -sfn libcudart.so "${GPGPU_BUILD}/libcudart.so.12"
else
  echo "[1/3] Skipping AccelSim/GPGPU-Sim runtime build"
fi

if [[ "${BUILD_RAMULATOR2}" -eq 1 ]]; then
  echo "[2/3] Building Ramulator2 runtime in ${RAMULATOR2_ROOT}/build"
  cmake -S "${RAMULATOR2_ROOT}" -B "${RAMULATOR2_ROOT}/build" -DCMAKE_BUILD_TYPE=Release
  cmake --build "${RAMULATOR2_ROOT}/build" -j"${JOBS}" --target ramulator
else
  echo "[2/3] Skipping Ramulator2 runtime build"
fi

if [[ "${BUILD_BRIDGE}" -eq 1 ]]; then
  echo "[3/3] Building AccelSim-Ramulator2 bridge in ${BRIDGE_BUILD}"
  RAMULATOR2_DIR="${RAMULATOR2_ROOT}" BUILD_DIR="${BRIDGE_BUILD}" \
    "${INTEGRATION_DIR}/scripts/build_ramulator2_bridge.sh"
else
  echo "[3/3] Skipping bridge build"
fi

echo
echo "Runtime artifacts ready:"
echo "  ${GPGPU_BUILD}/libcudart.so"
echo "  ${RAMULATOR2_ROOT}/libramulator.so"
echo "  ${BRIDGE_BUILD}/libsgram_ramulator2_bridge.so"

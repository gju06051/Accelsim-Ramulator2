#!/usr/bin/env bash
# Source this file before manually building gpu-app-collection targets.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPUAPPS="${ROOT}/gpu-app-collection"

export CUDA_INSTALL_PATH="${CUDA_INSTALL_PATH:-/usr/local/cuda-12.3}"
export CUDAHOSTCXX="${CUDAHOSTCXX:-/usr/bin/g++-11}"
export PATH="${CUDA_INSTALL_PATH}/bin:${PATH}"
export NVCC_PREPEND_FLAGS="${NVCC_PREPEND_FLAGS:--ccbin ${CUDAHOSTCXX}}"

# setup_environment tries to fetch the CUDA 4.2 SDK when this directory is
# absent. The modern CUDA 12 build targets we use do not need it.
mkdir -p "${GPUAPPS}/4.2"

# shellcheck source=/dev/null
source "${GPUAPPS}/src/setup_environment"

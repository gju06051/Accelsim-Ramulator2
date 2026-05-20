#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CUDA_INSTALL_PATH="${CUDA_INSTALL_PATH:-/usr/local/cuda-12.3}"

mkdir -p "${ROOT}/footprint_tracer/build"
g++ -std=c++17 -O2 -fPIC -shared \
  -I"${CUDA_INSTALL_PATH}/include" \
  "${ROOT}/footprint_tracer/cuda_footprint_tracer.cpp" \
  -ldl -pthread \
  -o "${ROOT}/footprint_tracer/build/libcuda_footprint_tracer.so"

echo "${ROOT}/footprint_tracer/build/libcuda_footprint_tracer.so"

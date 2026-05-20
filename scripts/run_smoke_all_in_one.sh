#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export SGRAM_WORKSPACE_ROOT="$ROOT"
export SGRAM_GPU_BENCHMARK_ROOT="$ROOT/gpu_benchmark"
export SGRAM_GPGPU_ROOT="$ROOT/simulator/gpgpu-sim_distribution"
export SGRAM_RAMULATOR2_ROOT="$ROOT/simulator/ramulator2"
export SGRAM_GPGPU_BUILD="$ROOT/simulator/gpgpu-sim_distribution/build/sgram_fixed"

cd "$ROOT/simulator/accelsim_ramulator"

python3 ./scripts/run_fixed_backend_matrix.py \
  --backend fixed \
  --preset stackganged_operational \
  --benchmarks micro_l1_access_grain \
  --latencies 1 \
  --queue-limits 32 \
  --config-variant a100_1stack \
  --a100-l2-8mb \
  --max-cycle 100 \
  --timeout 60 \
  --jobs 1 \
  --out-dir results/all_in_one_fixed_smoke

# Accel-Sim + Ramulator Integration for SG-HBM

This repository contains the distributable integration layer for connecting
Accel-Sim/GPGPU-Sim with Ramulator2 for StackGanged / SG-HBM experiments.

The simulator repositories themselves are kept outside this repo as sibling
submodules of the top-level StackGanged project:

```text
StackGanged/
  simulator/
    gpgpu-sim_distribution/   # Accel-Sim/GPGPU-Sim fork
    ramulator2/               # Ramulator2 fork
    accelsim_ramulator/       # this integration repo
```

For deployment outside the top-level `StackGanged` tree, keep this repository
independent and point it at the local simulator and benchmark trees with:

```bash
export SGRAM_WORKSPACE_ROOT=/path/to/workspace
export SGRAM_GPU_BENCHMARK_ROOT=/path/to/gpu_benchmark
export SGRAM_GPGPU_ROOT=/path/to/gpgpu-sim_distribution
export SGRAM_RAMULATOR2_ROOT=/path/to/ramulator2
export SGRAM_GPGPU_BUILD=/path/to/gpgpu-sim_distribution/build/sgram_fixed
```

## Rule

Do not make integration changes directly in the simulator submodules unless the
change belongs to that simulator itself. Integration-specific code, build glue,
patches, overlays, and experiment scripts live here.

## Planned Flow

1. Keep `../gpgpu-sim_distribution` and `../ramulator2` clean.
2. Store Accel-Sim overlay patches in `overlay/accelsim`.
3. Store bridge code in `bridge`.
4. Apply overlays only for experiment builds.
5. Run HBM4 baseline first, then SG-HBM modes.

## Current Scaffolding

The first Accel-Sim overlay adds an external memory backend hook and a fixed
latency backend named `sgram_backend_t`.

Apply it from this repo:

```bash
./scripts/apply_overlay.sh
```

Enable the scaffolding backend at runtime:

```bash
export SGRAM_BACKEND=fixed
export SGRAM_FIXED_LATENCY=100
```

Build the Ramulator2 C bridge:

```bash
./scripts/build_ramulator2_bridge.sh
```

Enable the Ramulator2 HBM4 backend:

```bash
export SGRAM_BACKEND=ramulator2
export SGRAM_RAMULATOR_LIB=$PWD/build/ramulator2_bridge/libsgram_ramulator2_bridge.so
export SGRAM_RAMULATOR_CONFIG=$PWD/configs/ramulator/hbm4.yaml
export SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT=32
export SGRAM_QUEUE_LIMIT=32
```

The Ramulator2 bridge is built as a separate shared library so the
Accel-Sim/GPGPU-Sim C++17 build does not directly include or link Ramulator2's
C++20 headers.

Remove the overlay when done:

```bash
./scripts/remove_overlay.sh
```

The fixed backend is not a performance model. It only validates the integration
path:

```text
Accel-Sim memory partition -> external backend -> completion return queue
```

The Ramulator2 backend uses the same path, but issues accepted requests into a
shared Ramulator2 `Frontend=GEM5` + `MemorySystem=GenericDRAM` instance. Writes
are returned to Accel-Sim after Ramulator2 accepts them, matching the practical
behavior of the older GPGPUSim-Ramulator integration where write callbacks were
not invoked by Ramulator.

Reference and validation notes:

- `docs/gpgpusim_ramulator_reference.md`
- `docs/accelsim_hms_reference.md`
- `docs/ramulator2_backend_validation.md`

Benchmark operation files:

- `benchmarks/operational_manifest.tsv`: validated 92-benchmark operational set
- `benchmarks/exclusions.md`: benchmarks excluded due to AccelSim compatibility
- `benchmarks/README.md`: manifest usage and deployment notes

List the packaged operational benchmark set:

```bash
./scripts/run_fixed_backend_matrix.py --list-benchmarks
```

Run the default operational preset:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset stackganged_operational \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_1stack \
  --config-overrides '-gpgpu_memory_partition_indexing 2' \
  --a100-l2-8mb \
  --max-cycle 50000 \
  --jobs 32 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/operational_smoke
```

## Milestones

- M1: identify the Accel-Sim DRAM boundary and create a fixed-latency external backend stub. [scaffolded]
- M2: link a minimal Ramulator2 wrapper and issue requests from the backend. [scaffolded]
- M3: return completions to Accel-Sim memory partitions. [scaffolded]
- M4: validate HBM4 baseline timing and queue behavior. [smoke-tested]
- M5: add SG-HBM timing modes and experiment scripts.

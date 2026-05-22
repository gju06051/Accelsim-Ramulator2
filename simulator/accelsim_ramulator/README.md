# AccelSim + Ramulator2 Integration Layer

This directory contains the integration layer that connects AccelSim/GPGPU-Sim
memory partitions to Ramulator2. It is the main implementation area for this
repository: bridge code, AccelSim overlay patches, Ramulator2 configs,
validation scripts, benchmark runners, and notes live here.

The all-in-one checkout places the integration layer next to the simulator
trees it drives:

```text
Accelsim-Ramulator/
  simulator/
    gpgpu-sim_distribution/   # Accel-Sim/GPGPU-Sim fork
    ramulator2/               # Ramulator2 fork
    accelsim_ramulator/       # this integration repo
```

For another deployment layout, point the runner at the local simulator and
benchmark trees with:

```bash
export SGRAM_WORKSPACE_ROOT=/path/to/workspace
export SGRAM_GPU_BENCHMARK_ROOT=/path/to/gpu_benchmark
export SGRAM_GPGPU_ROOT=/path/to/gpgpu-sim_distribution
export SGRAM_RAMULATOR2_ROOT=/path/to/ramulator2
export SGRAM_GPGPU_BUILD=/path/to/gpgpu-sim_distribution/build/sgram_fixed
```

The `SGRAM_*` prefix and `sgram_backend_t` type name are legacy/internal names
for the external memory-backend hook. The functional goal is AccelSim +
Ramulator2 co-simulation.

## Development Boundary

Keep integration-specific code here when possible:

- AccelSim patch/overlay glue lives in `overlay/accelsim`.
- Ramulator2 C API bridge code lives in `bridge`.
- Runtime configs live in `configs`.
- Experiment and smoke runners live in `scripts`.
- Benchmark manifests live in `benchmarks`.

Only edit `../gpgpu-sim_distribution` or `../ramulator2` directly when the
change genuinely belongs to that simulator rather than the integration layer.

## Backend Flow

The AccelSim overlay adds an external memory backend hook and a fixed-latency
backend named `sgram_backend_t`.

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
export SGRAM_RAMULATOR_CONFIG=$PWD/configs/ramulator/a100_hbm2e_5stack.yaml
export SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT=5120
export SGRAM_QUEUE_LIMIT=128
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
AccelSim memory partition -> external backend -> completion return queue
```

The Ramulator2 backend uses the same path, but issues accepted requests into a
shared Ramulator2 `Frontend=GEM5` + `MemorySystem=GenericDRAM` instance. Writes
are returned to AccelSim after Ramulator2 accepts them, matching the practical
behavior of the older GPGPUSim-Ramulator integration where write callbacks were
not invoked by Ramulator.

Reference and validation notes:

- `docs/gpgpusim_ramulator_reference.md`
- `docs/accelsim_hms_reference.md`
- `docs/ramulator2_backend_validation.md`

Benchmark operation files:

- `benchmarks/operational_manifest.tsv`: validated 92-benchmark operational set
- `benchmarks/exclusions.md`: benchmarks excluded for AccelSim compatibility
- `benchmarks/README.md`: manifest usage and deployment notes

List the packaged operational benchmark set:

```bash
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

Run the operational preset:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_5stack \
  --ramulator-config configs/ramulator/a100_hbm2e_5stack.yaml \
  --max-cycle 50000 \
  --jobs 32 \
  --ramulator-inflight-read-limit auto \
  --out-dir results/operational_smoke
```

The preset name `stackganged_operational` is kept for compatibility with earlier
scripts. New runs should normally start from `accelsim_ramulator_main`.

By default, `--ramulator-ticks-per-dram-cycle auto` derives the Ramulator tick
ratio from AccelSim's DRAM clock and Ramulator2 `tCK`. With `--backend
ramulator2`, each positive `--queue-limits` value is applied both to AccelSim's
`SGRAM_QUEUE_LIMIT` and to the per-run Ramulator2 `read_buffer_size` /
`write_buffer_size`; `--ramulator-inflight-read-limit auto` then resolves to
`channels * read_buffer_size`. The effective Ramulator buffer sizes and inflight
limit are recorded in `summary.csv`.

The runner also enables GPGPU-Sim host timing metrics in `summary.csv`; use
`--gpgpusim-host-timing off` to disable that instrumentation. Ramulator finalize
stats are enabled by default for `--backend ramulator2` so row-buffer and latency
metrics are populated when the run exits cleanly. Wall-clock timeout is disabled
by default; pass `--timeout <seconds>` for bounded smoke runs.

The runner profiles core-side memory granularity after coalescing by default:

```bash
--core-granularity-profile on
```

Each run directory will contain `core_granularity_profile.csv`, aggregated by
PC, access type, access size, useful bytes, active lanes, and per-lane byte
width. The top-level `summary.csv` also includes ratios such as useful-8B,
useful-32B, lane-4B, lane-8B, and overall sector efficiency.
Use `--core-granularity-profile off` to disable this instrumentation.

For ad hoc binary runs without the matrix runner, set
`SGRAM_CORE_GRANULARITY_PROFILE=1`; optionally set
`SGRAM_CORE_GRANULARITY_PROFILE_FILE=/path/to/core_granularity_profile.csv`.

Config selection notes:

- `docs/configuration.md`: how to swap AccelSim and Ramulator2 config files
- `configs/accelsim/README.md`: AccelSim base config and override fragments
- `configs/ramulator/README.md`: Ramulator2 YAML choices, including A100 HBM2e

## Milestones

- M1: identify the Accel-Sim DRAM boundary and create a fixed-latency external backend stub. [scaffolded]
- M2: link a minimal Ramulator2 wrapper and issue requests from the backend. [scaffolded]
- M3: return completions to Accel-Sim memory partitions. [scaffolded]
- M4: validate HBM4 baseline timing and queue behavior. [smoke-tested]
- M5: add additional Ramulator2 memory-mode configs and experiment scripts.

# AccelSim + Ramulator2 Integration Bundle

This repository packages an AccelSim/GPGPU-Sim and Ramulator2 integration in one
checkout. The main purpose is to run CUDA workloads in AccelSim while routing
memory requests through a Ramulator2-backed external memory backend.

The repository vendors the simulator sources, the integration bridge, runtime
libraries, helper scripts, and a validated benchmark manifest. Some historical
script and environment names still use `sgram`; treat those as internal/legacy
names for the memory-backend hook, not as the identity of this repository.

The checkout layout is:

```text
Accelsim-Ramulator/
  simulator/
    gpgpu-sim_distribution/   # AccelSim/GPGPU-Sim source tree
    ramulator2/               # Ramulator2 source tree and runtime library
    accelsim_ramulator/       # bridge, overlays, configs, docs, runners
  gpu_benchmark/
    scripts/                  # benchmark build/run/trace helpers
  scripts/                    # top-level layout checks and smoke tests
  tools/                      # optional NVBit tooling used by trace helpers
```

## What Is Included

- AccelSim/GPGPU-Sim source plus the packaged `build/sgram_fixed/libcudart.so`
  runtime library used by the smoke runner.
- Ramulator2 source plus the packaged `libramulator.so` runtime library.
- AccelSim + Ramulator2 bridge code, overlay patch, configs, docs, and matrix
  runner under `simulator/accelsim_ramulator`.
- Operational benchmark manifest with 92 validated benchmarks.
- Benchmark release binaries and the small input/data files referenced by the
  operational manifest.
- NVBit tooling used by optional memory-trace helper scripts.

## What Is Not Included

- Generated CMake build trees, object files, and intermediate build products.
- NVBit trace dumps.
- Ramulator replay outputs.
- AccelSim result logs.
- Large unused benchmark datasets such as Tango/AlexNet and large GraphBIG
  datasets.

## Quick Check

List the packaged benchmark set:

```bash
./scripts/check_all_in_one.py
```

Run a tiny fixed-backend smoke test:

```bash
./scripts/run_smoke_all_in_one.sh
```

Run the operational Ramulator2 smoke sweep:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset stackganged_operational \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_1stack \
  --config-overrides '-gpgpu_memory_partition_indexing 2' \
  --a100-l2-8mb \
  --max-cycle 50000 \
  --timeout 240 \
  --jobs 32 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/operational_smoke
```

For full runs that need Ramulator2 internal stats, use `--max-cycle 0`. The
runner default `--ramulator-finalize-stats auto` keeps bounded smoke runs stable
and enables Ramulator2 stats for unbounded runs.

## Environment

The helper scripts set these paths automatically for this all-in-one layout:

```bash
export SGRAM_WORKSPACE_ROOT=$PWD
export SGRAM_GPU_BENCHMARK_ROOT=$PWD/gpu_benchmark
export SGRAM_GPGPU_ROOT=$PWD/simulator/gpgpu-sim_distribution
export SGRAM_RAMULATOR2_ROOT=$PWD/simulator/ramulator2
export SGRAM_GPGPU_BUILD=$PWD/simulator/gpgpu-sim_distribution/build/sgram_fixed
```

If you move components elsewhere, set the same variables manually before using
`simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py`.

`SGRAM_*` is the current environment-variable prefix used by the bridge and
runner. It is kept for compatibility with the existing code path.

## Benchmark Set

The canonical AccelSim + Ramulator2 operational manifest is:

```text
simulator/accelsim_ramulator/benchmarks/operational_manifest.tsv
```

It contains 92 validated benchmarks:

| Class | Count |
| --- | ---: |
| Streaming | 22 |
| Mixed-locality | 27 |
| Irregular | 43 |

Known incompatible candidates are documented in:

```text
simulator/accelsim_ramulator/benchmarks/exclusions.md
```

The runner preset is still named `stackganged_operational` for compatibility
with earlier scripts, but it refers to the AccelSim + Ramulator2 operational
benchmark set above.

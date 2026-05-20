# StackGanged All-In-One Artifact

This repository is a self-contained StackGanged / SG-HBM artifact bundle.  It
vendors the simulator sources, the AccelSim + Ramulator2 bridge, and the
validated benchmark binaries and inputs needed by the operational benchmark
manifest.

The intended checkout layout is:

```text
StackGanged-AllInOne/
  simulator/
    gpgpu-sim_distribution/
    ramulator2/
    accelsim_ramulator/
  gpu_benchmark/
  scripts/
```

## What Is Included

- AccelSim/GPGPU-Sim source and the local `build/sgram_fixed` runtime library
  used by the SG-HBM experiments.
- Ramulator2 source and runtime library.
- AccelSim + Ramulator2 integration repo with the Ramulator2 bridge, configs,
  docs, and runner.
- Operational benchmark manifest with 92 validated benchmarks.
- Benchmark release binaries and the small input/data files referenced by the
  operational manifest.

## What Is Not Included

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

The helper scripts set these paths automatically for the all-in-one layout:

```bash
export SGRAM_WORKSPACE_ROOT=$PWD
export SGRAM_GPU_BENCHMARK_ROOT=$PWD/gpu_benchmark
export SGRAM_GPGPU_ROOT=$PWD/simulator/gpgpu-sim_distribution
export SGRAM_RAMULATOR2_ROOT=$PWD/simulator/ramulator2
export SGRAM_GPGPU_BUILD=$PWD/simulator/gpgpu-sim_distribution/build/sgram_fixed
```

If you move components elsewhere, set the same variables manually before using
`simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py`.

## Benchmark Set

The canonical manifest is:

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

# Benchmark Manifests

This directory contains the benchmark metadata that is safe to distribute with
the AccelSim + Ramulator2 integration repo.

It intentionally does not include benchmark source trees, binaries, datasets, or
generated traces. Those stay outside this repo and are referenced through
environment variables.

## Files

| File | Purpose |
| --- | --- |
| `operational_manifest.tsv` | Canonical validated benchmark list for AccelSim + Ramulator2 runs |
| `operational_manifest_notes.md` | Source, class, suite, and validation notes for the manifest |
| `exclusions.md` | Benchmarks excluded from the operational set and the reason for exclusion |

## Operational Set

The operational manifest currently has 92 benchmarks:

| Class | Count |
| --- | ---: |
| Streaming | 22 |
| Mixed-locality | 27 |
| Irregular | 43 |

| Suite | Count |
| --- | ---: |
| polybench | 15 |
| graphBIG | 17 |
| ispass-2009 | 7 |
| rodinia | 13 |
| proxy-apps | 2 |
| microbench | 15 |
| parboil | 6 |
| lonestar | 5 |
| pannotia | 8 |
| dragon-li | 4 |

## Expected External Tree

By default, the runner assumes the integration repo is placed under a workspace
like this:

```text
Accelsim-Ramulator/
  gpu_benchmark/
  simulator/
    accelsim_ramulator/
    gpgpu-sim_distribution/
    ramulator2/
```

For a different deployment layout, set:

```bash
export SGRAM_WORKSPACE_ROOT=/path/to/workspace
export SGRAM_GPU_BENCHMARK_ROOT=/path/to/gpu_benchmark
export SGRAM_GPGPU_ROOT=/path/to/gpgpu-sim_distribution
export SGRAM_RAMULATOR2_ROOT=/path/to/ramulator2
export SGRAM_GPGPU_BUILD=/path/to/gpgpu-sim_distribution/build/sgram_fixed
```

## Runner Preset

The operational runner preset is still named `stackganged_operational` for
compatibility with earlier scripts. It loads
`benchmarks/operational_manifest.tsv`.

List the distributable benchmark set without requiring an AccelSim build:

```bash
./scripts/run_fixed_backend_matrix.py --list-benchmarks
```

Run a bounded smoke on the operational set:

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
  --timeout 240 \
  --jobs 32 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/operational_smoke
```

For full runs where Ramulator2 internal row-buffer and queue stats are needed,
use `--max-cycle 0`. The default `--ramulator-finalize-stats auto` keeps
bounded smoke runs stable and enables Ramulator2 stats for unbounded runs.

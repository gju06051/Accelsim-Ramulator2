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
| `final_manifest.tsv` | Smaller application benchmark set recommended for routine sweeps |
| `final_manifest_notes.md` | Selection policy and family-level de-duplication notes for the final set |
| `exclusions.md` | Benchmarks excluded from the operational set and the reason for exclusion |

## Operational Set

The operational manifest currently has 91 benchmarks:

| Class | Count |
| --- | ---: |
| Streaming | 22 |
| Mixed-locality | 27 |
| Irregular | 42 |

| Suite | Count |
| --- | ---: |
| polybench | 15 |
| graphBIG | 17 |
| ispass-2009 | 7 |
| rodinia | 12 |
| proxy-apps | 2 |
| microbench | 15 |
| parboil | 6 |
| lonestar | 5 |
| pannotia | 8 |
| dragon-li | 4 |

## Final Representative Set

The final manifest has 36 application benchmarks selected from the operational
pool. It keeps all major application suites represented, removes near-duplicate
variants, and avoids current-repo input/problem cases found during validation.
Synthetic microbenchmarks live in
`gpu_benchmark/benchmarks/system/manifest.tsv`.

| Class | Count |
| --- | ---: |
| Streaming | 8 |
| Mixed-locality | 15 |
| Irregular | 13 |

| Suite | Count |
| --- | ---: |
| polybench | 7 |
| graphBIG | 5 |
| ispass-2009 | 3 |
| rodinia | 6 |
| proxy-apps | 2 |
| parboil | 4 |
| lonestar | 2 |
| pannotia | 5 |
| dragon-li | 2 |

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

## Runner Presets

The recommended user-facing preset is `accelsim_ramulator_main`. It loads
`gpu_benchmark/benchmarks/main/manifest.tsv`, so local benchmark additions can
be made without editing the simulator tree. The frozen application subset is
available as `accelsim_ramulator_final`, the microbenchmark sanity-check set is
available as `accelsim_ramulator_system_check`, and the broader validated pool
is available as `accelsim_ramulator_operational`. Legacy `stackganged_*` preset
names remain for compatibility with earlier scripts.

List the final benchmark set without requiring an AccelSim build:

```bash
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

Run a bounded smoke on the final set:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_1stack \
  --config-overrides '-gpgpu_memory_partition_indexing 2' \
  --a100-l2-8mb \
  --max-cycle 50000 \
  --timeout 240 \
  --jobs 32 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --out-dir results/operational_smoke
```

For full runs where Ramulator2 internal row-buffer and queue stats are needed,
use `--max-cycle 0`. The default `--ramulator-finalize-stats on` enables
Ramulator2 stats for runs that exit cleanly.

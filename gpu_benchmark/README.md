# GPU Benchmark Workspace

This tree contains the CUDA benchmark binaries, datasets, helper scripts, and
benchmark manifests used by the AccelSim + Ramulator2 integration.

## Layout

| Path | Purpose |
| --- | --- |
| `benchmarks/main/` | User-facing benchmark set used by `accelsim_ramulator_main` |
| `benchmarks/main/manifest.tsv` | Default main run list |
| `benchmarks/main/local/` | Place new local benchmark directories here |
| `benchmarks/inventory/` | Archived TSV inventories from benchmark bring-up |
| `common/gpu-app-collection-harness/` | Built gpu-app-collection binaries and shared datasets |
| `suites/graphBIG/` | GraphBIG GPU benchmarks and staged graph datasets |
| `scripts/` | Build, smoke, trace, and classification helpers |
| `docs/` | Historical notes, suite audits, footprint notes, and exclusions |
| `generated_inputs/` | Small generated inputs used by specific workloads |
| `footprint_tracer/` | CUDA footprint tracer source |

The heavy source/binary/data locations under `common/` and `suites/` are kept
stable because manifests and runner scripts point at those paths.

## Main Benchmark Set

The routine AccelSim + Ramulator2 benchmark list is:

```text
benchmarks/main/manifest.tsv
```

List it from the repository root:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

Run one added benchmark by name:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks my_benchmark \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000
```

See `benchmarks/README.md` for the benchmark-addition workflow.

## Graph Inputs

The main graph rows are intentionally larger than the original sample inputs:

| Suite | Main input | Notes |
| --- | --- | --- |
| GraphBIG | `suites/graphBIG/dataset/LDBC_100k` | Used by all five main GraphBIG rows. BFS/SSSP rows start from high-degree root `90628`. |
| LonestarGPU | `common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr` | Generated deterministic RMAT medium graph in the Galois/Lonestar `.gr` binary format. |

`benchmarks/main/manifest.graph_medium_large.tsv` keeps extra GraphBIG
`LDBC_1000k` and Lonestar `rmat20.sym.gr` validation rows. The large datasets
are staged locally and ignored by Git. See
`benchmarks/main/GRAPH_INPUTS.md` for the argument table and generation notes.

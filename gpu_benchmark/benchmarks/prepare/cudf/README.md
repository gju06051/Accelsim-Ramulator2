# cuDF Prepared Microbenchmarks

This directory contains optional RAPIDS cuDF microbenchmarks for profiling
libcudf GPU work with Nsight Compute. They are intentionally Python-based and
not part of the default CUDA build because this workspace does not bundle
RAPIDS.

## Operations

| Operation | cuDF surface | GPU behavior to isolate |
| --- | --- | --- |
| `filter` | boolean mask + row gather | predicate evaluation and compaction |
| `project` | column arithmetic | elementwise libcudf transform kernels |
| `groupby` | `DataFrame.groupby(...).agg(...)` | hash/group aggregation |
| `join` | `DataFrame.merge(...)` | hash join build/probe and gather |
| `sort` | `DataFrame.sort_values(...)` | radix/sort pipeline and shuffles |

The benchmark builds deterministic numeric columns on the host and copies them
to a cuDF DataFrame before profiling. When `--profile-operation-only` is used,
it calls `cudaProfilerStart/Stop` around only the selected cuDF operation, so
Nsight Compute can exclude input construction and Python setup.

## TPC-H-Style Queries

`cudf_tpch_bench.py` contains thin native-cuDF query workloads over synthetic
TPC-H-like tables:

| Query | Shape | Main cuDF kernels |
| --- | --- | --- |
| `q1` | pricing summary | filter, projection, groupby aggregation, sort |
| `q3` | shipping priority | customer/orders/lineitem joins, revenue aggregation, top-k sort |
| `q6` | revenue scan | selective filter and reduction |
| `q10` | returned item reporting | orders/lineitem/customer/nation joins, aggregation, top-k sort |

These are not a compliance implementation of TPC-H. They are compact,
deterministic query-shaped workloads intended for profiler-scoped NCU and
Accel-Sim trace generation.

## Smoke Run

This workspace has a local RAPIDS venv at
`/home/gju06051/.venvs/rapids-cudf-cu12`. Run directly with that Python, or let
`run_cudf_ncu_ablation.py` auto-detect it.

```bash
/home/gju06051/.venvs/rapids-cudf-cu12/bin/python \
  gpu_benchmark/benchmarks/prepare/cudf/cudf_microbench.py \
  --op groupby --target-bytes 32MiB --iters 1 --warmup 1

/home/gju06051/.venvs/rapids-cudf-cu12/bin/python \
  gpu_benchmark/benchmarks/prepare/cudf/cudf_tpch_bench.py \
  --query q3 --target-bytes 32MiB --iters 1 --warmup 1
```

## Nsight Compute Sweep

```bash
python gpu_benchmark/scripts/run_cudf_ncu_ablation.py \
  --out-dir results/cudf_ncu_2m_to_512m \
  --ops filter project groupby join sort \
  --sizes 2MiB 4MiB 8MiB 16MiB 32MiB 64MiB 128MiB 256MiB 512MiB \
  --gpu 0
```

The summary reports L1/L2 hit rates, DRAM read/write/input, total DRAM/input,
IPC, and profiled kernel count for the profiler-scoped cuDF operation.

## Accel-Sim Trace Generation

Use the Accel-Sim NVBit tracer for simulator-ready SASS traces:

```bash
python3 gpu_benchmark/scripts/run_cudf_accelsim_trace.py \
  --op project --size 256KiB --out-dir results/cudf_accelsim_traces --gpu 0
```

This traces only the `cudaProfilerStart/Stop` region in `cudf_microbench.py`.
See `ACCELSIM_TRACE_NOTES.md` for details.

For a TPC-H-style query trace:

```bash
python3 gpu_benchmark/scripts/run_cudf_accelsim_trace.py \
  --workload tpch --query q3 --size 256KiB \
  --out-dir results/cudf_tpch_accelsim_traces --gpu 0
```

## Memory-Intensive Trace Set

The current main manifest uses small cuDF micro traces and 64 MiB TPC-H traces.
For H100 1/5-stack memory-pressure studies, regenerate larger profiler-scoped
traces before promoting cuDF rows:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py \
  --skip-nvcomp \
  --cudf-micro-size 64MiB \
  --cudf-tpch-size 128MiB
```

The helper writes
`gpu_benchmark/benchmarks/main/trace_manifest.memory_intensive.tsv`, pointing
cuDF micro rows at 64 MiB traces and TPC-H rows at 128 MiB traces. Use
`SGRAM_TRACE_MANIFEST=...` for validation first, then activate the generated
manifest only after the trace replay passes.

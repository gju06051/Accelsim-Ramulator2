# cuDF Accel-Sim Trace Notes

The goal for cuDF is to trace libcudf GPU kernels, not Python setup, host-side
data generation, DataFrame construction, H2D copies, or warmup. The prepared
cuDF benchmark therefore wraps only the selected cuDF operation with
`cudaProfilerStart/Stop`.

The Accel-Sim NVBit tracer supports that mode with:

```bash
export ACTIVE_FROM_START=0
```

When this is used, `DYNAMIC_KERNEL_RANGE` is ignored and tracing starts only
after `cudaProfilerStart()`.

## Workloads

The selected operations match common cuDF API/benchmark categories:

| Operation | cuDF surface | Kernel family |
| --- | --- | --- |
| `filter` | boolean mask + row gather | predicate evaluation and compaction |
| `project` | column arithmetic | elementwise transform kernels |
| `groupby` | `DataFrame.groupby(...).agg(...)` | hash/group aggregation |
| `join` | `DataFrame.merge(...)` | hash join build/probe and gather |
| `sort` | `DataFrame.sort_values(...)` | radix/sort pipeline and shuffles |

RAPIDS documents database-like groupby/join benchmarks for `cudf.pandas`, and
cuDF's developer benchmarking guide describes API-level benchmarks for public
features. For trace generation, we keep a deterministic standalone script
instead of invoking `pytest-benchmark`, because the simulator wants a bounded
kernel region rather than timing harness behavior.

Thin TPC-H-style query workloads are also available in `cudf_tpch_bench.py`.
They use synthetic lineitem/orders/customer/nation tables and native cuDF APIs
to exercise query-shaped GPU work:

| Query | Shape |
| --- | --- |
| `q1` | filter, projection, groupby aggregation, sort |
| `q3` | customer/orders/lineitem joins, aggregation, top-k sort |
| `q6` | filtered lineitem revenue reduction |
| `q10` | returned item joins, aggregation, top-k sort |

## Trace Generation

Generate a small trace for a single cuDF operation:

```bash
python3 gpu_benchmark/scripts/run_cudf_accelsim_trace.py \
  --op project \
  --size 256KiB \
  --out-dir results/cudf_accelsim_traces \
  --gpu 0 \
  --force
```

By default this uses:

- RAPIDS Python: `/home/gju06051/.venvs/rapids-cudf-cu12/bin/python`
- tracer: `/tmp/accel-sim-framework-dev/util/tracer_nvbit/tracer_tool/tracer_tool.so`
- postprocessor:
  `/tmp/accel-sim-framework-dev/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing`

The resulting Accel-Sim input is:

```text
results/cudf_accelsim_traces/<case>/traces/kernelslist.g
```

Generate a TPC-H-style query trace:

```bash
python3 gpu_benchmark/scripts/run_cudf_accelsim_trace.py \
  --workload tpch \
  --query q3 \
  --size 256KiB \
  --out-dir results/cudf_tpch_accelsim_traces \
  --gpu 0 \
  --force
```

## Local Smoke Result

This command was validated:

```bash
python3 gpu_benchmark/scripts/run_cudf_accelsim_trace.py \
  --op project \
  --size 256KiB \
  --out-dir results/cudf_accelsim_traces_smoke \
  --gpu 0 \
  --force
```

The profiler-scoped trace contained four `project` kernels. Warmup/setup
kernels appeared in `stats_ctx_*` with zero reported instructions and were not
included in `kernelslist.g`.

The same profiler-scoped path was also smoke-tested for all prepared cuDF
operations at 64 KiB input:

| Case | Kernels in `kernelslist.g` | Trace directory size |
| --- | ---: | ---: |
| `filter` | 7 | 220 KiB |
| `project` | 4 | 308 KiB |
| `groupby` | 12 | 3.0 MiB |
| `join` | 27 | 5.3 MiB |
| `sort` | 14 | 484 KiB |

The 1 MiB microtrace set was also generated successfully under
`results/cudf_accelsim_traces_1MiB_20260521`:

| Case | Kernels in `kernelslist.g` | Trace directory size |
| --- | ---: | ---: |
| `filter` | 7 | 2.3 MiB |
| `project` | 4 | 4.6 MiB |
| `groupby` | 12 | 69 MiB |
| `join` | 29 | 85 MiB |
| `sort` | 20 | 11 MiB |

The 256 KiB TPC-H-style query trace set was generated successfully under
`results/cudf_tpch_accelsim_traces_256KiB_20260521`:

| Case | Kernels in `kernelslist.g` | Trace directory size |
| --- | ---: | ---: |
| `q1` | 77 | 14 MiB |
| `q3` | 94 | 5.8 MiB |
| `q6` | 31 | 1.8 MiB |
| `q10` | 134 | 4.0 MiB |

## Size Guidance

NCU showed that cuDF memory behavior stabilizes roughly at:

- `filter`, `project`, `join`: around 32 MiB
- `sort`: around 64 MiB
- `groupby`: 64 MiB for DRAM/input, 128-256 MiB for slowly changing L2 behavior

Those sizes can generate very large SASS traces. For Accel-Sim bring-up, start
with 256 KiB to 1 MiB traces and then scale upward per operation. Treat small
traces as simulator-feasibility microtraces, not as final cache-locality
representatives.

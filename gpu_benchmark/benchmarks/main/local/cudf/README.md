# cuDF Main Benchmark Wrappers

These wrappers promote the prepared RAPIDS cuDF workloads into the main
benchmark manifest without requiring the default system Python to carry cuDF.
`run_cudf_bench.sh` auto-detects a RAPIDS Python or uses `RAPIDS_PYTHON` when it
is set.

The main manifest includes:

| Group | Benchmarks |
| --- | --- |
| cuDF microbenchmarks | `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_join`, `cudf_sort` |
| TPC-H-style queries | `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` |

All rows use 64MiB synthetic input and keep the query/operator region profiler
scoped in the underlying Python benchmark. For NVBit trace generation, use
`gpu_benchmark/scripts/run_cudf_accelsim_trace.py`.

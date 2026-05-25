# Benchmark Representativeness

This note records the current memory-traffic sanity checks for the main
benchmark set. It is intentionally separate from result directories: result CSVs
stay under `simulator/accelsim_ramulator/results/`, while this file records the
rules and conclusions that should survive cleanup.

## Classifier

Run the classifier from the repository root:

```bash
gpu_benchmark/scripts/classify_benchmark_representativeness.py \
  simulator/accelsim_ramulator/results/<run-name>/summary.csv
```

Useful options:

```bash
gpu_benchmark/scripts/classify_benchmark_representativeness.py \
  --only-flagged \
  simulator/accelsim_ramulator/results/<run-a>/summary.csv \
  simulator/accelsim_ramulator/results/<run-b>/summary.csv
```

Default classes:

| Class | Meaning |
| --- | --- |
| `representative` | At least 100k observed DRAM requests. |
| `moderate` | Nontrivial memory traffic below 100k DRAM requests. |
| `small` | Below 10k DRAM requests and below 50k L2 misses. |
| `tiny` | Below 1k DRAM requests and below 10k L2 misses. |
| `partition_sparse` | Uses less than half of observed memory partitions before reaching 100k requests. |
| `metric_missing` / `no_backend` / `failed` | Validation issue rather than a representative memory result. |

Bounded `MAX_CYCLE_OK` rows are provisional because the run stopped at a cycle
limit. Prefer unbounded completion for final benchmark-set decisions.

## Current H100 Trace Validation

Validated configs:

| Config | Summary |
| --- | --- |
| H100 SXM Samsung HBM3 1/5 stack, q64 | `simulator/accelsim_ramulator/results/h100_1stack_memory_trace_manifest_all_smoke_q64_j4_20260525_v1/summary.csv` |
| H100 SXM Samsung HBM3 full stack, q64 | `simulator/accelsim_ramulator/results/h100_full_memory_trace_manifest_all_smoke_q64_j4_20260525_v1/summary.csv` |

Both runs replayed `trace_manifest.memory_intensive.tsv` and started the
Ramulator2 backend for all 21 trace rows. No row had missing Ramulator metrics.

Largest rows in the current memory-intensive trace smoke:

| Group | Result |
| --- | --- |
| cuDF filter/project/sort/TPC-H q1/q3/q6/q10 | Representative in the full-stack smoke, with roughly 168k-671k DRAM requests. |
| cuDF filter/project/groupby/sort/TPC-H q1/q6/q10 | Representative or near representative in the 1/5-stack smoke, with roughly 118k-136k DRAM requests for the strongest read-heavy rows. |
| `nvcomp_ans` | Representative in both 1/5 and full-stack smoke, roughly 133k DRAM requests. |

Rows that remain too small in both 1/5 and full-stack memory-intensive smoke:

| Benchmark | Current issue |
| --- | --- |
| `nvcomp_deflate` | Tiny trace, only 16 DRAM requests observed. |
| `nvcomp_gdeflate` | Tiny trace, no DRAM request observed in the smoke. |
| `nvcomp_zstd` | Tiny trace, no DRAM request observed in the smoke. |
| `nvcomp_snappy` | Small bounded trace, roughly 3.6k DRAM requests. |
| `tango_cifarnet` | Tiny bounded trace, roughly 401 DRAM requests. |
| `tango_gru` | Small trace, roughly 3.8k DRAM requests. |
| `tango_alexnet` | Small bounded trace, roughly 5.7k-7.6k DRAM requests. |

Treat these rows as functional trace-replay coverage unless the traces are
regenerated with larger or more memory-intensive inputs.

## Graph Rows

GraphBIG and Lonestar rows use larger inputs than the original samples; see
`GRAPH_INPUTS.md` for exact arguments and generation commands.

The final GraphBIG/Lonestar representative classification should use unbounded
H100 q64 runs once they complete. Bounded validation is useful for checking that
Ramulator2 starts and metrics are present, but it can undercount long graph
rows.

Current unbounded result directories:

```text
simulator/accelsim_ramulator/results/h100_1stack_graph_main_unbounded_q64_j4_20260525_v1/
simulator/accelsim_ramulator/results/h100_full_graph_main_unbounded_q64_j4_20260525_v1/
```

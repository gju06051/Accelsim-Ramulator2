# Benchmark Representativeness

This note records the current memory-traffic sanity checks for the main
benchmark set. It is intentionally separate from result directories: result CSVs
stay under `simulator/accelsim_ramulator/results/`, while this file records the
rules and conclusions that should survive cleanup.

The primary classification below uses the H100 SXM Samsung HBM3 1/5-stack
configuration. That config exposes memory pressure most clearly because it has
fewer memory partitions and less aggregate L2 capacity than the full-stack
config.

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

The classifier reports two independent labels:

| Label | Meaning |
| --- | --- |
| `class` | Raw-size and partition-coverage class. This answers whether the run is large enough to be a stable memory-system sample. |
| `intensity_class` | Instruction-normalized memory intensity. This answers whether the benchmark is actually memory-heavy relative to its executed instructions. |

Default raw-size classes:

| Class | Meaning |
| --- | --- |
| `representative` | At least 100k observed DRAM requests. |
| `moderate` | Nontrivial memory traffic below 100k DRAM requests. |
| `small` | Below 10k DRAM requests and below 50k L2 misses. |
| `tiny` | Below 1k DRAM requests and below 10k L2 misses. |
| `partition_sparse` | Uses less than half of observed memory partitions before reaching 100k requests. |
| `metric_missing` / `no_backend` / `failed` | Validation issue rather than a representative memory result. |

Default H100 1/5-stack intensity classes:

| Intensity class | Rule |
| --- | --- |
| `high-intensity` | At least 10k DRAM requests and at least 5 DRAM requests per kilo-instruction. |
| `moderate-intensity` | At least 10k DRAM requests and 1-5 DRAM requests per kilo-instruction. |
| `low-intensity` | At least 10k DRAM requests but below 1 DRAM request per kilo-instruction. |
| `small-high-intensity` | At least 5 DRAM requests per kilo-instruction, but below 10k total DRAM requests. Dense, but too small for stable memory-system studies. |
| `small-low-intensity` | Below 10k total DRAM requests and below the high-intensity threshold. |

Bounded `MAX_CYCLE_OK` rows are provisional because the run stopped at a cycle
limit. Prefer unbounded completion for final benchmark-set decisions.

## Main-Set Exclusions

The active `manifest.tsv` excludes `polybench_fdtd2d`,
`polybench_gramschmidt`, `polybench_covariance`, and `polybench_2mm`. These
native PolyBench binaries were memory-relevant in partial H100 1/5-stack
metrics, but they became long-tail unbounded runs and cannot be shortened by a
simple manifest argument. Keep them as inventory/bounded-smoke candidates until
the PolyBench sources are restored and rebuilt with smaller problem sizes.

Synthetic `micro_*` rows are also intentionally absent from the main set. They
are system-check probes rather than representative application workloads and
live in `gpu_benchmark/benchmarks/system/manifest.tsv`.

## H100 1/5-Stack Classification

The table below uses:

```text
DRAM req/KI = DRAM requests / simulated instructions * 1000
B/inst      = DRAM requests * 32 B / simulated instructions
```

### High-Intensity Representatives

These rows are both large enough and memory-heavy on the 1/5-stack H100 SXM
configuration.

| Benchmark | Source | DRAM req/KI | B/inst | DRAM requests | Note |
| --- | --- | ---: | ---: | ---: | --- |
| `graphbig_bfs_topo_atomic` | GraphBIG unbounded | 17.39 | 0.557 | 4.55M | Strong irregular graph memory pressure. |
| `graphbig_sssp_data_warp` | GraphBIG unbounded | 12.27 | 0.393 | 2.12M | Strong irregular graph memory pressure. |
| `graphbig_bfs_data_warp` | GraphBIG unbounded | 9.83 | 0.315 | 843k | Strong irregular graph memory pressure. |
| `cudf_sort` | memory trace smoke | 6.77 | 0.217 | 134k | Bounded trace; high L2-miss density. |
| `graphbig_triangle_count` | GraphBIG unbounded | 6.63 | 0.212 | 22.9M | High on 1/5 stack; full-stack run becomes cache-sensitive and much less DRAM-intensive. |
| `nvcomp_ans` | memory trace smoke | 5.62 | 0.180 | 133k | Best nvCOMP memory-intensive trace so far. |

### Large Moderate-Intensity Rows

These rows have enough total memory traffic for stable statistics, but their
instruction-normalized memory pressure is moderate rather than high.

| Benchmark | Source | DRAM req/KI | B/inst | DRAM requests | Note |
| --- | --- | ---: | ---: | ---: | --- |
| `cudf_tpch_q3` | memory trace smoke | 2.49 | 0.080 | 114k | Bounded trace. |
| `lonestar_sssp_wln` | Lonestar unbounded | 2.41 | 0.077 | 285k | Medium RMAT input. |
| `lonestar_bfs_wlw` | Lonestar unbounded | 2.16 | 0.069 | 154k | Medium RMAT input. |
| `cudf_groupby` | memory trace smoke | 2.03 | 0.065 | 118k | Bounded trace; write-heavy in the 1/5 smoke. |
| `cudf_filter` | memory trace smoke | 1.36 | 0.044 | 136k | Bounded trace; large but not dense. |
| `cudf_tpch_q1` | memory trace smoke | 1.36 | 0.044 | 136k | Bounded trace; large but not dense. |
| `cudf_tpch_q6` | memory trace smoke | 1.36 | 0.044 | 137k | Bounded trace; large but not dense. |
| `cudf_tpch_q10` | memory trace smoke | 1.36 | 0.044 | 136k | Bounded trace; large but not dense. |
| `cudf_project` | memory trace smoke | 1.00 | 0.032 | 118k | Borderline moderate; rounded value is almost exactly 1 req/KI. |

### Medium Or Small But Dense

These are memory-dense relative to instruction count, but too small or too
bounded to be primary memory-system benchmarks.

| Benchmark | Source | DRAM req/KI | B/inst | DRAM requests | Note |
| --- | --- | ---: | ---: | ---: | --- |
| `tango_lstm` | memory trace smoke | 89.70 | 2.870 | 10.2k | Dense but small. |
| `tango_gru` | memory trace smoke | 18.12 | 0.580 | 3.8k | Dense but tiny. |
| `nvcomp_deflate` | memory trace smoke | 4.81 | 0.154 | 16 | Too tiny despite nontrivial density. |

### Moderate Or Low Priority

These are not primary memory-intensive representatives on the H100 1/5-stack
config, although some are still useful for functional trace coverage.

| Benchmark | Reason |
| --- | --- |
| `graphbig_kcore` | Moderate density, but only 43.7k DRAM requests. |
| `nvcomp_bitcomp` | Moderate density and 93.4k requests; near the large threshold but bounded. |
| `nvcomp_cascaded`, `cudf_join` | Low to moderate density and below 100k requests. |
| `nvcomp_lz4`, `nvcomp_snappy`, `nvcomp_gdeflate`, `nvcomp_zstd` | Too little observed DRAM traffic. |
| `tango_alexnet`, `tango_cifarnet` | Functional trace coverage, not memory-intensive representatives. |

## Current H100 Trace Validation

Validated configs:

| Config | Summary |
| --- | --- |
| H100 SXM Samsung HBM3 1/5 stack, q64 | `simulator/accelsim_ramulator/results/h100_1stack_memory_trace_manifest_all_smoke_q64_j4_20260525_v1/summary.csv` |
| H100 SXM Samsung HBM3 full stack, q64 | `simulator/accelsim_ramulator/results/h100_full_memory_trace_manifest_all_smoke_q64_j4_20260525_v1/summary.csv` |

Both runs replayed `trace_manifest.memory_intensive.tsv` and started the
Ramulator2 backend for all 21 trace rows. No row had missing Ramulator metrics.

Largest raw-size rows in the current memory-intensive trace smoke:

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

The GraphBIG/Lonestar representative classification above uses unbounded H100
1/5-stack q64 runs. Bounded validation is useful for checking that Ramulator2
starts and metrics are present, but it can undercount long graph rows.

Current unbounded result directories:

```text
simulator/accelsim_ramulator/results/h100_1stack_graph_main_unbounded_q64_j4_20260525_v1/
simulator/accelsim_ramulator/results/h100_full_graph_main_unbounded_q64_j4_20260525_v1/
```

# Benchmark Characterization

This file fixes the H100 SXM Samsung HBM3SID 1/5-stack q64 benchmark characterization used by `main/manifest.tsv`. The active set is intentionally not only memory-intensive: it keeps both memory-intensive and compute-intensive rows, then uses `Streaming`, `Mixed-locality`, and `Irregular` as the access-pattern axis. Rows moved to `manifest.optional.tsv` are preserved for functional coverage, but are too small or cache-fit for routine comparative studies. Known multi-hour long-tail rows are separated into `manifest.not_use.tsv`.

## Classification Policy

| Label | Rule | Meaning |
| --- | --- | --- |
| Memory-intensive | DRAM req/KI >= 5, or high queue pressure with high L2 miss rate | Off-chip traffic or Ramulator queue pressure is a first-order performance signal. |
| Compute-intensive | Below the memory-intensive thresholds while still large enough to keep in the active set | Arithmetic, control flow, cache locality, or framework overhead dominates more than DRAM traffic. |
| Optional | Below 100k DRAM requests on H100 1/5 or cache-fit under the current input/trace | Kept for coverage and smoke tests, not used as a default representative row. |
| Not-use | Known multi-hour long-tail under the current native binary/input mix | Kept in inventory only; not included in active or optional selection. |

The memory-intensive rule uses `req_per_kinst`, `l2_miss_rate`, and `queue_avg_sum`: rows are memory-intensive if `req_per_kinst >= 5`, or if Ramulator queue pressure is high enough to show sustained backend pressure (`queue_avg_sum >= 256` and `l2_miss_rate >= 0.50`, or `req_per_kinst >= 3`, `queue_avg_sum >= 128`, and `l2_miss_rate >= 0.70`). Metrics use 32 B per Ramulator request for B/inst. Bounded trace rows are marked in the source column; they are acceptable for trace-size screening but should be rerun unbounded for final paper-quality numbers.

## Active Set Summary

Active rows: **41**. Optional rows: **31**. Not-use rows: **2**.

| Intensity class | Active rows | Optional rows | Not-use rows |
| --- | ---: | ---: | ---: |
| memory-intensive | 24 | 3 | 1 |
| compute-intensive | 17 | 28 | 1 |

| Access pattern | Memory-intensive | Compute-intensive | Total active |
| --- | ---: | ---: | ---: |
| Streaming | 4 | 3 | 7 |
| Mixed-locality | 9 | 9 | 18 |
| Irregular | 11 | 5 | 16 |

### Streaming

#### memory-intensive

| Benchmark | DRAM req/KI | B/inst | DRAM req | Row-hit | L2 miss rate | Queue avg sum | Source |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `polybench_bicg` | 27.76 | 0.888 | 4,166,716 | 0.489 | 0.496 | 133.2 | non-trace unbounded |
| `polybench_atax` | 27.72 | 0.887 | 4,160,588 | 0.473 | 0.495 | 132.6 | non-trace unbounded |
| `coral2_rajaperf_stream_triad` | 12.68 | 0.406 | 3,511,168 | 0.933 | 1.000 | 1354.2 | official unbounded |
| `coral2_rajaperf_reduce3` | 3.61 | 0.115 | 3,148,479 | 0.965 | 0.973 | 498.0 | official unbounded |

#### compute-intensive

| Benchmark | DRAM req/KI | B/inst | DRAM req | Row-hit | L2 miss rate | Queue avg sum | Source |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `cudf_tpch_q6` | 1.36 | 0.044 | 136,504 | 0.968 | 0.727 | 162.9 | memory trace bounded |
| `cudf_filter` | 1.36 | 0.044 | 136,282 | 0.968 | 0.727 | 160.5 | memory trace bounded |
| `cudf_project` | 1.00 | 0.032 | 118,025 | 0.969 | 1.000 | 146.6 | memory trace bounded |

### Mixed-locality

#### memory-intensive

| Benchmark | DRAM req/KI | B/inst | DRAM req | Row-hit | L2 miss rate | Queue avg sum | Source |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `pannotia_pagerank_spmv` | 15.91 | 0.509 | 11,919,709 | 0.679 | 0.354 | 383.2 | non-trace unbounded |
| `parboil_lbm` | 14.04 | 0.449 | 47,344,045 | 0.773 | 0.952 | 1204.7 | estimated from completed `t10` plus `t7` first-kernel probe |
| `coral2_rajaperf_energy` | 12.04 | 0.385 | 3,636,869 | 0.938 | 1.000 | 1289.6 | official unbounded |
| `cudf_sort` | 6.77 | 0.217 | 133,779 | 0.760 | 1.000 | 401.2 | memory trace bounded |
| `nvcomp_ans` | 5.62 | 0.180 | 133,170 | 0.872 | 0.988 | 663.4 | memory trace bounded |
| `gsuite_gcn_mp_pubmed` | 4.83 | 0.154 | 3,102,053 | 0.750 | 0.922 | 995.5 | official unbounded |
| `gsuite_gin_wl_pubmed` | 4.29 | 0.137 | 1,411,816 | 0.797 | 0.879 | 893.0 | official unbounded |
| `polybench_2dconv` | 3.42 | 0.109 | 2,580,224 | 0.904 | 0.706 | 384.2 | non-trace unbounded |
| `cudf_tpch_q3` | 2.49 | 0.080 | 114,009 | 0.965 | 0.748 | 264.0 | memory trace bounded |

#### compute-intensive

| Benchmark | DRAM req/KI | B/inst | DRAM req | Row-hit | L2 miss rate | Queue avg sum | Source |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `polybench_3dconv` | 2.44 | 0.078 | 2,574,528 | 0.931 | 0.352 | 205.4 | non-trace unbounded |
| `ispass_lib` | 2.34 | 0.075 | 1,539,266 | 0.850 | 0.370 | 38.0 | non-trace unbounded |
| `rodinia_backprop` | 2.11 | 0.068 | 286,730 | 0.968 | 0.302 | 193.9 | non-trace unbounded |
| `cudf_groupby` | 2.03 | 0.065 | 117,769 | 0.875 | 1.000 | 60.6 | memory trace bounded |
| `cudf_tpch_q1` | 1.36 | 0.044 | 136,211 | 0.969 | 0.727 | 159.8 | memory trace bounded |
| `cudf_tpch_q10` | 1.36 | 0.044 | 136,400 | 0.969 | 0.727 | 161.3 | memory trace bounded |
| `tango_alexnet` | 1.04 | 0.033 | 7,687,736 | 0.575 | 0.740 | 27.0 | trace unbounded |
| `coral2_rajaperf_planckian` | 0.72 | 0.023 | 578,200 | 0.891 | 1.000 | 64.5 | official unbounded |
| `coral2_rajaperf_ltimes` | 0.69 | 0.022 | 507,937 | 0.904 | 0.139 | 58.8 | official unbounded |

### Irregular

#### memory-intensive

| Benchmark | DRAM req/KI | B/inst | DRAM req | Row-hit | L2 miss rate | Queue avg sum | Source |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `graphbig_bfs_topo_atomic` | 17.39 | 0.557 | 4,546,572 | 0.186 | 0.221 | 246.0 | graph unbounded |
| `dlrm_v2_embeddingbag_quantile` | 14.28 | 0.457 | 11,410,618 | 0.840 | 0.859 | 950.3 | official unbounded |
| `dlrm_v2_embeddingbag_fixed` | 13.06 | 0.418 | 7,370,370 | 0.845 | 0.865 | 1205.7 | official unbounded |
| `graphbig_sssp_data_warp` | 12.27 | 0.393 | 2,122,279 | 0.665 | 0.315 | 274.7 | graph unbounded |
| `pannotia_mis` | 10.36 | 0.332 | 5,757,061 | 0.894 | 0.706 | 1116.8 | non-trace unbounded |
| `graphbig_bfs_data_warp` | 9.83 | 0.315 | 843,514 | 0.710 | 0.264 | 171.1 | graph unbounded |
| `dlrm_v3_sequence_gather` | 9.41 | 0.301 | 7,476,056 | 0.708 | 0.866 | 1084.9 | official unbounded |
| `pannotia_color_maxmin` | 8.44 | 0.270 | 4,689,771 | 0.908 | 0.610 | 587.6 | non-trace unbounded |
| `mlperf_rgat_relation_agg` | 7.02 | 0.225 | 493,824 | 0.249 | 0.116 | 114.4 | official unbounded |
| `graphbig_triangle_count` | 6.63 | 0.212 | 22,900,823 | 0.106 | 0.377 | 307.0 | graph unbounded |
| `mlperf_rgat_feature_fetch` | 4.20 | 0.134 | 2,042,717 | 0.796 | 0.863 | 881.5 | official unbounded |

#### compute-intensive

| Benchmark | DRAM req/KI | B/inst | DRAM req | Row-hit | L2 miss rate | Queue avg sum | Source |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gsuite_sage_mp_pubmed` | 4.99 | 0.160 | 442,579 | 0.177 | 0.092 | 70.5 | official unbounded |
| `proxy_xsbench` | 3.62 | 0.116 | 180,857 | 0.609 | 0.055 | 36.8 | non-trace unbounded |
| `lonestar_sssp_wln` | 2.41 | 0.077 | 284,733 | 0.549 | 0.234 | 0.2 | graph unbounded |
| `ispass_lps` | 2.22 | 0.071 | 125,000 | 0.969 | 0.619 | 52.4 | non-trace unbounded |
| `lonestar_bfs_wlw` | 2.16 | 0.069 | 153,676 | 0.680 | 0.220 | 0.2 | graph unbounded |

## Optional Rows

These rows remain in `manifest.optional.tsv`. Some are memory-intensive by req/KI, but their absolute DRAM-request count is too small to make stable H100 1/5 comparisons; others are compute/cache-fit rows.

| Benchmark | Pattern | Intensity | Reason | DRAM req/KI | DRAM req | Source |
| --- | --- | --- | --- | ---: | ---: | --- |
| `graphbig_kcore` | Irregular | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 2.56 | 43,743 | graph unbounded |
| `ispass_nn` | Irregular | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.28 | 19,704 | non-trace unbounded |
| `ispass_nqu` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.01 | 9 | non-trace unbounded |
| `ispass_ray` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.00 | 0 | non-trace unbounded |
| `rodinia_srad_v1` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.04 | 28,989 | non-trace unbounded |
| `rodinia_srad_v2` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.24 | 2,080 | non-trace unbounded |
| `rodinia_gaussian` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.12 | 800 | non-trace unbounded |
| `rodinia_lavamd` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.36 | 226 | non-trace unbounded |
| `rodinia_myocyte` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.00 | 104 | non-trace unbounded |
| `rodinia_nw` | Mixed-locality | memory-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 7.37 | 761 | non-trace unbounded |
| `rodinia_particlefilter_naive` | Irregular | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.01 | 580 | non-trace unbounded |
| `rodinia_pathfinder` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 1.90 | 1,252 | non-trace unbounded |
| `parboil_cutcp` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.00 | 19,620 | non-trace unbounded |
| `parboil_stencil` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.04 | 78,152 | non-trace unbounded |
| `parboil_mri_q` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.01 | 21,248 | non-trace unbounded |
| `parboil_sgemm` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 1.24 | 6,016 | non-trace unbounded |
| `pannotia_fw_block` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.01 | 8,192 | non-trace unbounded |
| `dragon_join` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.12 | 744 | non-trace unbounded |
| `dragon_amr` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.00 | 3 | non-trace unbounded |
| `nvcomp_lz4` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.13 | 2,929 | memory trace bounded |
| `nvcomp_snappy` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.19 | 3,627 | memory trace bounded |
| `nvcomp_gdeflate` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.00 | 0 | memory trace bounded |
| `nvcomp_deflate` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 4.81 | 16 | memory trace bounded |
| `nvcomp_zstd` | Streaming | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.00 | 0 | memory trace bounded |
| `nvcomp_cascaded` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.67 | 32,723 | memory trace bounded |
| `nvcomp_bitcomp` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 1.52 | 93,439 | memory trace bounded |
| `tango_cifarnet` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.23 | 36,712 | trace unbounded |
| `tango_gru` | Mixed-locality | memory-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 18.12 | 3,842 | trace unbounded |
| `tango_lstm` | Mixed-locality | memory-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 89.70 | 10,226 | trace unbounded |
| `cudf_join` | Mixed-locality | compute-intensive | below 100k DRAM requests on H100 1/5; too small/cache-fit for stable comparisons | 0.50 | 22,340 | memory trace bounded |

## Not-Use Long-Tail Rows

These rows remain documented in `manifest.not_use.tsv`, but are excluded from
the active and optional selection file. They can be restored only after a
rebuilt binary or reduced input is validated under AccelSim + Ramulator2.

| Benchmark | Pattern | Intensity | Reason | DRAM req/KI | DRAM req | Source |
| --- | --- | --- | --- | ---: | ---: | --- |
| `proxy_lulesh` | Mixed-locality | compute-intensive | numeric stop-time candidates down to 0.000001 still made only 4-5 heavy kernel launches in about 10 minutes; smaller settings become no-op-like | 16.56 | 1,069,540 | H100 1/5 q64 ablation, intentionally stopped |
| `pannotia_sssp_ell` | Irregular | memory-intensive | original NY ELL SSSP is long-tail; 32K/64K induced subgraph reductions complete but collapse req/KI to about 0.07 | 14.18 original / 0.07 reduced | 689,449,657 original / 98,304 reduced reads | H100 1/5 q64 ablation |

## Source Runs

| Source label | Result source |
| --- | --- |
| non-trace | recovered stdout from `results/h100_1stack_sxm_samsung_hbm3sid_main_nontrace_unbounded_q64_j24_20260523_v1/` |
| graph | `results/h100_1stack_graph_main_unbounded_q64_j4_20260525_v1/summary.csv` |
| memory trace | `results/h100_1stack_memory_trace_manifest_all_smoke_q64_j4_20260525_v1/summary.csv` |
| trace | `results/h100_1stack_sxm_samsung_hbm3sid_main_trace_unbounded_q64_j24_20260523_v1/summary.csv` |
| official | `results/h100_1stack_official_memory_unbounded_q64_j13_20260527_v2/summary.csv` |

The non-trace run did not produce a top-level `summary.csv` because it was launched before the current summary/finalization workflow. Its completed stdout logs were parsed once to recover Ramulator totals and AccelSim end-of-run counters; those recovered metrics are recorded in `representativeness_h100_1stack.tsv`.

# AccelSim + Ramulator2 Performance Metric Triage

Last updated: 2026-05-20

This note summarizes the first performance-metric sanity check of the
AccelSim + Ramulator2 runs. The goal is to identify which metrics are usable
now and which parts need investigation before AccelSim + Ramulator2 performance claims.

## Result Sets Checked

Completed bounded summaries:

| Result set | Notes |
| --- | --- |
| `ramulator2_backend_broad_after_argbuffer_fix_a100_1stack_l2_8mb_j52_mc50k_v1` | Broad set, Ramulator2, A100 1-stack, L2 8 MiB, queue 32, max-cycle 50k |
| `ramulator2_backend_more_suites_smoke_a100_1stack_l2_8mb_q128_if128_tick1_mc5k_j8_v1` | Lonestar/Pannotia smoke, queue 128, max-cycle 5k; includes old excluded candidates |
| `ramulator2_backend_parboil_data_smoke_a100_1stack_l2_8mb_q128_if128_tick1_mc5k_j4_v1` | Parboil data smoke, queue 128, max-cycle 5k |

Currently running unbounded runs were not stopped. Their logs are partial and
should not be treated as final performance results.

## Immediate Metric Warnings

1. `MAX_CYCLE_OK` summaries are smoke/triage data, not final performance data.
   They are useful for finding bottleneck signatures, but absolute IPC,
   runtime, and bandwidth should not be claimed from them.

2. Several AccelSim summary columns are missing or weak for this backend path:
   `l2_bw_gbs`, `l2_bw_total_gbs`, and `stall_icnt2sh` are often blank.
   `LD_mem_lat_dist` and `ST_mem_lat_dist` are zero in inspected logs.

3. Ramulator2 internal counters are now promoted into the runner CSV for
   unbounded Ramulator2 runs. With `--ramulator-finalize-stats auto`,
   `--max-cycle 0` runs parse Ramulator2's YAML stats dump into fields such as
   `ramulator_row_hits`, `ramulator_row_misses`,
   `ramulator_row_conflicts`, `ramulator_avg_read_latency`, and per-channel
   request vectors. Bounded `MAX_CYCLE_OK` runs still skip Ramulator2 final
   stats by default and should be treated as bridge-counter smoke data.

4. The running `more_suites_validated_unbounded...j4_v2` job was launched before
   the candidate manifest was cleaned. It still includes excluded benchmarks
   such as `lonestar_dmr`, `lonestar_mst`, and `lonestar_nsp`.

5. There are simultaneous broad unbounded runs with queue 32 and queue 128. This
   is fine for correctness, but wall-clock rates are host-contention affected.
   Simulated-cycle metrics are still meaningful once a benchmark finishes.

## Main Findings

### 1. Partition Imbalance Can Be Severe In Short Windows

In `broad_mc50k_q32`, some benchmarks route all accepted backend traffic to one
memory partition during the first 50k cycles.

| Benchmark | Active partitions | Max partition share | Accepted | Rejected | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `polybench_atax` | 1/8 | 1.000 | 5009 | 48097 | Partition 0 only |
| `polybench_mvt` | 1/8 | 1.000 | 5114 | 47990 | Partition 0 only |
| `polybench_gesummv` | 1/8 | 1.000 | 5219 | 47923 | Partition 0 only |
| `polybench_gramschmidt` | 1/8 | 1.000 | 158 | 0 | Very small traffic sample |
| `polybench_syr2k` | 8/8 | 0.808 | 19600 | 242462 | Still dominated by partition 0 |

Follow-up address-mapping checks show that this is a real early-phase
channel-camping signature, not a backend hardwiring bug. With the current
`dramid@8` mapping and `n_mem = 8`, channel bits are address `[10:8]`; the
PolyBench `N = 4096` float row stride is 16KB and can keep those bits constant
in short windows. Current unbounded q128 logs eventually distribute
`polybench_atax` and `polybench_mvt` almost perfectly across all 8 partitions.
See `docs/address_mapping_partition_imbalance.md`.

### 2. Queue Rejection Is A Real Bottleneck Signature

Highest rejected-request counts in `broad_mc50k_q32`:

| Benchmark | Rejected | Accepted | Weighted avg read latency | Row hit rate |
| --- | ---: | ---: | ---: | ---: |
| `rodinia_streamcluster` | 368269 | 33792 | 49.86 | 0.749 |
| `polybench_bicg` | 316159 | 33204 | 51.12 | 0.924 |
| `polybench_fdtd2d` | 253628 | 29823 | 56.40 | 0.601 |
| `polybench_syr2k` | 242462 | 19600 | 88.11 | 0.209 |
| `micro_mem_bw` | 233364 | 37385 | 45.30 | 0.811 |
| `proxy_lulesh` | 224591 | 47754 | 40.70 | 0.896 |

Queue 128 still saturates in some 5k smoke cases:

| Benchmark | Pending | Queue limit | Rejected | Accepted reads |
| --- | ---: | ---: | ---: | ---: |
| `pannotia_color_max` | 128 on several partitions | 128 | 21870 | 10229 |

This means the queue/inflight limit is not just a cosmetic parameter. It can
change performance and should be swept or justified.

### 3. Some Long-Latency Cases Are Mapping/Row-Locality Pathologies

Worst weighted average read latency in `broad_mc50k_q32`:

| Benchmark | Avg read latency | Queue length avg | Row hit rate | Rejected |
| --- | ---: | ---: | ---: | ---: |
| `polybench_atax` | 337.64 | 19.52 | 0.000 | 48097 |
| `polybench_mvt` | 330.81 | 17.77 | 0.000 | 47990 |
| `polybench_gesummv` | 325.15 | 28.90 | 0.0046 | 47923 |
| `polybench_syr2k` | 88.11 | 9.29 | 0.209 | 242462 |
| `proxy_xsbench` | 81.13 | 2.02 | 0.112 | 191818 |

These are useful stress cases, but first verify address mapping and partition
interleaving before interpreting them as HBM timing sensitivity.

### 4. L1/Shader Memory Stalls May Mask DRAM Effects

In `broad_mc50k_q32`, `gpgpu_n_stall_shd_mem` is often almost identical to
`gpgpu_n_l1cache_bkconflict`.

| Benchmark | `stall_shd_mem` | `l1cache_bkconflict` |
| --- | ---: | ---: |
| `micro_mem_bw` | 1087547 | 1077992 |
| `polybench_syrk` | 948075 | 948075 |
| `polybench_syr2k` | 824635 | 824635 |
| `ispass_nn` | 463376 | 325496 |
| `proxy_xsbench` | 221723 | 206449 |

For these benchmarks, memory-system changes may be partly hidden by L1/shared
bank conflicts or shader-side memory issue stalls.

### 5. L2 Miss Rate Alone Is Not Enough

Examples:

| Benchmark | L2 miss rate | Ramulator row hit rate | Comment |
| --- | ---: | ---: | --- |
| `parboil_mri_gridding` | 1.000 | 0.925 | Every L2 access misses, but DRAM row locality is high |
| `pannotia_mis` | 1.000 | 0.936 | Looks irregular at L2, but row-buffer locality exists |
| `micro_mem_bw` | 1.000 | 0.811 | Streaming-like DRAM locality despite L2 misses |
| `proxy_xsbench` | 0.115 | 0.112 | Low L2 miss rate does not guarantee row locality |

For benchmark classification and performance explanation, use both cache-level and
DRAM-level locality metrics.

## Benchmarks To Investigate First

| Priority | Benchmark group | Why |
| --- | --- | --- |
| P0 | `polybench_atax`, `polybench_mvt`, `polybench_gesummv` | Single-partition mapping, zero/near-zero row hit rate, very high avg latency |
| P0 | `pannotia_color_max` | Queue 128 still fills; high rejected count in a short 5k run |
| P1 | `micro_mem_bw`, `parboil_lbm`, `parboil_mri_gridding` | Memory-intensive; good for checking if Ramulator timing/bandwidth are plausible |
| P1 | `proxy_xsbench` | Irregular workload with low row hit rate and many rejected requests |
| P1 | `polybench_syr2k`, `polybench_syrk` | Shader/L1 stalls may hide DRAM timing effects |
| P2 | Dragon-li small inputs | Very small traffic counts; useful for correctness, weak for performance claims |

## Recommended Next Actions

1. Keep using the newly added AccelSim-side backend partition counters in
   `summary.csv`:
   total accepted reads/writes, completed reads, rejected requests, max pending,
   active partition count, max partition share, partition coefficient of
   variation, and partition-wise accepted/rejected counts. For completed
   unbounded Ramulator2 runs, also use the new `ramulator_*` fields for
   memory-system cycles, row hit/conflict/miss counts, queue length averages,
   read latency, and per-channel request distribution.

2. Check address mapping for the single-partition PolyBench cases. Specifically
   inspect whether the A100 1-stack address mapping and 32B atom/partition bits
   are unintentionally mapping contiguous arrays to partition 0.

3. Sweep queue/inflight settings on a small set:
   `queue_limit = 32/64/128/256`,
   `ramulator_inflight_read_limit = 32/64/128/256`.
   Use `polybench_atax`, `polybench_mvt`, `pannotia_color_max`,
   `micro_mem_bw`, and `proxy_xsbench`.

4. For final AccelSim + Ramulator2 comparison, avoid using `MAX_CYCLE_OK` absolute IPC as the
   main claim. Use completed runs or fixed instruction/window sampling with
   explicit warmup and measurement windows.

5. Relaunch `more_suites_validated` after the cleaned final/operational manifest
   is wired into the runner. The current running job was started with the old
   manifest and includes excluded candidates.

# Microbenchmark Memory Performance Check

Date: 2026-05-20

This note compares the current AccelSim + Ramulator2 bridge across 1-stack and
5-stack/full-stack memory configurations. The 5-stack runs use the full A100
geometry through `--config-variant a100_5stack`: 108 SM clusters, 40 memory
partitions, and 4 L2 sub-partitions per memory channel. The 1-stack runs use
`--config-variant a100_1stack`: 22 SM clusters and 8 memory partitions. The
same `-gpgpu_cache:dl2` line is inherited from the SM80_A100 base config, so
the effective total L2 scales with the number of memory partitions/slices.
The full-stack run intentionally follows the stock SM80_A100 108-SM geometry
rather than forcing an artificial `22 * 5 = 110` SM shape.

Raw derived CSV:

```text
results/micro_memory_perf_matrix_20260520.csv
```

Note: the HBM3SID rows below were collected before the HBM3 CK calculation was
corrected to the JEDEC 6.4Gbps/pin clocking rule (`tCK=0.625ns`). Rerun this
microbenchmark matrix before using the HBM3SID rows for final comparisons.

## Method

Each row used:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks micro_mem_bw,micro_mem_lat \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --timeout 600 \
  --jobs 2 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto
```

The `micro_mem_lat` benchmark did not generate Ramulator2 DRAM traffic within
50k cycles. A 500k-cycle HBM2e 1-stack probe also produced `mem_read_global=0`,
`backend_total_accepted_reads=0`, and `ramulator_num_read_reqs=0`, so latency
microbenchmark rows are not used for DRAM performance conclusions here.

## Bandwidth Microbenchmark Results

`micro_mem_bw` is the useful memory-system stress case in this run. All rows
ended with `MAX_CYCLE_OK` and `ramulator_stats_source=yaml`.

| Memory config | AccelSim variant | Channels | IPC | Global mem ops/cycle | Ramulator read req/cycle | Avg read latency | Row hit rate | Active partitions | Partition CV |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HBM2e 1-stack | `a100_1stack` | 8 | 28.636 | 2.150 | 2.179 | 57.548 | 0.764 | 8 | 0.441 |
| HBM2e 5-stack | `a100_5stack` | 40 | 29.494 | 2.422 | 1.970 | 64.349 | 0.601 | 18 | 2.812 |
| HBM3SID 1-stack | `a100_1stack` | 8 | 33.459 | 2.534 | 2.666 | 47.305 | 0.687 | 8 | 0.547 |
| HBM3SID 5-stack | `a100_5stack` | 40 | 31.702 | 2.639 | 2.270 | 55.821 | 0.537 | 16 | 2.701 |
| HBM4 1-stack | `a100_1stack` | 8 | 25.524 | 1.832 | 1.527 | 82.549 | 0.865 | 8 | 0.387 |
| HBM4 5-stack | `a100_5stack` | 40 | 23.660 | 1.879 | 1.347 | 94.035 | 0.712 | 14 | 2.973 |

## Interpretation

- HBM3SID is the best-performing model in this short `micro_mem_bw` window. It
  has the highest global memory operation rate and lowest Ramulator average read
  latency in both 1-stack and 5-stack forms.
- HBM4 is slower in this configuration despite its higher nominal data rate,
  because the current HBM4 timing preset uses much larger cycle timings
  (`nCL=28`, `nRCD=28`, `nRP=26`) than the HBM2e/HBM3SID configs.
- 5-stack/full-stack does not scale linearly over 1-stack for this microbench.
  The generated full-stack configs do expose 40 backends, but the short run only
  uses 14-18 active partitions depending on memory model. Partition CV is high,
  so address distribution and kernel access phasing dominate much of the early
  window.
- L2 miss rate is 1.0 for `micro_mem_bw`, so the benchmark is a valid DRAM-path
  stressor. The main caveat is queue pressure: all bandwidth rows have high
  rejected-request counts, so queue/inflight-limit sweeps are needed before
  making final absolute bandwidth claims.

## Result Paths

| Config | Summary |
| --- | --- |
| HBM2e 1-stack | `results/perf_hbm2e_1stack_micro_20260520/summary.csv` |
| HBM2e 5-stack | `results/perf_hbm2e_5stack_micro_20260520/summary.csv` |
| HBM3SID 1-stack | `results/perf_hbm3sid_1stack_micro_20260520/summary.csv` |
| HBM3SID 5-stack | `results/perf_hbm3sid_5stack_micro_20260520/summary.csv` |
| HBM4 1-stack | `results/perf_hbm4_1stack_micro_20260520/summary.csv` |
| HBM4 5-stack | `results/perf_hbm4_5stack_micro_20260520/summary.csv` |
| `micro_mem_lat` 500k probe | `results/probe_hbm2e_1stack_memlat_500k_20260520/summary.csv` |

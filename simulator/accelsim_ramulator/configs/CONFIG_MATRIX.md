# Canonical AccelSim + Ramulator2 Configuration Matrix

This directory keeps clean, human-readable AccelSim configs and their intended
Ramulator2 pairings.  Use these files when a run should not rely on the
runner's historical base-config-plus-override construction.

Generate or refresh the clean AccelSim configs with:

```bash
simulator/accelsim_ramulator/scripts/generate_canonical_accelsim_configs.py
```

Run them with `--config-variant canonical` so the matrix runner does not append
another architecture preset:

```bash
python3 simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_system_check \
  --benchmarks micro_mem_bw \
  --gpgpusim-config simulator/accelsim_ramulator/configs/accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config \
  --config-variant canonical \
  --ramulator-config simulator/accelsim_ramulator/configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --latencies 1 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto
```

## Canonical AccelSim Configs

| Canonical AccelSim config | Geometry | Main memory intent |
| --- | --- | --- |
| `accelsim/canonical/a100_hbm2e_1stack_8ch.gpgpusim.config` | 22 SMs, 8 memory partitions, 4 subpartitions/channel, 8 MiB L2 | A100 1/5-stack experiments |
| `accelsim/canonical/a100_hbm2e_full_40ch.gpgpusim.config` | 108 SMs, 40 memory partitions, 4 subpartitions/channel, 40 MiB L2 | A100 full 5-stack experiments |
| `accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config` | 26 SMs, 16 memory partitions, 2 subpartitions/channel, 10 MiB L2 | H100 SXM 1/5-stack experiments |
| `accelsim/canonical/h100_sxm_hbm3sid_full_80ch.gpgpusim.config` | 132 SMs, 80 memory partitions, 2 subpartitions/channel, 50 MiB L2 | H100 SXM full 5-stack experiments |

Each generated file keeps only one effective line for the important topology
and queue options:

- `-gpgpu_n_clusters`
- `-gpgpu_n_mem`
- `-gpgpu_n_sub_partition_per_mchannel`
- `-gpgpu_clock_domains`
- `-gpgpu_cache:dl2`
- `-gpgpu_memory_partition_indexing`
- `-gpgpu_mem_addr_mapping`
- `-gpgpu_dram_partition_queues`
- `-gpgpu_frfcfs_dram_sched_queue_size`
- `-gpgpu_dram_return_queue_size`

## Pairing Table

| Study target | AccelSim config | Ramulator2 config | Channels | Address mapping status |
| --- | --- | --- | ---: | --- |
| A100 1/5 HBM2e | `a100_hbm2e_1stack_8ch.gpgpusim.config` | `a100_hbm2e_1stack.yaml` | 8 | Direct external-channel mapping, current clean config generated |
| A100 full HBM2e | `a100_hbm2e_full_40ch.gpgpusim.config` | `a100_hbm2e_5stack.yaml` | 40 | Balanced IPoly path with 40-channel folding |
| A100 full HBM2e alias | `a100_hbm2e_full_40ch.gpgpusim.config` | `a100_hbm2e_80gb.yaml` | 40 | Equivalent 40-channel A100 80GB naming |
| H100 SXM 1/5 HBM3SID | `h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config` | `h100_sxm_hbm3_sid_16ch.yaml` | 16 | Direct external-channel mapping with HBM3 SID lower bits |
| H100 SXM full HBM3SID | `h100_sxm_hbm3sid_full_80ch.gpgpusim.config` | `h100_sxm_hbm3_sid_80ch.yaml` | 80 | Balanced IPoly path with 80-channel folding |
| A100 1/5 HBM3SID experiment | `a100_hbm2e_1stack_8ch.gpgpusim.config` | `hbm3_sid_external_8ch.yaml` | 8 | A100-side 8-channel SID comparison |
| A100 full HBM3SID experiment | `a100_hbm2e_full_40ch.gpgpusim.config` | `hbm3_sid_external_40ch.yaml` | 40 | A100-side 40-channel SID comparison |
| A100 1/5 HBM4 experiment | `a100_hbm2e_1stack_8ch.gpgpusim.config` | `hbm4.yaml` or `hbm4_external.yaml` | 8 | HBM4 smoke comparison path |
| A100 full HBM4 experiment | `a100_hbm2e_full_40ch.gpgpusim.config` | `hbm4_external_40ch.yaml` | 40 | HBM4 40-channel comparison path |

## Validation Rules

For a pairing to be promoted to "validated" in reports, run at least one bounded
system-check benchmark and inspect:

- `status` is `MAX_CYCLE_OK` or `OK`.
- `backend_enabled_partitions` equals the Ramulator2 channel count.
- `ramulator_stats_present=1`.
- `ramulator_cmd_stats_present=1`.
- `analysis_ramulator_cmd_rd_channel_cv` and
  `analysis_backend_accepted_read_partition_cv` are reasonable for the selected
  benchmark.

The same checks can be automated with:

```bash
simulator/accelsim_ramulator/scripts/check_summary.py \
  <result-dir-or-summary.csv> \
  --expected-partitions <channels> \
  --mode bounded
```

For unbounded final baselines, also require:

- `status=OK`.
- `max_cycle_hit=0`.
- `analysis_backend_read_completion_gap=0`.
- `analysis_backend_write_completion_gap=0` unless the run intentionally uses
  fire-and-forget write semantics.

## Latest Canonical Smoke

| Date | Pairing | Benchmark | Result |
| --- | --- | --- | --- |
| 2026-05-27 | `h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config` + `h100_sxm_hbm3_sid_16ch.yaml` | `micro_mem_bw`, q64, 1k cycles | `MAX_CYCLE_OK`, 16/16 backend partitions, `ramulator_stats_present=1`, `ramulator_cmd_stats_present=1` |

Summary CSV:

```text
simulator/accelsim_ramulator/results/canonical_h100_1stack_smoke_20260527_v1/summary.csv
```

# Configuring AccelSim + Ramulator2 Runs

The benchmark runner now lets AccelSim and Ramulator2 configs be selected as
files instead of editing the script.

## AccelSim Config

The base AccelSim/GPGPU-Sim config is copied into every run directory as
`gpgpusim.config`.

```bash
--gpgpusim-config /path/to/gpgpusim.config
```

Relative paths are resolved from the current directory, then from
`simulator/accelsim_ramulator`, then from the workspace root.

Additional AccelSim overrides can be supplied inline:

```bash
--config-overrides '-gpgpu_memory_partition_indexing 2;-gpgpu_dram_return_queue_size 256'
```

or as reusable files:

```bash
--accelsim-config-override-file configs/accelsim/a100_1stack_8mb_l2.config
```

The generated run config records the source base config and override files in
comments near the appended runner block.

## Ramulator2 Config

The Ramulator2 YAML is selected with:

```bash
--ramulator-config configs/ramulator/a100_hbm2e_1stack.yaml
```

For `--backend ramulator2`, the runner copies the selected YAML into each run
directory as `ramulator2.yaml` and exports:

```bash
SGRAM_RAMULATOR_CONFIG=<run-dir>/ramulator2.yaml
```

The result `summary.csv` also records:

- `gpgpusim_config_source`
- `gpgpusim_config_run`
- `config_override_files`
- `ramulator_config_source`
- `ramulator_config_run`
- `ramulator_stats_source`
- `accelsim_*_freq_mhz`
- `ramulator_tck_ns`
- `ramulator_effective_ticks_per_dram_cycle`
- `gpgpusim_host_timing_*`

`ramulator_stats_source=yaml` means the row was filled from Ramulator2's
internal finalizer and includes row hit/miss, latency, and queue metrics.
`ramulator_stats_source=bridge` means the process exited before Ramulator2 could
finalize, so the runner fell back to request counters printed by the
AccelSim-Ramulator2 bridge.

## Clock Coupling

AccelSim advances its CORE/ICNT/L2/DRAM domains according to
`-gpgpu_clock_domains`. The Ramulator2 bridge is called from AccelSim's DRAM
domain. By default, the runner exports:

```bash
SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=auto
SGRAM_ACCELSIM_DRAM_FREQ_MHZ=<dram clock from gpgpusim.config>
```

In `auto` mode the bridge queries Ramulator2 `tCK` and computes:

```text
ramulator_ticks_per_accelsim_dram_tick = (1000 / ramulator_tck_ns) / accelsim_dram_freq_mhz
```

The bridge uses a fractional accumulator, so non-integer ratios are preserved.
For example, A100's `-gpgpu_clock_domains ...:1512` with HBM2e `tCK=0.625 ns`
uses about `1.0582` Ramulator ticks per AccelSim DRAM tick.
The HBM3 SID configs use the JEDEC 6.4Gbps/pin speed bin, which is also
`tCK=0.625 ns` because HBM3 data rate is four times CK.

Use `--ramulator-ticks-per-dram-cycle <value>` only for an intentional manual
sensitivity run.

## Host Timing Metrics

The runner enables `-gpgpu_host_timing 1` by default. GPGPU-Sim then prints
wall-clock microsecond counters for major `gpgpu_sim::cycle()` stages:

```text
gpgpusim_host_timing_dram_us
gpgpusim_host_timing_l2_us
gpgpusim_host_timing_core_pipeline_us
gpgpusim_host_timing_total_us
```

The same fields, plus call counts and percentage of total host time, are copied
into `summary.csv`. Disable this instrumentation with
`--gpgpusim-host-timing off` when measuring raw simulator throughput.

## A100 HBM2e Examples

Normal 5-stack A100 HBM2e baseline:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --config-variant a100_5stack \
  --ramulator-config configs/ramulator/a100_hbm2e_5stack.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --timeout 600 \
  --jobs 64 \
  --ramulator-inflight-read-limit auto \
  --out-dir results/a100_hbm2e_5stack_smoke
```

Quick 1-stack smoke:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks micro_mem_bw \
  --config-variant a100_1stack \
  --ramulator-config configs/ramulator/a100_hbm2e_1stack.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --timeout 600 \
  --ramulator-inflight-read-limit auto \
  --out-dir results/a100_hbm2e_1stack_smoke
```

Equivalent full 40-memory-partition A100 HBM2e-style run using the older
`a100_full` variant name:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --config-variant a100_full \
  --ramulator-config configs/ramulator/a100_hbm2e_80gb.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --timeout 600 \
  --jobs 64 \
  --ramulator-inflight-read-limit auto \
  --out-dir results/a100_hbm2e_80gb_smoke
```

The 1-stack config is intended for fast validation only. For baseline results,
use the 5-stack config so AccelSim has 40 memory partitions and Ramulator2 has
40 externally selected channels.

## Address Mapping Notes

The 5-stack A100 config uses 40 memory partitions/channels.
`-gpgpu_memory_partition_indexing 2` selects IPoly. This tree supports 40-channel
IPoly by hashing in the next power-of-two channel domain and folding the result
back to 40.

For 5-stack balanced runs, use:

```text
-gpgpu_memory_partition_indexing 2
-gpgpu_mem_addr_mapping dramid@8;00000000.00000000.00000000.00000000.0000RRRR.RRRRRRRR.RBBBCCCC.BCCSSSSS
```

Because 40 is not a power of two, AccelSim's address decoder uses its
non-power-of-two `gap` path: the printed `addr_dec_mask[CHIP] = 0` is expected,
and the chip id is selected with `(addr >> dramid_start) % 40`.

Ramulator2 must expose the same number of externally selected channels as
AccelSim memory partitions. `a100_hbm2e_5stack.yaml` uses:

```text
DRAM.org.channel: 40
AddrMapper.impl: ExternalChannelRoBaRaCoCh
```

That mapper takes the Ramulator2 channel from AccelSim's memory partition id
(`Request::source_id`) and applies the lower-level `RoBaRaCoCh` mapping below
the channel.

## Validated Address-Mapping Configs

These combinations have been smoke-tested with the current AccelSim +
Ramulator2 bridge binaries:

| Ramulator2 config | AccelSim variant | Channels | Result |
| --- | --- | ---: | --- |
| `configs/ramulator/a100_hbm2e_1stack.yaml` | `a100_1stack` | 8 | `results/a100_hbm2e_1stack_current_smoke_20260520/summary.csv` |
| `configs/ramulator/a100_hbm2e_5stack.yaml` | `a100_5stack` | 40 | `results/a100_hbm2e_5stack_current_smoke_20260520/summary.csv` |
| `configs/ramulator/a100_hbm2e_80gb.yaml` | `a100_full` | 40 | `results/a100_hbm2e_80gb_current_smoke_20260520/summary.csv` |
| `configs/ramulator/hbm3_sid_external_8ch.yaml` | `a100_1stack` | 8 | `results/perf_hbm3sid_1stack_micro_20260520/summary.csv` |
| `configs/ramulator/hbm3_sid_external_40ch.yaml` | `a100_5stack` | 40 | `results/hbm3_sid_external_40ch_smoke_20260520/summary.csv` |
| `configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml` | `h100_1stack` | 16 | `results/h100_sxm_hbm3_1stack_smoke_yaml_auto1024_20260520_v1/summary.csv` |
| `configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml` | `h100_full` | 80 | `results/h100_sxm_hbm3_80ch_metric_yaml_auto5120_graphbig_kcore_20260520_v1/summary.csv` |
| `configs/ramulator/hbm4.yaml` | `a100_1stack` | 8 | `results/hbm4_current_smoke_20260520/summary.csv` |
| `configs/ramulator/hbm4_external.yaml` | `a100_1stack` | 8 | `results/hbm4_external_current_smoke_20260520/summary.csv` |
| `configs/ramulator/hbm4_external_40ch.yaml` | `a100_5stack` | 40 | `results/perf_hbm4_5stack_micro_20260520/summary.csv` |

All rows above use `ExternalChannelRoBaRaCoCh`, so the AccelSim memory partition
id must match the Ramulator2 channel count exposed by the YAML.

## HBM3 SID Runs

The default Ramulator2 `HBM3` implementation in this repository has no `sid`
level. Use `configs/ramulator/hbm3_sid_external_40ch.yaml` for the SID-capable
experimental model:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks graphbig_bfs_data_warp,polybench_atax \
  --config-variant a100_5stack \
  --ramulator-config configs/ramulator/hbm3_sid_external_40ch.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --timeout 600 \
  --jobs 2 \
  --ramulator-inflight-read-limit auto \
  --out-dir results/hbm3_sid_external_40ch_smoke
```

The channel mapping is still external: AccelSim selects the Ramulator2 channel
with the memory partition id, and Ramulator2 maps lower address bits across
`pseudochannel/sid/bankgroup/bank/row/column`.

The generic HBM3 SID YAMLs select `HBM3SID_6.4Gbps`. A quick smoke run should report
`ramulator_tck_ns=0.625`, `ramulator_mhz=1600.000`, and
`ramulator_effective_ticks_per_dram_cycle=1.058201` when paired with the A100
1512MHz DRAM clock.

The H100 SXM YAMLs select `HBM3SID_H100_SXM_5.234Gbps` to match the effective
3.35 TB/s class over a 5120-bit interface. With the H100 AccelSim DRAM clock at
1309MHz, `SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=auto` should report
`ramulator_tck_ns=0.764`, `ramulator_mhz=1308.901`, and
`ramulator_effective_ticks_per_dram_cycle=0.999924`.

# AccelSim + Ramulator2 Project Worklog

Last updated: 2026-05-21

This note is a working journal for the current AccelSim + Ramulator2
integration repository. It is intentionally separate from raw result reports:
keep long CSVs, benchmark output directories, and paper/spec archives out of
this file.

## Project Goal

The repository focus is AccelSim/GPGPU-Sim plus Ramulator2 co-simulation. The
important path is:

```text
AccelSim memory partition -> external backend hook -> Ramulator2 bridge
```

StackGanged naming remains only as legacy compatibility in some scripts and
manifests. New work should use the AccelSim + Ramulator2 terminology.

## Completed Work

### Repository and Benchmark Layout

- Moved loose benchmark helper scripts under `gpu_benchmark/scripts`.
- Organized the default user-facing benchmark list under
  `gpu_benchmark/benchmarks/main/manifest.tsv`.
- Added benchmark manifest documentation so new local benchmarks can be placed
  under `gpu_benchmark/benchmarks/main/local`.
- Removed `rodinia_particlefilter_float` from the main validated set because it
  repeatedly crashed under the current AccelSim path.

### Runner and Metrics

- Extended `scripts/run_fixed_backend_matrix.py` with AccelSim config variants:
  `a100_1stack`, `a100_5stack`, `h100_1stack`, and `h100_full`.
- Added Ramulator2 YAML selection through `--ramulator-config`.
- Added automatic Ramulator tick derivation from AccelSim DRAM clock and
  Ramulator2 `tCK` through `--ramulator-ticks-per-dram-cycle auto`.
- Added automatic inflight read limit sizing based on Ramulator2 channel count.
- Added Ramulator2 stats extraction into `summary.csv`, including request
  counts, row stats, queue stats, and average read latency.
- Added GPGPU-Sim host timing metric collection so slow simulator regions can be
  identified from the summary output.

### AccelSim/GPGPU-Sim Integration

- Added or updated the external memory backend path in GPGPU-Sim.
- Kept the fixed-latency backend as a scaffolding backend for integration
  sanity checks.
- Added Ramulator2 backend plumbing for read completion and write acceptance.
- Updated IPoly/hash address partitioning so non-power-of-two memory partition
  counts can fold from the next power-of-two domain instead of breaking.
- Verified that 40-channel and 80-channel style configs can route requests
  through all active partitions with the current binary.

### Ramulator2 Models and Configs

- Added an HBM3 SID model implementation:
  `simulator/ramulator2/src/dram/impl/HBM3SID.cpp`.
- Added H100-oriented HBM3 SID configs:
  - `configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml`
  - `configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml`
- Added H100 AccelSim config fragments:
  - `configs/accelsim/h100_sxm_hbm3_1stack_16ch.config`
  - `configs/accelsim/h100_sxm_hbm3_80ch.config`
- Added A100 HBM2e 5-stack config support:
  - `configs/accelsim/a100_5stack_hbm2e.config`
  - `configs/ramulator/a100_hbm2e_5stack.yaml`
- Added external-channel HBM3/HBM4 YAML variants for address-mapping checks.

## Current Validated Configurations

### H100 1/5 HBM3

- AccelSim variant: `h100_1stack`
- AccelSim fragment:
  `configs/accelsim/h100_sxm_hbm3_1stack_16ch.config`
- Ramulator2 config:
  `configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml`
- Shape: 26 SMs, 16 x 64-bit HBM3 channels, 32 L2 subpartitions, 10 MiB L2.

### H100 Full HBM3

- AccelSim variant: `h100_full`
- AccelSim fragment:
  `configs/accelsim/h100_sxm_hbm3_80ch.config`
- Ramulator2 config:
  `configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml`
- Shape: 132 SMs, 80 x 64-bit HBM3 channels, 160 L2 subpartitions, 50 MiB L2.

### A100 5-Stack HBM2e

- AccelSim variant: `a100_5stack`
- AccelSim fragment:
  `configs/accelsim/a100_5stack_hbm2e.config`
- Ramulator2 config:
  `configs/ramulator/a100_hbm2e_5stack.yaml`
- Shape: 108 SMs, 40 memory partitions, 4 subpartitions per memory channel.

## Recent Validation Notes

- H100 1/5 and full H100 microbenchmark runs completed with `OK:4` each.
- Microbenchmark result summaries:
  - `results/h100_1stack_micro_perf_natural_auto_20260521_v1/summary.csv`
  - `results/h100_full_micro_perf_natural_auto_20260521_v1/summary.csv`
- `micro_mem_bw` exercised the DRAM path with all expected partitions active:
  16/16 for H100 1/5 and 80/80 for full H100.
- `backend_total_rejected_inflight` was zero in the H100 microbenchmark runs, so
  the configured inflight guard was not the limiting factor there.
- H100 full delivered higher memory throughput than H100 1/5, while
  `micro_mem_lat` average read latency stayed close because both configs use the
  same HBM3 timing preset.

## Known Caveats

- Some long natural full-suite runs take many hours. Use bounded smoke tests
  first before launching unbounded runs.
- The old `stackganged_*` preset names still exist for compatibility. Prefer
  `accelsim_ramulator_main` for new runs.
- `micro_l2_*` benchmarks may not generate Ramulator2 DRAM traffic when the
  accesses are served by cache. Use `micro_mem_bw` for DRAM-path bandwidth
  pressure.
- Current H100 configs keep the SM80 functional/PTX compatibility path. They
  model H100-like performance geometry rather than changing compute capability.
- Large binary build products are currently tracked. GitHub warns about files
  over 50 MiB; moving those to Git LFS or rebuilding from source is a future
  cleanup item.

## Open Work

1. Finish or retire any old unbounded validation runners that are still active.
2. Re-run long full-suite H100 1/5 and H100 full jobs only when final
   end-to-end benchmark data is actually needed.
3. Add a small automated post-run checker for:
   - status counts,
   - enabled/active partition counts,
   - Ramulator stats presence,
   - inflight rejection,
   - accepted/completed read matching,
   - suspicious zero-request cases.
4. Add a concise config matrix table to the main README once the config list is
   stable.
5. Decide whether tracked shared libraries should remain in git or move to a
   build artifact/LFS workflow.
6. Keep root-level paper/spec archives and raw benchmark result reports out of
   normal commits unless explicitly requested.

## Common Commands

List the current main benchmark set:

```bash
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

Run an H100 1/5 Ramulator2 smoke test:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks micro_mem_bw,micro_mem_lat \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --jobs 2 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto
```

Run a full H100 Ramulator2 smoke test:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks micro_mem_bw,micro_mem_lat \
  --config-variant h100_full \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --jobs 2 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto
```

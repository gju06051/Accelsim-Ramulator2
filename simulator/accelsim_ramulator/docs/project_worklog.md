# AccelSim + Ramulator2 Project Worklog

Last updated: 2026-06-29

This note is the compact project journal for the current AccelSim + Ramulator2
integration repository. It records implementation state, validated operating
assumptions, and remaining cleanup work. Keep raw result directories, large
CSVs, trace dumps, and paper/spec archives out of this file.

## Project Goal

The repository focus is AccelSim/GPGPU-Sim plus Ramulator2 co-simulation. The
important path is:

```text
AccelSim memory partition -> external backend hook -> Ramulator2 bridge
```

Some scripts and types still use the historical `sgram` label. Treat that name
as a legacy internal label for the external memory backend hook, not as the
main research target.

## Current State Summary

- The Ramulator2 backend path is implemented and is the normal memory backend
  for current experiments.
- The fixed-latency backend remains as a small integration sanity-check path.
- A100 and H100 geometry variants exist in both historical runner override form
  and clean canonical config form.
- H100 SXM Samsung-style HBM3SID configs remain the current primary
  benchmark-characterization target.
- Conventional HBM4 baseline configs are available for H100 1/5 and full-stack
  comparison runs. The repository default `HBM4_8000Mbps` preset now follows
  the baseline HBM4 timing used by the SPIRE-HBM paper, not the SPIRE
  sub-pseudo-channel architecture.
- Main application benchmarks, optional application benchmarks, and system
  microbenchmarks are separated.
- Benchmark selection is controlled by a user-editable TSV file instead of
  hard-coded benchmark lists.
- Runtime shared libraries are now local build artifacts rather than tracked
  source files.

## Recent Updates Since 2026-05-21

### Benchmark Selection and Characterization

- Added `gpu_benchmark/benchmarks/main/benchmark_selection.tsv`.
  - Users can set `run=1` or `run=0` per benchmark.
  - Rows include suite, access pattern, memory/compute class, status, and
    H100 1/5 characterization notes.
- Added runner support for `--benchmark-selection-file`.
  - The default main preset reads the selection file when supplied.
  - Optional rows from `manifest.optional.tsv` can be enabled without moving
    them back into the active manifest.
- Split benchmark purposes:
  - `gpu_benchmark/benchmarks/main/manifest.tsv`: active application rows.
  - `gpu_benchmark/benchmarks/main/manifest.optional.tsv`: retained optional
    rows that are small or cache-fit under the H100 1/5 characterization.
  - `gpu_benchmark/benchmarks/main/manifest.not_use.tsv`: retained inventory
    for known multi-hour long-tail rows (`rodinia_streamcluster`,
    `proxy_lulesh`) excluded from routine active/optional selection.
  - `gpu_benchmark/benchmarks/system/manifest.tsv`: microbenchmarks for
    bandwidth, latency, queue, cache-path, and atomics checks.
- Fixed the H100 SXM Samsung HBM3SID 1/5-stack q64 characterization in
  `gpu_benchmark/benchmarks/main/REPRESENTATIVENESS.md`.
  - Active rows: 42.
  - Optional rows: 30.
  - Not-use long-tail rows: 2.
  - Active memory-intensive rows: 25.
  - Active compute-intensive rows: 17.
  - Access-pattern split: 7 streaming, 18 mixed-locality, 17 irregular.
- The top-level README now lists all selectable application benchmarks by
  workload field and lists the system-check microbenchmarks separately.

### Benchmark Inputs, Traces, and Official-Derived Rows

- Promoted official-derived proxy rows for DLRM, GNN, and CORAL2-style memory
  motifs after H100 1/5 validation.
- Scaled selected GNN rows to avoid overly cache-fit behavior:
  - `mlperf_rgat_relation_agg`
  - `gsuite_sage_mp_pubmed`
- Kept `nvcomp_*`, `cudf_*`, and `tango_*` as trace-driven rows because their
  native wrappers do not reliably enter the AccelSim/Ramulator2 backend path.
- Documented trace preparation, source provenance, and local artifact packaging
  in the root README and benchmark README files.
- Added trace-packaging support so ignored prepared traces can be moved between
  clones as tar payloads rather than committed to Git.
- Removed or demoted problematic rows from default active use:
  - `rodinia_particlefilter_float` was removed after repeated crashes.
  - Long-tail PolyBench rows such as `polybench_fdtd2d`,
    `polybench_gramschmidt`, `polybench_covariance`, and `polybench_2mm` stay
    out of the active main set until smaller rebuilt inputs are available.
  - `micro_*` rows are system checks, not application benchmarks.

### Canonical Configuration Cleanup

- Added clean canonical AccelSim configs under
  `simulator/accelsim_ramulator/configs/accelsim/canonical/`.
- Added `simulator/accelsim_ramulator/scripts/generate_canonical_accelsim_configs.py`
  to regenerate the clean configs from the maintained spec table.
- Added `simulator/accelsim_ramulator/configs/CONFIG_MATRIX.md`.
  - The matrix records intended AccelSim/Ramulator2 pairings.
  - It documents validation rules for bounded smoke runs and unbounded final
    baselines.
  - New runs that should avoid append-style overrides can use
    `--config-variant canonical` with an explicit `--gpgpusim-config`.
- The historical runner append/override path still works, but canonical configs
  are the preferred human-readable form for final experiments.

### Backend Metrics and Summary Output

- Extended `scripts/run_fixed_backend_matrix.py` to collect and summarize:
  - AccelSim backend accepted/completed read/write counters.
  - Ramulator request counts and average latency.
  - Ramulator command counts, including read/write/activate/precharge-style
    command stats when present.
  - Queue pressure and rejected request counters.
  - Partition/channel distribution checks.
  - Host-side GPGPU-Sim timing buckets.
  - Core-granularity and request-size ratios.
- Added separate read/write completion-gap reporting so write-finalization
  caveats are visible instead of hidden behind a single combined counter.
- Current default interpretation:
  - Reads complete through Ramulator callback timing.
  - Writes are accepted into Ramulator and returned to AccelSim early; remaining
    write drain/finalization state should be interpreted as a modeling caveat.
  - Bounded `--max-cycle` runs may leave outstanding reads at forced stop time;
    use unbounded runs for final completion-gap checks.
- Added `scripts/check_summary.py` as a post-run quality gate for `summary.csv`
  files. It reports P0/P1/P2 findings for status, Ramulator stats, command
  stats, partitions, completion gaps, zero-request rows, bounded run state,
  partition/channel CV, and queue rejection pressure.
- Wired the checker into `scripts/run_fixed_backend_matrix.py`; each completed
  matrix run now writes `summary_check.txt` and `summary_check.json` in the
  output directory by default.

### Runtime Build Artifact Cleanup

- Runtime shared libraries are now treated as local build artifacts:
  - `simulator/gpgpu-sim_distribution/build/sgram_fixed/libcudart.so`
  - `simulator/gpgpu-sim_distribution/build/sgram_fixed/libcudart.so.12`
  - `simulator/ramulator2/libramulator.so`
  - `simulator/accelsim_ramulator/build/ramulator2_bridge/libsgram_ramulator2_bridge.so`
- Added ignore rules so these files are not re-added accidentally.
- Added `simulator/accelsim_ramulator/scripts/build_runtime_artifacts.sh` to
  regenerate AccelSim/GPGPU-Sim, Ramulator2, and the bridge from source.
- The root README and integration README now describe the fresh-clone rebuild
  flow.

### HBM4 Baseline Update

- Promoted the conventional HBM4 timing used by the SPIRE-HBM paper to the
  repository's default HBM4 baseline preset:
  `simulator/ramulator2/src/dram/impl/HBM4.cpp::HBM4_8000Mbps`.
- The HBM4 baseline uses:
  - `HBM4_32Gb_16Hi` organization.
  - 32-bit pseudochannels.
  - 4 SIDs / 16Hi.
  - 2 bank groups x 8 banks per SID.
  - 8.0Gbps/pin, `tCK=0.500ns`.
  - Baseline read-to-read timing `tCCDS=2`, `tCCDR=3`, `tCCDL=5`.
  - Open-row policy, all-bank refresh, FR-FCFS scheduling, and 64-entry
    read/write queues per pseudochannel.
- Kept the explicit `HBM4_SPIREBaseline_8000Mbps` name as a compatibility
  alias.
- Moved the Safari Ramulator2-derived exploratory 8.0Gbps preset to
  `HBM4_Safari_8000Mbps` so it can still be used for comparisons without being
  confused with the repository baseline.
- Updated H100 HBM4 YAMLs:
  - `configs/ramulator/h100_sxm_hbm4_1stack_32ch.yaml`
  - `configs/ramulator/h100_sxm_hbm4_5stack_160ch.yaml`
- The HBM4 YAMLs intentionally do not model SPIRE-HBM's sub-pseudo-channel
  data path, SID-bit repurposing, or doubled burst length.

## Implementation Work Completed

### AccelSim/GPGPU-Sim Integration

- Added the external memory backend hook in GPGPU-Sim.
- Added fixed-latency and Ramulator2 backend modes.
- Routed accepted reads through Ramulator2 completion callbacks.
- Routed writes into Ramulator2 while returning them to AccelSim after backend
  acceptance.
- Added support for external backend queue limits and inflight read limits.
- Updated non-power-of-two partition handling so 40-channel and 80-channel
  configurations can use folded IPoly/hash partitioning.
- Fixed the kernel-end L2 flush loop so full H100-style configurations do not
  stop at only `m_n_mem` subpartitions when more subpartitions exist.
- Added simulator host timing instrumentation to expose where GPGPU-Sim time is
  being spent.

### Ramulator2 Models and Configs

- Added the HBM3SID model implementation:
  `simulator/ramulator2/src/dram/impl/HBM3SID.cpp`.
- Added Samsung-style HBM3SID organization/timing presets for current H100 SXM
  study configs.
- Current H100 HBM3SID modeling intent:
  - 5 HBM stacks for full H100.
  - 16 x 64-bit external channels per stack.
  - 80 x 64-bit external channels for full H100.
  - 2 pseudo-channels/SID-aware internal structure in the Ramulator model.
  - H100 SXM bandwidth-derived frequency while using Samsung-style HBM3 timing
    and organization assumptions.
- Added A100 HBM2e and HBM3/HBM4 comparison YAMLs for smoke and address-mapping
  checks.
- Added H100 HBM4 baseline YAMLs:
  - `h100_sxm_hbm4_1stack_32ch.yaml`: H100 1/5 geometry with 16 AccelSim memory
    partitions mapped onto 32 HBM4 pseudochannels.
  - `h100_sxm_hbm4_5stack_160ch.yaml`: full H100 geometry with 80 AccelSim
    memory partitions mapped onto 160 HBM4 pseudochannels.

### Runner and Configuration Support

- Added AccelSim config variants:
  - `a100_1stack`
  - `a100_5stack`
  - `h100_1stack`
  - `h100_full`
  - `canonical`
- Added Ramulator2 YAML selection through `--ramulator-config`.
- Added automatic Ramulator tick derivation from AccelSim DRAM clock and
  Ramulator2 `tCK` with `--ramulator-ticks-per-dram-cycle auto`.
- Added automatic bridge inflight read sizing from Ramulator2 channel count and
  selected queue size.
- Standardized current queue-size default around AccelSim/Ramulator agreement;
  q64 is the current H100 Samsung baseline used by the characterization table.
- Updated automatic summary-check expected-partition resolution so `auto` uses
  the AccelSim `-gpgpu_n_mem` partition count when the runner variant supplies
  it. This avoids false P0 partition-count warnings for HBM4 configs where the
  Ramulator2 pseudochannel count is 32 or 160 while AccelSim exposes 16 or 80
  memory partitions.

## Current Validated Configuration Set

### A100 HBM2e 1/5

- Canonical AccelSim config:
  `configs/accelsim/canonical/a100_hbm2e_1stack_8ch.gpgpusim.config`
- Ramulator2 config:
  `configs/ramulator/a100_hbm2e_1stack.yaml`
- Shape: 22 SMs, 8 memory partitions, 4 subpartitions/channel, 8 MiB L2.

### A100 HBM2e Full

- Canonical AccelSim config:
  `configs/accelsim/canonical/a100_hbm2e_full_40ch.gpgpusim.config`
- Ramulator2 config:
  `configs/ramulator/a100_hbm2e_5stack.yaml`
- Shape: 108 SMs, 40 memory partitions, 4 subpartitions/channel, 40 MiB L2.

### H100 SXM HBM3SID 1/5

- Canonical AccelSim config:
  `configs/accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config`
- Ramulator2 config:
  `configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml`
- Shape: 26 SMs, 16 memory partitions, 2 subpartitions/channel, 10 MiB L2.
- This is the main benchmark characterization baseline.

### H100 SXM HBM3SID Full

- Canonical AccelSim config:
  `configs/accelsim/canonical/h100_sxm_hbm3sid_full_80ch.gpgpusim.config`
- Ramulator2 config:
  `configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml`
- Shape: 132 SMs, 80 memory partitions, 2 subpartitions/channel, 50 MiB L2.

### H100 SXM HBM4 Baseline 1/5

- AccelSim variant:
  `h100_1stack`
- Ramulator2 config:
  `configs/ramulator/h100_sxm_hbm4_1stack_32ch.yaml`
- Shape: 26 SMs, 16 AccelSim memory partitions, 2 subpartitions/channel,
  10 MiB L2, mapped to 32 x 32-bit HBM4 pseudochannels.
- Baseline model: conventional HBM4, `HBM4_32Gb_16Hi`,
  `HBM4_8000Mbps`.
- Latest smoke:
  `results/h100_1stack_hbm4_baseline_smoke_20260629_v1/summary.csv`.
  Bounded 5k-cycle `polybench_atax` run reached `MAX_CYCLE_OK` with
  Ramulator2 stats and command stats present. The read gap is expected for the
  bounded stop condition.

### H100 SXM HBM4 Baseline Full

- AccelSim variant:
  `h100_full`
- Ramulator2 config:
  `configs/ramulator/h100_sxm_hbm4_5stack_160ch.yaml`
- Shape: 132 SMs, 80 AccelSim memory partitions, 2 subpartitions/channel,
  50 MiB L2, mapped to 160 x 32-bit HBM4 pseudochannels.
- Baseline model: conventional HBM4, `HBM4_32Gb_16Hi`,
  `HBM4_8000Mbps`.
- Latest smoke:
  `results/h100_full_hbm4_baseline_smoke_20260629_v1/summary.csv`.
  Bounded 5k-cycle `polybench_atax` run reached `MAX_CYCLE_OK` with
  Ramulator2 stats and command stats present. The read gap is expected for the
  bounded stop condition.

### HBM3/HBM4 Comparison Paths

- A100-side HBM3SID comparison YAMLs exist for 8-channel and 40-channel smoke
  checks.
- HBM4 YAMLs exist for 8-channel and 40-channel A100-side comparison paths,
  using the same conventional HBM4 baseline timing as the H100 HBM4 configs.
- H100 HBM4 baseline rows above are smoke-validated with the current bridge
  build. Treat final performance claims as pending until unbounded benchmark
  runs are completed and checked with `summary_check.py`.

## Recent Validation Notes

- H100 1/5 Samsung HBM3SID q64 is the current baseline for benchmark
  representativeness.
- The active benchmark table uses recovered or generated metrics from:
  - non-trace unbounded H100 1/5 logs,
  - graph main unbounded H100 1/5 runs,
  - memory trace bounded smoke runs,
  - trace unbounded runs,
  - official-derived DLRM/GNN/CORAL2 unbounded runs.
- Latest canonical smoke recorded in `configs/CONFIG_MATRIX.md`:
  - H100 SXM HBM3SID 1/5 canonical config.
  - `micro_mem_bw`, q64, 1k cycles.
  - 16/16 backend partitions active.
  - Ramulator stats and command stats present.
- Latest HBM4 baseline smokes:
  - H100 1/5 HBM4 baseline, `polybench_atax`, q64, 5k cycles,
    `tCK=0.500ns`, 16/16 backend partitions active.
  - H100 full HBM4 baseline, `polybench_atax`, q64, 5k cycles,
    `tCK=0.500ns`, 80/80 backend partitions active.
  - Both bounded smokes leave expected read gaps at forced stop time.
- `micro_l2_*` rows may be served mostly by cache; use `micro_mem_bw` and
  `micro_mem_lat` for DRAM-path backend checks.
- Trace-driven rows should be checked for `backend_enabled_partitions`,
  `ramulator_stats_present`, and nonzero request counts before including them
  in performance comparisons.

## Known Caveats

- Current H100 configs keep the SM80 functional/PTX compatibility path. They
  model H100-like performance geometry rather than changing compute capability.
- Ramulator-backed writes are accepted into Ramulator but returned to AccelSim
  early. This is the main remaining timing-semantics caveat.
- Bounded validation runs can leave outstanding reads or writes at forced stop
  time. Final performance comparisons should use unbounded natural completion
  when practical.
- Some optional benchmarks are retained for coverage but are too small or
  cache-fit for routine comparative studies. Known multi-hour native long-tail
  rows are separated into `manifest.not_use.tsv`.
- The old `stackganged_*` preset names remain for compatibility. New runs
  should use `accelsim_ramulator_main`, `accelsim_ramulator_system_check`, and
  explicit config names.
- Prepared traces, large graph inputs, local paper/spec PDFs, result CSVs, and
  runtime shared libraries are intentionally ignored.

## Open Work

1. Run native AccelSim DRAM vs Ramulator2 cross-checks on a small fixed set and
   compare read/write totals, row locality, queue pressure, IPC, and runtime
   trends.
2. Use the automatic `summary_check.txt/json` reports as the first triage step
   for long runs, and tune thresholds if a workload class needs stricter CV or
   queue-pressure rules.
3. Decide how strongly write timing should be modeled:
   - keep current fire-and-forget completion semantics,
   - add delayed write completion,
   - or expose both modes as explicit experiments.
4. Promote additional canonical pairings to "validated" only after running the
   validation rules in `configs/CONFIG_MATRIX.md`.
5. Keep benchmark selection and representativeness tables synchronized whenever
   active/optional rows or default inputs change.
6. Keep ignored local payload packaging up to date when prepared trace groups or
   large graph inputs are added.

## Common Commands

Build ignored runtime artifacts after a fresh clone:

```bash
./simulator/accelsim_ramulator/scripts/build_runtime_artifacts.sh \
  --cuda /usr/local/cuda-12.3
```

List the selected main benchmark set:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --benchmark-selection-file ../../gpu_benchmark/benchmarks/main/benchmark_selection.tsv \
  --list-benchmarks
```

Run a canonical H100 1/5 Ramulator2 smoke test:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_system_check \
  --benchmarks micro_mem_bw \
  --gpgpusim-config configs/accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config \
  --config-variant canonical \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --latencies 1 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --max-cycle 1000 \
  --jobs 1
```

Check a run summary after completion:

```bash
cd simulator/accelsim_ramulator
./scripts/check_summary.py \
  results/h100_1stack_selected_main/summary.csv \
  --expected-partitions 16 \
  --mode unbounded
```

Run the active H100 1/5 main set with the selection file:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmark-selection-file ../../gpu_benchmark/benchmarks/main/benchmark_selection.tsv \
  --config-variant canonical \
  --gpgpusim-config configs/accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --latencies 0 \
  --queue-limits 64 \
  --max-cycle 0 \
  --timeout 0 \
  --jobs 24 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --out-dir results/h100_1stack_selected_main
```

# AccelSim + Ramulator2 Integration Bundle

This repository packages an AccelSim/GPGPU-Sim and Ramulator2 co-simulation
environment in one checkout. Its main purpose is to run CUDA workloads through
AccelSim while routing memory-system requests into a Ramulator2-backed external
memory backend.

Some internal scripts and environment variables still use the historical
`sgram` name. Treat those names as legacy labels for the external memory
backend hook. The project focus is AccelSim + Ramulator2 integration.

## Repository Layout

```text
Accelsim-Ramulator/
  simulator/
    gpgpu-sim_distribution/   # AccelSim/GPGPU-Sim source tree and runtime build
    ramulator2/               # Ramulator2 source tree and runtime library
    accelsim_ramulator/       # bridge, configs, docs, validation runners
  gpu_benchmark/
    benchmarks/main/          # default benchmark manifest and local drop zone
    benchmarks/inventory/     # broader candidate manifests
    common/                   # packaged benchmark harness, binaries, and data
    docs/                     # benchmark layout notes
    scripts/                  # benchmark helper scripts
  scripts/                    # top-level layout checks and smoke helpers
  tools/                      # optional tracing tools
```

The main implementation area is `simulator/accelsim_ramulator`. It contains the
Ramulator2 bridge, runtime config files, benchmark runner, and project notes.

## What Is Included

- AccelSim/GPGPU-Sim source plus the packaged `build/sgram_fixed/libcudart.so`
  runtime used by the benchmark runner.
- Ramulator2 source plus the packaged `libramulator.so` runtime library.
- The external memory backend path that connects AccelSim memory partitions to
  Ramulator2.
- HBM2e, HBM3 SID, and HBM4-oriented Ramulator2 YAML configs.
- A100 and H100 AccelSim config variants, including H100 1/5 and full H100
  HBM3 layouts.
- A curated main benchmark set and a larger operational benchmark pool.

Generated result directories, trace dumps, replay outputs, and large paper/spec
archives are not part of normal commits.

## Quick Start

Check the all-in-one layout:

```bash
./scripts/check_all_in_one.py
```

Run a tiny fixed-backend smoke test:

```bash
./scripts/run_smoke_all_in_one.sh
```

List the default AccelSim + Ramulator2 benchmark set:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

Run a bounded A100 HBM2e 5-stack Ramulator2 smoke sweep:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_5stack \
  --ramulator-config configs/ramulator/a100_hbm2e_5stack.yaml \
  --max-cycle 50000 \
  --timeout 240 \
  --jobs 32 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --out-dir results/a100_hbm2e_5stack_smoke
```

The runner writes a `summary.csv` in the selected output directory. It includes
benchmark status, AccelSim metrics, Ramulator2 stats, bridge counters,
partition activity, and host-side simulator timing metrics.

## Common Configurations

| Target | AccelSim variant | Ramulator2 config | Shape |
| --- | --- | --- | --- |
| A100 HBM2e 1-stack | `a100_1stack` | `configs/ramulator/a100_hbm2e_1stack.yaml` | 8 memory partitions |
| A100 HBM2e 5-stack | `a100_5stack` | `configs/ramulator/a100_hbm2e_5stack.yaml` | 40 memory partitions |
| H100 HBM3 1/5 | `h100_1stack` | `configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml` | 26 SMs, 16 x 64-bit channels, 10 MiB L2 |
| H100 HBM3 full | `h100_full` | `configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml` | 132 SMs, 80 x 64-bit channels, 50 MiB L2 |

The H100 variants keep the SM80 functional/PTX path for benchmark
compatibility. They model H100-like performance geometry rather than changing
compute capability.

Additional config fragments are documented in:

- `simulator/accelsim_ramulator/configs/accelsim/README.md`
- `simulator/accelsim_ramulator/configs/ramulator/README.md`
- `simulator/accelsim_ramulator/docs/configuration.md`

## H100 Microbenchmark Examples

Run a natural-completion H100 1/5 microbenchmark check:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks micro_mem_bw,micro_mem_lat,micro_l2_bw_32f,micro_l2_lat \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 0 \
  --timeout 0 \
  --jobs 4 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --ramulator-finalize-stats auto \
  --out-dir results/h100_1stack_micro
```

Run the matching full H100 check:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks micro_mem_bw,micro_mem_lat,micro_l2_bw_32f,micro_l2_lat \
  --config-variant h100_full \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 0 \
  --timeout 0 \
  --jobs 4 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --ramulator-finalize-stats auto \
  --out-dir results/h100_full_micro
```

Use `micro_mem_bw` for DRAM-path pressure. The `micro_l2_*` benchmarks can be
served mostly by cache and may produce little or no Ramulator2 DRAM traffic.

## Timing and Stats

The runner defaults are chosen to keep AccelSim and Ramulator2 aligned:

- `--ramulator-ticks-per-dram-cycle auto` reads AccelSim's DRAM clock and
  Ramulator2 `tCK`, then uses a fractional tick accumulator.
- `--ramulator-inflight-read-limit auto` scales the bridge-wide read guard with
  the Ramulator2 channel count.
- `--ramulator-finalize-stats auto` enables Ramulator2 internal stats and falls
  back to bridge counters if a process exits before Ramulator2 finalization.
- `--gpgpusim-host-timing on` records host-side time spent in core, interconnect,
  L2, DRAM, and other simulator stages.

Useful `summary.csv` columns include:

- `status`, `max_cycle_hit`, `seconds`
- `backend_enabled_partitions`, `backend_active_partitions`
- `backend_total_accepted_reads`, `backend_total_completed_reads`
- `backend_total_rejected_inflight`, `backend_total_rejected_ramulator`
- `ramulator_stats_present`, `ramulator_stats_source`
- `ramulator_total_num_read_requests`, `ramulator_avg_read_latency`
- `ramulator_tck_ns`, `ramulator_mhz`
- `gpgpusim_host_timing_*`

## Benchmark Sets

The default benchmark manifest is:

```text
gpu_benchmark/benchmarks/main/manifest.tsv
```

It currently contains 72 representative benchmarks:

| Class | Count |
| --- | ---: |
| Streaming | 19 |
| Mixed-locality | 35 |
| Irregular | 18 |

Main benchmark coverage by workload field:

| Field | Benchmarks |
| --- | --- |
| Dense matrix and regular arrays | `polybench_bicg`, `polybench_atax`, `polybench_covariance`, `polybench_2mm`, `polybench_gramschmidt`, `rodinia_gaussian`, `parboil_mri_q`, `parboil_sgemm` |
| Stencils, grids, meshes, and structured simulation | `polybench_2dconv`, `polybench_3dconv`, `polybench_fdtd2d`, `ispass_ray`, `rodinia_srad_v1`, `rodinia_srad_v2`, `rodinia_myocyte`, `proxy_lulesh`, `parboil_stencil`, `parboil_lbm`, `dragon_amr` |
| Graph and sparse traversal analytics | `graphbig_bfs_data_warp`, `graphbig_bfs_topo_atomic`, `graphbig_sssp_data_warp`, `graphbig_triangle_count`, `graphbig_kcore`, `lonestar_bfs_wlw`, `lonestar_sssp_wln`, `pannotia_mis`, `pannotia_color_maxmin`, `pannotia_sssp_ell`, `pannotia_pagerank_spmv` |
| Search, lookup, joins, and data mining | `ispass_lps`, `ispass_lib`, `ispass_nn`, `ispass_nqu`, `rodinia_streamcluster`, `proxy_xsbench`, `dragon_join` |
| Particle, molecular, and probabilistic tracking | `rodinia_lavamd`, `rodinia_particlefilter_naive`, `parboil_cutcp` |
| Dynamic programming and path-style kernels | `rodinia_nw`, `rodinia_pathfinder`, `pannotia_fw_block` |
| Compression and entropy coding | `nvcomp_lz4`, `nvcomp_snappy`, `nvcomp_gdeflate`, `nvcomp_deflate`, `nvcomp_zstd`, `nvcomp_cascaded`, `nvcomp_bitcomp`, `nvcomp_ans` |
| Columnar dataframe analytics | `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_join`, `cudf_sort`, `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` |
| Memory-system microbenchmarks | `micro_mem_atom_size`, `micro_mem_bw`, `micro_mem_lat`, `micro_l1_bw_128`, `micro_l2_bw_32f`, `micro_l2_lat`, `micro_atomic_add_bw_conflict`, `micro_l2_access_grain` |
| Neural-network inference and layers | `rodinia_backprop`, `tango_cifarnet`, `tango_gru`, `tango_lstm` |

The broader operational manifest is:

```text
simulator/accelsim_ramulator/benchmarks/operational_manifest.tsv
```

It currently contains 91 validated benchmarks:

| Class | Count |
| --- | ---: |
| Streaming | 22 |
| Mixed-locality | 27 |
| Irregular | 42 |

Add local benchmarks under:

```text
gpu_benchmark/benchmarks/main/local/
```

Then add one TSV row to `gpu_benchmark/benchmarks/main/manifest.tsv`. See
`gpu_benchmark/benchmarks/README.md` for the field format.

Known incompatible candidates are documented in:

```text
simulator/accelsim_ramulator/benchmarks/exclusions.md
```

The legacy `stackganged_*` preset names remain for compatibility with earlier
scripts. New runs should normally use `accelsim_ramulator_main`.

## Environment Variables

The helper scripts set these paths automatically for this all-in-one checkout:

```bash
export SGRAM_WORKSPACE_ROOT=$PWD
export SGRAM_GPU_BENCHMARK_ROOT=$PWD/gpu_benchmark
export SGRAM_GPGPU_ROOT=$PWD/simulator/gpgpu-sim_distribution
export SGRAM_RAMULATOR2_ROOT=$PWD/simulator/ramulator2
export SGRAM_GPGPU_BUILD=$PWD/simulator/gpgpu-sim_distribution/build/sgram_fixed
```

If the simulator, Ramulator2, or benchmark trees are moved elsewhere, set these
variables manually before invoking
`simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py`.

## Documentation Map

- `simulator/accelsim_ramulator/README.md`: integration-layer details.
- `simulator/accelsim_ramulator/docs/project_worklog.md`: current project
  journal and open work.
- `simulator/accelsim_ramulator/docs/configuration.md`: how to choose and wire
  AccelSim and Ramulator2 configs.
- `simulator/accelsim_ramulator/docs/ramulator2_backend_validation.md`: backend
  validation notes.
- `simulator/accelsim_ramulator/docs/ramulator2_reject_inflight_notes.md`:
  queue and inflight-pressure interpretation.
- `simulator/accelsim_ramulator/docs/address_mapping_partition_imbalance.md`:
  partition hashing and balance notes.
- `gpu_benchmark/README.md`: benchmark tree layout.

## Current Caveats

- Full natural benchmark runs can take many hours. Start with bounded smoke
  runs before launching `--max-cycle 0 --timeout 0` jobs.
- Large shared-library build products are currently tracked. GitHub may warn
  about files larger than 50 MiB.
- Raw result reports, generated CSVs, and paper/spec archives are intentionally
  kept out of normal commits unless explicitly requested.

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
| A100 HBM2e 1-stack | `a100_1stack` | `configs/ramulator/a100_hbm2e_1stack.yaml` | 22 SMs, 8 x 128-bit channels, 8 MiB L2 |
| A100 HBM2e 5-stack | `a100_5stack` | `configs/ramulator/a100_hbm2e_5stack.yaml` | 108 SMs, 40 x 128-bit channels, 40 MiB L2 |
| H100 HBM3 1/5 | `h100_1stack` | `configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml` | 26 SMs, 16 x 64-bit channels, 10 MiB L2 |
| H100 HBM3 full | `h100_full` | `configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml` | 132 SMs, 80 x 64-bit channels, 50 MiB L2 |

The A100 L2 sizes come from the SM80_A100 L2 config used by the runner:
256 KiB per L2 sub-partition. `a100_1stack` keeps 8 memory partitions with 4
sub-partitions each, so it models 8 MiB L2; the 40-partition A100 configs model
40 MiB L2. `a100_5stack` is the normal 40-channel A100 HBM2e experiment preset
with explicit balanced partition indexing/address mapping.

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
  --out-dir results/h100_full_micro
```

Use `micro_mem_bw` for DRAM-path pressure. The `micro_l2_*` benchmarks can be
served mostly by cache and may produce little or no Ramulator2 DRAM traffic.

## Timing and Stats

The runner defaults are chosen to keep AccelSim and Ramulator2 aligned:

- `--ramulator-ticks-per-dram-cycle auto` reads AccelSim's DRAM clock and
  Ramulator2 `tCK`, then uses a fractional tick accumulator.
- Positive `--queue-limits` values set both AccelSim `SGRAM_QUEUE_LIMIT` and
  the per-run Ramulator2 `read_buffer_size` / `write_buffer_size`.
- `--ramulator-inflight-read-limit auto` scales the bridge-wide read guard as
  `channels * read_buffer_size`.
- `--ramulator-finalize-stats on` enables Ramulator2 internal stats and falls
  back to bridge counters if a process exits before Ramulator2 finalization.
- `--core-granularity-profile on` records core-side coalesced request
  granularity and promotes aggregate ratios into `summary.csv`.
- `--timeout 0` is the default so long-running experiments are not killed before
  Ramulator2 finalizes stats.
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

It currently contains 73 representative benchmarks:

| Class | Count |
| --- | ---: |
| Streaming | 19 |
| Mixed-locality | 36 |
| Irregular | 18 |

Suite sources:

| Manifest suite | Notes |
| --- | --- |
| `polybench`, `rodinia`, `parboil`, `ispass-2009`, `lonestar`, `pannotia`, `proxy-apps`, `dragon-li`, `microbench` | Built through the packaged gpu-app-collection harness and launched as native CUDA binaries through AccelSim's CUDA runtime path. Lonestar main rows use generated medium RMAT `.gr` inputs. |
| `graphBIG` | Standalone GraphBIG GPU checkout using the staged LDBC medium graph dataset. |
| `prepare-nvcomp` | nvCOMP codec candidates staged outside the default build because nvCOMP is an external dependency. Main rows replay prepared Accel-Sim traces. |
| `prepare-cudf`, `prepare-cudf-query` | RAPIDS cuDF microbenchmarks and compact TPC-H-style query workloads. Main rows replay prepared Accel-Sim traces. |
| `prepare-tango` | Sparse checkout of selected Tango DNN models from upstream, with promoted rows validated by trace replay. |

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
| Neural-network inference and layers | `rodinia_backprop`, `tango_cifarnet`, `tango_gru`, `tango_lstm`, `tango_alexnet` |

Graph input sizing:

| Benchmark rows | Main input | Arguments |
| --- | --- | --- |
| `graphbig_bfs_data_warp`, `graphbig_bfs_topo_atomic`, `graphbig_sssp_data_warp` | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset .../LDBC_100k --root 90628` |
| `graphbig_triangle_count`, `graphbig_kcore` | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset .../LDBC_100k` |
| `lonestar_bfs_wlw`, `lonestar_sssp_wln` | `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr` | executable path plus the `.gr` input path |

Additional medium/large graph validation rows live in
`gpu_benchmark/benchmarks/main/manifest.graph_medium_large.tsv`. The detailed
input layout, command arguments, generation path, and validation notes are in
`gpu_benchmark/benchmarks/main/GRAPH_INPUTS.md`.

Trace-driven rows:

`nvcomp_*`, `cudf_*`, and `tango_*` rows do not execute their original native
workload inside the AccelSim runtime interceptor. Their manifest commands call
`gpu_benchmark/scripts/run_accelsim_trace_replay.py --benchmark <name>`. The
helper looks up the benchmark in
`gpu_benchmark/benchmarks/main/trace_manifest.tsv`, resolves the local
`kernelslist.g`, derives an ISA-compatible trace config when needed, and invokes
`accel-sim.out -trace` from the per-run directory created by the normal
AccelSim + Ramulator2 runner.

Trace preparation summary:

| Group | Trace creation path | Trace ISA | Main sizing / scope |
| --- | --- | ---: | --- |
| `nvcomp_*` | Built `nvcomp_codec_bench` from the optional nvCOMP candidate tree, then captured simulator-ready traces with the Accel-Sim NVBit tracer for each codec. | SM86 | Compression-phase codec traces, with trace paths recorded under `/tmp/nvcomp_accelsim_ramulator_traces_comp/...`. |
| `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_join`, `cudf_sort` | Ran RAPIDS cuDF microbenchmarks from `prepare/cudf` with `cudaProfilerStart/Stop` around only the selected operation, then captured Accel-Sim traces with `run_cudf_accelsim_trace.py`. | SM80 | Profiler-scoped 1 MiB synthetic-column traces stored under ignored local `gpu_benchmark/benchmarks/prepare/results/cudf_accelsim_traces_1MiB_20260521/...`. |
| `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` | Ran compact native-cuDF TPC-H-shaped query scripts over synthetic tables with profiler scoping, then captured Accel-Sim traces with `run_cudf_accelsim_trace.py`. | SM80 | Profiler-scoped 64 MiB query traces stored under ignored local `gpu_benchmark/benchmarks/prepare/results/cudf_tpch_accelsim_traces_64MiB_20260521/...`. |
| `tango_*` | Sparse-fetched Tango upstream models, built the selected CUDA models with `CUDA_ARCH=86`, and captured SM86 NVBit traces for H100 1/5 validation. | SM86 | `CifarNet`, `GRU`, `LSTM`, and `AlexNet`; validation trace directories live under `/tmp/tango_*_h100_1stack_validation_sm86_20260522/...`. |

The trace payloads are intentionally not committed. `trace_manifest.tsv` records
the expected local paths, and `.gitignore` keeps the large prepared trace
directories out of GitHub.

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
- `gpu_benchmark/benchmarks/main/GRAPH_INPUTS.md`: GraphBIG and Lonestar input
  arguments, generation, and validation notes.

## Current Caveats

- Full natural benchmark runs can take many hours. Start with bounded smoke
  runs before launching `--max-cycle 0 --timeout 0` jobs.
- Large shared-library build products are currently tracked. GitHub may warn
  about files larger than 50 MiB.
- Raw result reports, generated CSVs, and paper/spec archives are intentionally
  kept out of normal commits unless explicitly requested.

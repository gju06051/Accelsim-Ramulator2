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
    benchmarks/system/        # synthetic microbenchmarks for simulator checks
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

- AccelSim/GPGPU-Sim source. The `build/sgram_fixed/libcudart.so` runtime is
  generated locally by the rebuild script rather than tracked in Git.
- Ramulator2 source. The `libramulator.so` runtime library is generated locally
  by the rebuild script rather than tracked in Git.
- The external memory backend path that connects AccelSim memory partitions to
  Ramulator2.
- HBM2e, HBM3 SID, and HBM4-oriented Ramulator2 YAML configs.
- A100 and H100 AccelSim config variants, including H100 1/5 and full H100
  HBM3 layouts.
- A curated main benchmark set, a separate microbenchmark system-check set, and
  a larger operational benchmark pool.

Generated result directories, trace dumps, replay outputs, runtime shared
libraries, build trees, and large paper/spec archives are not part of normal
commits.

If this repository is cloned on another machine, the git-tracked sources are
not enough for the prepared main trace/graph benchmark set.  Use
`gpu_benchmark/scripts/package_local_artifacts.py` to move the ignored local
payloads as one tarball; the current workstation bundle and optional trace-only
groups are documented in `gpu_benchmark/benchmarks/README.md`. DLRM/GNN/CORAL2
proxy traces, when generated, are moved with `--group trace-official-memory`;
the default main manifest can still run those rows natively from committed
source without that optional trace bundle.

## Quick Start

Build the local runtime shared libraries after a fresh clone or clean checkout:

```bash
./simulator/accelsim_ramulator/scripts/build_runtime_artifacts.sh \
  --cuda /usr/local/cuda-12.3
```

The script regenerates:

- `simulator/gpgpu-sim_distribution/build/sgram_fixed/libcudart.so`
- `simulator/ramulator2/libramulator.so`
- `simulator/accelsim_ramulator/build/ramulator2_bridge/libsgram_ramulator2_bridge.so`

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
  --preset accelsim_ramulator_system_check \
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
  --preset accelsim_ramulator_system_check \
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

## Native vs Ramulator2 Cross-Check

For bridge sanity checks, run the same canonical AccelSim config and benchmark
set once with native AccelSim DRAM and once with the Ramulator2 backend:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend native \
  --preset accelsim_ramulator_system_check \
  --benchmarks micro_mem_bw,micro_mem_lat \
  --gpgpusim-config configs/accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config \
  --config-variant canonical \
  --latencies 1 \
  --queue-limits 64 \
  --max-cycle 10000 \
  --timeout 0 \
  --jobs 2 \
  --out-dir results/crosscheck_native_h100_1stack_10k

./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_system_check \
  --benchmarks micro_mem_bw,micro_mem_lat \
  --gpgpusim-config configs/accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config \
  --config-variant canonical \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --latencies 1 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --max-cycle 10000 \
  --timeout 0 \
  --jobs 2 \
  --out-dir results/crosscheck_ramulator_h100_1stack_10k
```

Compare total read/write requests, row-hit rate, queue pressure, IPC, and host
runtime. Bounded runs can leave Ramulator2 reads outstanding at `max-cycle`, so
completion gaps in this mode are a stop-condition artifact rather than a bridge
failure. A recent 10k-cycle H100 1/5 q64 check showed the same direction for
`micro_mem_bw` and `dlrm_v2_embeddingbag_fixed`: Ramulator2 produced slightly
lower IPC/request progress, but similar high row locality and high queue
pressure.

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

The matrix runner automatically writes a post-run quality report next to each
`summary.csv`:

```text
summary_check.txt
summary_check.json
```

Re-run the checker manually before using an older result directory for reports:

```bash
cd simulator/accelsim_ramulator
./scripts/check_summary.py \
  results/h100_1stack_selected_main/summary.csv \
  --expected-partitions 16 \
  --mode unbounded
```

The checker reports P0/P1/P2 findings for failed statuses, missing Ramulator or
command stats, inactive partitions, read/write completion gaps, zero-request
rows, bounded stop conditions, high partition/channel CV, and high queue
rejection pressure. The runner uses `--summary-check-fail-on never` by default
so experiments finish and leave reports even when warnings exist; manual checker
runs default to failing on P0 findings.

## Benchmark Sets

The default benchmark manifest is:

```text
gpu_benchmark/benchmarks/main/manifest.tsv
```

For manual subset selection, edit:

```text
gpu_benchmark/benchmarks/main/benchmark_selection.tsv
```

Set `run` to `1` for rows to run and `0` for rows to skip. The file includes
the access pattern, memory/compute class, suite, status, and key H100 1/5
metrics for each active and optional benchmark.

It currently contains 42 application/trace benchmarks characterized with the
H100 SXM Samsung HBM3SID 1/5-stack q64 screen. The default set is intentionally
mixed: memory-intensive rows stress the Ramulator2 backend, while
compute-intensive rows keep cache-local, arithmetic-heavy, framework, and
control-flow behavior in the comparison set.

| Access pattern | Memory-intensive | Compute-intensive | Total |
| --- | ---: | ---: | ---: |
| Streaming | 4 | 3 | 7 |
| Mixed-locality | 9 | 9 | 18 |
| Irregular | 12 | 5 | 17 |

Suite sources:

| Manifest suite | Notes |
| --- | --- |
| `polybench`, `rodinia`, `parboil`, `ispass-2009`, `lonestar`, `pannotia`, `proxy-apps`, `dragon-li` | Built through the packaged gpu-app-collection harness and launched as native CUDA binaries through AccelSim's CUDA runtime path. Lonestar main rows use generated medium RMAT `.gr` inputs. |
| `graphBIG` | Standalone GraphBIG GPU checkout using the staged LDBC medium graph dataset. |
| `prepare-nvcomp` | nvCOMP codec candidates staged outside the default build because nvCOMP is an external dependency. The active row replays the larger ANS Accel-Sim trace; smaller codec traces are optional. |
| `prepare-cudf`, `prepare-cudf-query` | RAPIDS cuDF microbenchmarks and compact TPC-H-style query workloads. Active rows replay larger 64 MiB / 128 MiB Accel-Sim traces. |
| `prepare-tango` | Sparse checkout of selected Tango DNN models from upstream. The active main row is the larger AlexNet trace; smaller Tango traces are optional. |
| `prepare-dlrm` | Official-derived native CUDA proxy rows prepared from locally staged MLCommons DLRM-v2/v3 sources. |
| `prepare-gnn` | Official-derived native CUDA proxy rows prepared from locally staged MLCommons R-GAT and gSuite/PubMed sources. |
| `prepare-coral2` | Official-derived native CUDA proxy rows prepared from locally staged CORAL2/RAJAPerf source archives. |

Available application benchmarks by workload field:

The table below covers every application row that can be selected through
`benchmark_selection.tsv`: active rows default to `run=1`, while optional rows
default to `run=0` but can be enabled by flipping that column.

| Field | Active rows | Optional rows |
| --- | --- | --- |
| Dense matrix and regular arrays | `polybench_bicg`, `polybench_atax` | `rodinia_gaussian`, `parboil_mri_q`, `parboil_sgemm` |
| Stencils, grids, meshes, and structured simulation | `polybench_2dconv`, `polybench_3dconv`, `parboil_lbm` | `rodinia_srad_v1`, `rodinia_srad_v2`, `rodinia_lavamd`, `rodinia_myocyte`, `rodinia_nw`, `rodinia_pathfinder`, `proxy_lulesh`, `parboil_cutcp`, `parboil_stencil`, `dragon_amr` |
| Graph and sparse traversal analytics | `graphbig_bfs_data_warp`, `graphbig_bfs_topo_atomic`, `graphbig_sssp_data_warp`, `graphbig_triangle_count`, `lonestar_bfs_wlw`, `lonestar_sssp_wln`, `pannotia_mis`, `pannotia_color_maxmin`, `pannotia_sssp_ell`, `pannotia_pagerank_spmv` | `graphbig_kcore`, `pannotia_fw_block` |
| Search, lookup, and data mining | `ispass_lps`, `ispass_lib`, `proxy_xsbench` | `ispass_nn`, `ispass_nqu`, `ispass_ray`, `dragon_join` |
| Particle, clustering, and filtering | - | `rodinia_streamcluster`, `rodinia_particlefilter_naive` |
| Compression and entropy coding | `nvcomp_ans` | `nvcomp_lz4`, `nvcomp_snappy`, `nvcomp_gdeflate`, `nvcomp_deflate`, `nvcomp_zstd`, `nvcomp_cascaded`, `nvcomp_bitcomp` |
| Columnar dataframe analytics | `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_sort`, `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` | `cudf_join` |
| Neural-network inference and layers | `rodinia_backprop`, `tango_alexnet` | `tango_cifarnet`, `tango_gru`, `tango_lstm` |
| Recommendation embedding and sequence gathers | `dlrm_v2_embeddingbag_fixed`, `dlrm_v2_embeddingbag_quantile`, `dlrm_v3_sequence_gather` | - |
| Graph neural network proxy kernels | `mlperf_rgat_feature_fetch`, `mlperf_rgat_relation_agg`, `gsuite_gcn_mp_pubmed`, `gsuite_sage_mp_pubmed`, `gsuite_gin_wl_pubmed` | - |
| CORAL2 scientific proxy kernels | `coral2_rajaperf_stream_triad`, `coral2_rajaperf_ltimes`, `coral2_rajaperf_energy`, `coral2_rajaperf_planckian`, `coral2_rajaperf_reduce3` | - |

Synthetic memory-system microbenchmarks now live in:

```text
gpu_benchmark/benchmarks/system/manifest.tsv
```

Run them with `--preset accelsim_ramulator_system_check` when validating bridge
counters, queue pressure, latency, bandwidth, cache-path behavior, or atomics.

System-check microbenchmarks:

| Field | Benchmarks |
| --- | --- |
| DRAM bandwidth and request granularity | `micro_mem_bw`, `micro_mem_atom_size` |
| DRAM latency | `micro_mem_lat` |
| L1/L2 cache path | `micro_l1_bw_128`, `micro_l2_bw_32f`, `micro_l2_lat`, `micro_l2_access_grain` |
| Atomics and serialization | `micro_atomic_add_bw_conflict` |

Long-running native PolyBench rows `polybench_fdtd2d`,
`polybench_gramschmidt`, `polybench_covariance`, and `polybench_2mm` are kept
out of the main set until smaller rebuilt PolyBench inputs are available.
Additional functional rows that are too small, cache-fit, or operationally
long-tail are preserved in
`gpu_benchmark/benchmarks/main/manifest.optional.tsv`; the H100 1/5
memory-intensive/compute-intensive characterization and row-level metrics are in
`gpu_benchmark/benchmarks/main/REPRESENTATIVENESS.md`.

Graph input sizing:

| Benchmark rows | Main input | Arguments |
| --- | --- | --- |
| `graphbig_bfs_data_warp`, `graphbig_bfs_topo_atomic`, `graphbig_sssp_data_warp` | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset .../LDBC_100k --root 90628` |
| `graphbig_triangle_count` | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset .../LDBC_100k` |
| `lonestar_bfs_wlw`, `lonestar_sssp_wln` | `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr` | executable path plus the `.gr` input path |

Additional medium/large graph validation rows live in
`gpu_benchmark/benchmarks/main/manifest.graph_medium_large.tsv`. The detailed
input layout, command arguments, generation path, and validation notes are in
`gpu_benchmark/benchmarks/main/GRAPH_INPUTS.md`.

Official-derived native proxy rows:

The promoted DLRM, GNN, and CORAL2 rows run
`gpu_benchmark/benchmarks/prepare/bin/official_memory_proxy` through the normal
AccelSim CUDA runtime interception path. Build the proxy before running these
rows:

```bash
cd gpu_benchmark/benchmarks/prepare
make official_memory_proxy CUDA_ARCH=80
```

The proxy source is committed at
`gpu_benchmark/benchmarks/prepare/src/official_memory_proxy.cu`. It uses
deterministic synthetic inputs with dimensions and memory motifs chosen from the
locally staged official DLRM, GNN, and CORAL2 sources. These rows are intended
for memory-system studies, not MLPerf or CORAL2 compliance reporting. Full
row-by-row arguments are documented in
`gpu_benchmark/benchmarks/main/README.md`.

Trace-driven rows:

`nvcomp_*`, `cudf_*`, and `tango_*` rows do not execute their original native
workload inside the AccelSim runtime interceptor. Their manifest commands call
`gpu_benchmark/scripts/run_accelsim_trace_replay.py --benchmark <name>`. The
helper looks up the benchmark in
`gpu_benchmark/benchmarks/main/trace_manifest.tsv`, resolves the local
`kernelslist.g`, derives an ISA-compatible trace config when needed, and invokes
`accel-sim.out -trace` from the per-run directory created by the normal
AccelSim + Ramulator2 runner.

Trace Preparation Summary:

| Group | Trace creation path | Trace ISA | Main sizing / scope |
| --- | --- | ---: | --- |
| `nvcomp_ans` | Built `nvcomp_codec_bench` from the optional nvCOMP candidate tree, then captured simulator-ready traces with the Accel-Sim NVBit tracer. | SM86 | Active main uses the 4 MiB ANS trace in `gpu_benchmark/benchmarks/prepare/results/nvcomp_accelsim_traces_4MiB/...`; smaller codec rows are optional. |
| `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_sort` | Ran RAPIDS cuDF microbenchmarks from `prepare/cudf` with `cudaProfilerStart/Stop` around only the selected operation, then captured Accel-Sim traces with `run_cudf_accelsim_trace.py`. | SM80 | Active main uses profiler-scoped 64 MiB traces in ignored local `gpu_benchmark/benchmarks/prepare/results/cudf_accelsim_traces_64MiB/...`. |
| `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` | Ran compact native-cuDF TPC-H-shaped query scripts over synthetic tables with profiler scoping, then captured Accel-Sim traces with `run_cudf_accelsim_trace.py`. | SM80 | Active main uses profiler-scoped 128 MiB query traces in ignored local `gpu_benchmark/benchmarks/prepare/results/cudf_tpch_accelsim_traces_128MiB/...`. |
| `tango_alexnet` | Sparse-fetched Tango upstream models, built the selected CUDA model with `CUDA_ARCH=86`, and captured an SM86 NVBit trace for H100 1/5 validation. | SM86 | Active main uses the larger AlexNet trace; smaller Tango traces are optional. |
| `dlrm_*` | Staged MLCommons Inference DLRM-v2/v3 source under ignored local `gpu_benchmark/benchmarks/prepare/dlrm/`, then implemented the committed `official_memory_proxy` embedding-bag, quantile-gather, and sequence-gather modes from those memory motifs. Optional traces are generated with `run_official_memory_accelsim_trace.py`. | SM80 | Native main rows use deterministic synthetic embedding tables/indices. Optional replay paths are recorded in `gpu_benchmark/benchmarks/main/trace_manifest.official_memory.tsv` and packaged with `--group trace-official-memory`. |
| `mlperf_rgat_*`, `gsuite_*` | Staged MLCommons R-GAT source from `prepare/dlrm/inference/graph/R-GAT` plus gSuite/PubMed source under ignored local `gpu_benchmark/benchmarks/prepare/gnn/`, then mapped feature-fetch, relation aggregation, and PubMed message-passing motifs into `official_memory_proxy`. | SM80 | Main rows run native proxy kernels. `mlperf_rgat_relation_agg` and `gsuite_sage_mp_pubmed` defaults are scaled to larger node/edge counts after H100 1/5 L2-fit ablation; optional replay traces use the official-memory trace manifest. |
| `coral2_*` | Staged CORAL2/RAJAPerf source archives under ignored local `gpu_benchmark/benchmarks/prepare/coral2/`, then mapped STREAM, LTimes/Kripke-like tensor contraction, ENERGY, PLANCKIAN, and REDUCE3 motifs into `official_memory_proxy`. | SM80 | Main rows run native proxy kernels with deterministic arrays. Optional replay traces are generated and packaged with the same `trace-official-memory` flow as DLRM/GNN. |

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
- Runtime shared-library build products are intentionally ignored. Rebuild them
  with `simulator/accelsim_ramulator/scripts/build_runtime_artifacts.sh` after
  cloning onto a new machine.
- Raw result reports, generated CSVs, and paper/spec archives are intentionally
  kept out of normal commits unless explicitly requested.

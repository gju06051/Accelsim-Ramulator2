# Benchmark Management

This directory is the user-facing benchmark management area for the
AccelSim + Ramulator2 project.

## Directory Roles

| Path | Role |
| --- | --- |
| `main/manifest.tsv` | Active benchmark list loaded by the runner preset `accelsim_ramulator_main`. |
| `main/manifest.optional.tsv` | Functional-coverage rows moved out of the default list because they are too small, cache-fit, or long-tail on H100 1/5. |
| `main/benchmark_selection.tsv` | User-editable run list. Set `run` to `1` or `0` to choose active/optional rows by access pattern and memory/compute class. |
| `main/trace_manifest.tsv` | Default Accel-Sim trace paths for trace-driven rows; currently points at the larger nvCOMP/cuDF traces plus Tango traces used by the active set. |
| `main/trace_manifest.memory_intensive.tsv` | Regenerated larger trace manifest kept as the explicit source for the default trace manifest. |
| `main/trace_manifest.official_memory.tsv` | Optional DLRM/GNN/CORAL2 proxy trace paths. |
| `main/manifest.official_memory_trace.tsv` | Optional trace-replay manifest for the DLRM/GNN/CORAL2 proxy rows. |
| `main/local/` | Recommended location for new local benchmark binaries, inputs, and wrappers. |
| `system/manifest.tsv` | Synthetic microbenchmarks loaded by `accelsim_ramulator_system_check` for simulator sanity checks. |
| `prepare/` | Isolated staging area for external or generated benchmark candidates before main promotion. |
| `inventory/` | Archived candidate manifests used while building the benchmark pool. |

Do not put large generated traces or run results here. Use
`gpu_benchmark/benchmarks/prepare/results/` for prepared trace artifacts and
`simulator/accelsim_ramulator/results/` for simulator outputs.

## Active Main Set

`main/manifest.tsv` is the source of truth for routine AccelSim + Ramulator2
runs. List it with:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

The current active set has 42 application/trace rows characterized by the H100
SXM Samsung HBM3SID 1/5-stack q64 screen. It intentionally contains both
memory-intensive and compute-intensive workloads:

| Access pattern | Memory-intensive | Compute-intensive | Total |
| --- | ---: | ---: | ---: |
| Streaming | 4 | 3 | 7 |
| Mixed-locality | 9 | 9 | 18 |
| Irregular | 12 | 5 | 17 |

Native rows run CUDA binaries through the
AccelSim runtime interception path. Trace rows run
`gpu_benchmark/scripts/run_accelsim_trace_replay.py --benchmark <name>`, which
replays a prepared `kernelslist.g` through trace-driven AccelSim while keeping
the same Ramulator2 backend environment.

Rows below 100k DRAM requests, cache-fit rows, and known long-tail rows are
preserved in `main/manifest.optional.tsv`. The fixed workload-characterization
table and raw metrics are in `main/REPRESENTATIVENESS.md` and
`main/representativeness_h100_1stack.tsv`.

Microbenchmarks are kept out of the main set. Use
`system/manifest.tsv` or the `accelsim_ramulator_system_check` preset for
bandwidth, latency, cache-path, atomic, and bridge-counter probes.

To run a hand-picked subset, edit `main/benchmark_selection.tsv` and flip the
`run` column. The runner accepts this file directly:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --benchmark-selection-file gpu_benchmark/benchmarks/main/benchmark_selection.tsv \
  --backend ramulator2 \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --jobs 24 \
  --max-cycle 0 \
  --timeout 0 \
  --out-dir results/h100_1stack_selected
```

With the default main preset, selected optional rows are also available because
the runner supplements `manifest.tsv` with `manifest.optional.tsv` when a
selection file is provided.

## Moving Local Artifacts

Large graph inputs, prepared Accel-Sim traces, local PDFs, and simulator
results are intentionally ignored by Git.  To move the benchmark-ready local
state to another clone, package the required repo-relative artifacts from this
repository:

```bash
gpu_benchmark/scripts/package_local_artifacts.py pack \
  --group main-minimal \
  --output /tmp/accelsim_ramulator_main_artifacts.tar
```

Then extract it at the root of the fresh clone:

```bash
gpu_benchmark/scripts/package_local_artifacts.py unpack \
  /tmp/accelsim_ramulator_main_artifacts.tar \
  --destination /path/to/new/Accelsim-Ramulator
```

`main-minimal` contains the staged payloads needed by the active main manifest:
`LDBC_100k`, `rmat16.sym.gr`, the larger nvCOMP/cuDF trace directories,
the default Tango traces, and the trace replay runtime. Use
`--group trace-legacy-default` only if you need the older small validation
trace set. Use `--group trace-official-memory` for optional DLRM/GNN/CORAL2 proxy traces generated from
`run_official_memory_accelsim_trace.py`, or `--group all-traces` to collect all
prepared trace directories together. If the optional official-memory traces
have not been generated yet, use `--allow-missing` with `all-traces` or package
the explicit trace groups you already have. `--group all-inputs` still means
the main manifest payloads, extra memory trace group, and large graph inputs
together. Check a clone with:

```bash
gpu_benchmark/scripts/package_local_artifacts.py verify --group main-minimal
```

A historical `main-minimal` bundle may exist on this workstation, but the
active manifest now uses the larger trace paths listed in `trace_manifest.tsv`.
Regenerate the bundle after this characterization update, then extract it at
the new clone root and run the verifier:

```bash
gpu_benchmark/scripts/package_local_artifacts.py pack \
  --group main-minimal \
  --output /tmp/accelsim_ramulator_main_artifacts.tar

gpu_benchmark/scripts/package_local_artifacts.py unpack \
  /tmp/accelsim_ramulator_main_artifacts.tar \
  --destination /path/to/new/Accelsim-Ramulator

cd /path/to/new/Accelsim-Ramulator
gpu_benchmark/scripts/package_local_artifacts.py verify --group main-minimal
```

## Trace Generation Summary

Trace-driven rows are used when a workload cannot be represented well by the
native CUDA runtime path, or when the workload depends on prebuilt libraries
such as nvCOMP, RAPIDS cuDF, or Tango model code.

| Group | How traces were generated | Default replay | Optional/legacy replay |
| --- | --- | --- | --- |
| `nvcomp_*` | `gpu_benchmark/scripts/run_nvcomp_accelsim_trace.py` runs `prepare/bin/nvcomp_codec_bench` under the Accel-Sim NVBit tracer. The promoted flow uses one compression iteration, 4 MiB input, 64 KiB chunks, `DYNAMIC_KERNEL_RANGE=3`, SM86 trace replay. | `main/trace_manifest.tsv` points at `prepare/results/nvcomp_accelsim_traces_4MiB/<codec>/traces/kernelslist.g`. | `--group trace-legacy-default` packages the older codec validation traces. |
| `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_sort` | `gpu_benchmark/scripts/run_cudf_accelsim_trace.py --workload micro` runs `prepare/cudf/cudf_microbench.py` in the RAPIDS Python environment. It profiles only the `cudaProfilerStart/Stop` operation region, not input construction. | 64 MiB profiler-scoped traces, SM80. | The older 1 MiB traces are kept in the legacy trace group. |
| `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` | `gpu_benchmark/scripts/run_cudf_accelsim_trace.py --workload tpch` runs synthetic TPC-H-shaped cuDF queries from `prepare/cudf/cudf_tpch_bench.py`. These are deterministic query-shaped GPU workloads, not compliance TPC-H. | 128 MiB profiler-scoped traces, SM80. | The older 64 MiB traces are kept in the legacy trace group. |
| `tango_alexnet` | Prepared SM86 Accel-Sim trace from the larger Tango validation flow. | Existing SM86 AlexNet trace. | Smaller Tango rows are preserved in `manifest.optional.tsv`. |
| `dlrm_*`, `mlperf_rgat_*`, `gsuite_*`, `coral2_*` | Main rows normally run native `official_memory_proxy`. Optional trace rows are generated by `gpu_benchmark/scripts/run_official_memory_accelsim_trace.py`, which traces the proxy under the Accel-Sim NVBit tracer and writes `main/trace_manifest.official_memory.tsv`. | Not used by default main runs. | Optional trace set under `prepare/results/official_memory_accelsim_traces/`. |

Regenerate the staged larger trace manifest with:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py
```

`main/trace_manifest.tsv` is intentionally aligned to this larger trace
manifest for the active set.

Generate the optional DLRM/GNN/CORAL2 proxy traces with:

```bash
gpu_benchmark/scripts/run_official_memory_accelsim_trace.py --force
```

Package only those optional traces for another clone with:

```bash
gpu_benchmark/scripts/package_local_artifacts.py pack \
  --group trace-official-memory \
  --output /tmp/official_memory_accelsim_traces.tar
```

After unpacking, run the trace-replay variant with
`main/manifest.official_memory_trace.tsv`. The default main manifest still uses
the native proxy binary, so these optional traces are only needed when you want
DLRM/GNN/CORAL2 to follow the same replay path as nvCOMP/cuDF/Tango.

## Official-Derived Native Proxy Rows

The promoted `prepare-dlrm`, `prepare-gnn`, and `prepare-coral2` rows are
native CUDA proxy kernels built from
`gpu_benchmark/benchmarks/prepare/src/official_memory_proxy.cu`. They are not
MLPerf or CORAL2 submission-compliance workloads. They preserve memory-system
motifs from the locally staged official sources while staying small and stable
enough for AccelSim + Ramulator2.

Preparation details:

| Group | Local source used while preparing | What was preserved | How it runs now |
| --- | --- | --- | --- |
| DLRM | Local MLCommons DLRM-v2 and DLRM-v3 checkouts under `prepare/dlrm/` | Embedding-bag fanout, high-fanout quantile gather, and long sequence gather structure | Native `official_memory_proxy` embedding gather kernels with deterministic synthetic tables and indices |
| GNN | Local MLCommons R-GAT and gSuite/PubMed checkouts under `prepare/dlrm/inference/graph/R-GAT` and `prepare/gnn/gsuite` | Irregular neighbor feature fetch, relation-aware gather, and PubMed-derived/scaled node, edge, and feature dimensions | Native feature-fetch and relation-gather kernels with destination-indexed edge outputs |
| CORAL2 | Local CORAL2/RAJAPerf source archives under `prepare/coral2/` | STREAM, LTimes/Kripke-like tensor contraction, ENERGY, PLANCKIAN, and REDUCE3 access motifs | Native CUDA kernels with deterministic synthetic arrays |

The source checkouts/archives above are preparation provenance and are not
required to run the promoted rows after the proxy source is committed. Build
the runnable binary with:

```bash
cd gpu_benchmark/benchmarks/prepare
make official_memory_proxy CUDA_ARCH=80
```

Two AccelSim compatibility choices are intentional. The proxy uses shared CUDA
runtime linkage so AccelSim can intercept launches, and it initializes inputs
on the host before `cudaMemcpy` so bounded validation reaches the benchmark
kernel first. The relation-GNN rows avoid CUDA 12 `red.global.add.f32` because
that PTX atomic reduction form crashed the current AccelSim PTX path during
validation.

If a fresh clone should use these rows as trace replay instead of native CUDA
interception, unpack the `trace-official-memory` artifact group and run
`gpu_benchmark/benchmarks/main/manifest.official_memory_trace.tsv`. Its trace
paths are recorded in `main/trace_manifest.official_memory.tsv`.

## Benchmark Run Reference

The table below records how each active or optional benchmark row is run:
native CUDA binary or trace replay, the arguments passed, and the input files
or generated trace source. Use `main/manifest.tsv` for the active mixed
memory-intensive/compute-intensive set and `main/manifest.optional.tsv` for
rows that were moved out by the H100 1/5 size, cache-fit, or long-tail screen.

### polybench

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `polybench_2dconv` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Structured sliding-window stencil access. |
| `polybench_3dconv` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Structured 3D sliding-window stencil access. |
| `polybench_bicg` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Dense matrix-vector style access. |
| `polybench_atax` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Dense matrix-vector style access. |

`polybench_fdtd2d`, `polybench_gramschmidt`, `polybench_covariance`, and
`polybench_2mm` remain in inventory manifests only. The packaged binaries do
not expose simple runtime input-size controls and became long-tail unbounded
runs.

### graphBIG

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `graphbig_bfs_data_warp` | Native CUDA binary through AccelSim runtime interception. | Args: `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k --root 90628`. Input: `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`. | Frontier-driven graph traversal on the medium LDBC graph. |
| `graphbig_bfs_topo_atomic` | Native CUDA binary through AccelSim runtime interception. | Args: `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k --root 90628`. Input: `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`. | Topology-driven BFS with atomics on the medium LDBC graph. |
| `graphbig_sssp_data_warp` | Native CUDA binary through AccelSim runtime interception. | Args: `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k --root 90628`. Input: `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`. | Data-dependent SSSP traversal; edge weights are initialized by the benchmark. |
| `graphbig_triangle_count` | Native CUDA binary through AccelSim runtime interception. | Args: `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`. Input: `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`. | Triangle counting over the medium LDBC graph. |
| `graphbig_kcore` | Native CUDA binary through AccelSim runtime interception. | Args: `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`. Input: `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`. | K-core traversal over the medium LDBC graph. |

`main/GRAPH_INPUTS.md` records the graph sizes. `LDBC_100k` has 100,000
vertices and 2,887,796 directed edges. Root `90628` was selected as a high
degree vertex for BFS/SSSP validation.

### ispass-2009

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `ispass_lps` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Data-dependent search/access benchmark. |
| `ispass_lib` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Structured library benchmark. |
| `ispass_nn` | Native CUDA binary through AccelSim runtime interception. | Args: `28`. Generated input directory: `gpu_benchmark/generated_inputs/ispass_nn`. | The runner creates minimal NN weight/image files in the run directory when needed. |
| `ispass_nqu` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Structured N-Queens-style combinatorial search. |
| `ispass_ray` | Native CUDA binary through AccelSim runtime interception. | Args: `256 256`. | Ray-style structured traversal at 256x256. |

### rodinia

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `rodinia_streamcluster` | Native CUDA binary through AccelSim runtime interception. | Args: `10 20 256 65536 65536 1000 none output.txt 1`. | Streamcluster with generated input points and output file `output.txt`. A smaller `32768`/`16384` candidate is under validation but not yet promoted. |
| `rodinia_backprop` | Native CUDA binary through AccelSim runtime interception. | Args: `65536`. | Backprop layer benchmark with 65,536 inputs. |
| `rodinia_srad_v1` | Native CUDA binary through AccelSim runtime interception. | Args: `10 0.5 502 458`. | SRAD v1 image diffusion stencil. |
| `rodinia_srad_v2` | Native CUDA binary through AccelSim runtime interception. | Args: `512 512 0 511 0 511 0.5 2`. | SRAD v2 scaled to a 512x512 image region. |
| `rodinia_gaussian` | Native CUDA binary through AccelSim runtime interception. | Args: `-s 256 -q`. | Gaussian elimination with generated 256-sized input, quiet mode. |
| `rodinia_lavamd` | Native CUDA binary through AccelSim runtime interception. | Args: `-boxes1d 10`. | LavaMD particle-neighborhood benchmark. |
| `rodinia_myocyte` | Native CUDA binary through AccelSim runtime interception. | Args: `100 1 1`. Generated input files: `data/myocyte/y.txt` and `data/myocyte/params.txt` in the run tree. | The runner creates simple deterministic myocyte parameter files. |
| `rodinia_nw` | Native CUDA binary through AccelSim runtime interception. | Args: `512 10`. | Needleman-Wunsch dynamic programming. |
| `rodinia_particlefilter_naive` | Native CUDA binary through AccelSim runtime interception. | Args: `-x 128 -y 128 -z 10 -np 1000`. | Particle filter gather/scatter representative. |
| `rodinia_pathfinder` | Native CUDA binary through AccelSim runtime interception. | Args: `1000 1000 20`. | Grid dynamic-programming pathfinder with generated input dimensions. |

`rodinia_particlefilter_float` is excluded because it crashed in validation.

### proxy-apps

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `proxy_xsbench` | Native CUDA binary through AccelSim runtime interception. | Args: `12 small 0`. | XSBench randomized cross-section lookup using the small profile. |
| `proxy_lulesh` | Native CUDA binary through AccelSim runtime interception. | Args: `(no arguments)`. | Current binary does not appear to honor `-s`/`-i`; reduced-size candidates behaved like the default. Treat as a long-tail row unless rebuilt. |

### parboil

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `parboil_cutcp` | Native CUDA binary through AccelSim runtime interception. | Args: `-i gpu_benchmark/common/gpu-app-collection-harness/data_dirs/parboil/datasets/cutcp/small/input/watbox.sl40.pqr -o parboil_cutcp_lattice.dat`. | Cutoff Coulomb potential over the Parboil small `watbox.sl40.pqr` input. |
| `parboil_stencil` | Native CUDA binary through AccelSim runtime interception. | Args: `-i gpu_benchmark/common/gpu-app-collection-harness/data_dirs/parboil/datasets/stencil/small/input/128x128x32.bin -o parboil_stencil.out 128 128 32 100`. | Structured stencil over the Parboil small 128x128x32 input for 100 timesteps. |
| `parboil_lbm` | Native CUDA binary through AccelSim runtime interception. | Args: `-i gpu_benchmark/common/gpu-app-collection-harness/data_dirs/parboil/datasets/lbm/short/input/120_120_150_ldc.of -o parboil_lbm.out 100`. | LBM short dataset with 100 timesteps. Shorter timestep candidates are under validation but not yet promoted. |
| `parboil_mri_q` | Native CUDA binary through AccelSim runtime interception. | Args: `-i gpu_benchmark/common/gpu-app-collection-harness/data_dirs/parboil/datasets/mri-q/small/input/32_32_32_dataset.bin -o parboil_mri_q.out`. | Dense numerical kernel over the Parboil small MRI-Q input. |
| `parboil_sgemm` | Native CUDA binary through AccelSim runtime interception. | Args: `-i gpu_benchmark/common/gpu-app-collection-harness/data_dirs/parboil/datasets/sgemm/small/input/matrix1.txt,gpu_benchmark/common/gpu-app-collection-harness/data_dirs/parboil/datasets/sgemm/small/input/matrix2.txt,gpu_benchmark/common/gpu-app-collection-harness/data_dirs/parboil/datasets/sgemm/small/input/matrix2t.txt -o parboil_sgemm.out`. | SGEMM over Parboil small matrix files. |

### lonestar

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `lonestar_bfs_wlw` | Native CUDA binary through AccelSim runtime interception. | Args/input: `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr`. | Worklist BFS over generated RMAT16. |
| `lonestar_sssp_wln` | Native CUDA binary through AccelSim runtime interception. | Args/input: `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr`. | Worklist SSSP over generated RMAT16 with 32-bit edge weights. |

`rmat16.sym.gr` is generated by
`gpu_benchmark/scripts/generate_lonestar_rmat_gr.py --scale 16 --edge-factor 16`
and has 65,536 vertices and 1,048,450 edges.

### pannotia

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `pannotia_mis` | Native CUDA binary through AccelSim runtime interception. | Args/input: `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/pannotia/mis/data/ecology1.graph 1`. | Maximal independent set over `ecology1.graph`. |
| `pannotia_color_maxmin` | Native CUDA binary through AccelSim runtime interception. | Args/input: `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/pannotia/color_maxmin/data/ecology1.graph 1`. | Max-min graph coloring over `ecology1.graph`. |
| `pannotia_sssp_ell` | Native CUDA binary through AccelSim runtime interception. | Args/input: `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/pannotia/sssp_ell/data/USA-road-d.NY.gr 0`. | ELL SSSP over the DIMACS NY road graph from source vertex 0. |
| `pannotia_pagerank_spmv` | Native CUDA binary through AccelSim runtime interception. | Args/input: `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/pannotia/pagerank_spmv/data/coAuthorsDBLP.graph 1`. | PageRank expressed through SpMV-like traversal. |
| `pannotia_fw_block` | Native CUDA binary through AccelSim runtime interception. | Args/input: `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/pannotia/fw_block/data/256_16384.gr`. | Blocked Floyd-Warshall graph dynamic programming. |

### dragon-li

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `dragon_join` | Native CUDA binary through AccelSim runtime interception. | Args: `-l 65536 -r 65536 -m 65536`. | Join kernel over generated left/right/match arrays. |
| `dragon_amr` | Native CUDA binary through AccelSim runtime interception. | Args: `-s 4096 -r 2`. | Adaptive mesh refinement over generated hierarchical grid data. |

### Official-Derived Memory Proxy Rows

All rows below run the native CUDA binary
`gpu_benchmark/benchmarks/prepare/bin/official_memory_proxy` through AccelSim
runtime interception. Build it from
`gpu_benchmark/benchmarks/prepare/src/official_memory_proxy.cu` with
`make official_memory_proxy CUDA_ARCH=80`.

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `dlrm_v2_embeddingbag_fixed` | Native CUDA proxy through AccelSim runtime interception. | `--mode dlrm_embedding_fixed --bags 32768 --lookups 32 --dim 64 --entries 262144 --iters 1`. Inputs are deterministic synthetic embedding tables and multi-hot indices. | Prepared from local MLCommons DLRM-v2 settings; fixed fanout embedding-bag gather/reduce. |
| `dlrm_v2_embeddingbag_quantile` | Native CUDA proxy through AccelSim runtime interception. | `--mode dlrm_embedding_quantile --bags 16384 --lookups 100 --dim 64 --entries 262144 --iters 1`. Inputs are deterministic synthetic embedding tables and high-fanout indices. | Prepared from DLRM-v2 high-fanout quantile behavior; strongest request/KI row in bounded 1/5-stack smoke. |
| `dlrm_v3_sequence_gather` | Native CUDA proxy through AccelSim runtime interception. | `--mode dlrm_v3_sequence_gather --sequences 32768 --seq-len 64 --dim 32 --entries 524288 --iters 1`. Inputs are deterministic synthetic sequence indices. | Prepared from DLRM-v3 sequential recommendation gather structure. |
| `mlperf_rgat_feature_fetch` | Native CUDA proxy through AccelSim runtime interception. | `--mode gnn_feature_fetch --edges 262144 --nodes 65536 --dim 64 --iters 1`. Inputs are synthetic graph edge sources and node features. | Prepared from MLCommons R-GAT/IGBH-style irregular neighbor feature fetch. |
| `mlperf_rgat_relation_agg` | Native CUDA proxy through AccelSim runtime interception. | `--mode gnn_relation_agg --edges 1048576 --nodes 262144 --dim 32 --relations 4 --iters 1`. Inputs are synthetic src/dst/relation arrays, features, and relation weights. | Prepared from R-GAT relation-aware aggregation; writes destination-indexed edge outputs instead of atomics for AccelSim PTX stability. The promoted size uses a roughly 32 MiB feature working set after H100 1/5 cache-sensitivity ablation. |
| `gsuite_gcn_mp_pubmed` | Native CUDA proxy through AccelSim runtime interception. | `--mode gsuite_gcn_mp_pubmed --edges 44338 --nodes 19717 --dim 500 --iters 1`. Inputs use synthetic PubMed-shaped graph dimensions. | Prepared from gSuite PubMed GCN message-passing dimensions. |
| `gsuite_sage_mp_pubmed` | Native CUDA proxy through AccelSim runtime interception. | `--mode gsuite_sage_mp_pubmed --edges 524288 --nodes 262144 --dim 128 --relations 4 --iters 1`. Inputs use synthetic scaled PubMed-style graph dimensions. | Prepared from gSuite PubMed SAGE-style aggregation; destination-indexed edge outputs avoid current PTX atomic crash. The promoted size uses a roughly 128 MiB feature working set after H100 1/5 cache-sensitivity ablation. |
| `gsuite_gin_wl_pubmed` | Native CUDA proxy through AccelSim runtime interception. | `--mode gsuite_gin_wl_pubmed --edges 44338 --nodes 19717 --dim 256 --iters 1`. Inputs use synthetic PubMed-shaped graph dimensions. | Prepared from gSuite GIN/WL-style feature gather dimensions. |
| `coral2_rajaperf_stream_triad` | Native CUDA proxy through AccelSim runtime interception. | `--mode coral_stream_triad --elements 4194304 --iters 3`. Inputs are deterministic synthetic arrays. | Prepared from RAJAPerf STREAM TRIAD. |
| `coral2_rajaperf_ltimes` | Native CUDA proxy through AccelSim runtime interception. | `--mode coral_ltimes --zones 8192 --groups 32 --dirs 32 --moments 8 --iters 1`. Inputs are deterministic synthetic `phi` and `ell` arrays. | Prepared from CORAL2 transport/Kripke-like LTimes tensor contraction. |
| `coral2_rajaperf_energy` | Native CUDA proxy through AccelSim runtime interception. | `--mode coral_energy --elements 4194304 --iters 2`. Inputs are deterministic synthetic hydro arrays. | Prepared from RAJAPerf ENERGY-style hydro update. |
| `coral2_rajaperf_planckian` | Native CUDA proxy through AccelSim runtime interception. | `--mode coral_planckian --elements 1048576 --groups 16 --iters 1`. Inputs are deterministic synthetic temperature arrays. | Prepared from RAJAPerf PLANCKIAN-style grouped physics table computation; bounded smoke shows low early request/KI, so treat as functional CORAL2 coverage rather than a strong memory-pressure row. |
| `coral2_rajaperf_reduce3` | Native CUDA proxy through AccelSim runtime interception. | `--mode coral_reduce3 --elements 4194304 --iters 2`. Inputs are deterministic synthetic arrays and block partial output. | Prepared from RAJAPerf REDUCE3_INT-style multi-array reduction. |

The promoted proxy rows passed H100 1/5-stack Samsung HBM3SID q64 bounded
validation with `status_counts=MAX_CYCLE_OK:13`. The validation result is
`simulator/accelsim_ramulator/results/h100_1stack_official_memory_smoke_q64_20260526_v6/summary.csv`.

### nvCOMP Trace Rows

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `nvcomp_lz4` | Optional trace replay. | `--benchmark nvcomp_lz4`; larger trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_lz4_4MiB/traces/kernelslist.g`. | Functional optional row; still below the H100 1/5 100k-request cutoff. |
| `nvcomp_snappy` | Optional trace replay. | `--benchmark nvcomp_snappy`; larger trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_snappy_4MiB/traces/kernelslist.g`. | Functional optional row; still below the H100 1/5 100k-request cutoff. |
| `nvcomp_gdeflate` | Optional trace replay. | `--benchmark nvcomp_gdeflate`; larger trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_gdeflate_4MiB/traces/kernelslist.g`. | Functional optional row; still below the H100 1/5 100k-request cutoff. |
| `nvcomp_deflate` | Optional trace replay. | `--benchmark nvcomp_deflate`; larger trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_deflate_4MiB/traces/kernelslist.g`. | Functional optional row; still below the H100 1/5 100k-request cutoff. |
| `nvcomp_zstd` | Optional trace replay. | `--benchmark nvcomp_zstd`; larger trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_zstd_4MiB/traces/kernelslist.g`. | Functional optional row; still below the H100 1/5 100k-request cutoff. |
| `nvcomp_cascaded` | Optional trace replay. | `--benchmark nvcomp_cascaded`; larger trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_cascaded_4MiB/traces/kernelslist.g`. | Functional optional row; still below the H100 1/5 100k-request cutoff. |
| `nvcomp_bitcomp` | Optional trace replay. | `--benchmark nvcomp_bitcomp`; larger trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_bitcomp_4MiB/traces/kernelslist.g`. | Near-threshold optional row at roughly 93k H100 1/5 DRAM requests. |
| `nvcomp_ans` | Active trace replay. | `--benchmark nvcomp_ans`; default trace path: `prepare/results/nvcomp_accelsim_traces_4MiB/nvcomp_ans_4MiB/traces/kernelslist.g`. | ANS entropy-coding trace; active memory-intensive nvCOMP row. |

### Tango Trace Rows

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `tango_cifarnet` | Optional trace replay. | `--benchmark tango_cifarnet`; trace `prepare/results/tango_h100_1stack_validation_sm86_20260522/traces/tango_cifarnet/traces/kernelslist.g`. | Functional SM86 CifarNet trace, but too small for the active H100 1/5 set. |
| `tango_gru` | Optional trace replay. | `--benchmark tango_gru`; trace `prepare/results/tango_h100_1stack_validation_sm86_20260522/traces/tango_gru/traces/kernelslist.g`. | Functional SM86 GRU trace, but too small for the active H100 1/5 set. |
| `tango_lstm` | Optional trace replay. | `--benchmark tango_lstm`; trace `prepare/results/tango_h100_1stack_validation_sm86_20260522/traces/tango_lstm/traces/kernelslist.g`. | Dense but too small for stable memory-system statistics. |
| `tango_alexnet` | Main trace replay. | `--benchmark tango_alexnet`; trace `prepare/results/tango_large_h100_1stack_validation_sm86_20260522/traces/tango_alexnet/traces/kernelslist.g`. | SM86 AlexNet trace from the larger Tango validation flow. |

### cuDF Micro Trace Rows

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `cudf_filter` | Main trace replay. | `--benchmark cudf_filter`; default trace: `prepare/results/cudf_accelsim_traces_64MiB/cudf_filter_64MiB/traces/kernelslist.g`. | Boolean mask plus row gather, profiler-scoped to the cuDF operation. |
| `cudf_project` | Main trace replay. | `--benchmark cudf_project`; default trace: `prepare/results/cudf_accelsim_traces_64MiB/cudf_project_64MiB/traces/kernelslist.g`. | Column arithmetic / elementwise transform. |
| `cudf_groupby` | Main trace replay. | `--benchmark cudf_groupby`; default trace: `prepare/results/cudf_accelsim_traces_64MiB/cudf_groupby_64MiB/traces/kernelslist.g`. | Hash/group aggregation. |
| `cudf_join` | Optional trace replay. | `--benchmark cudf_join`; default trace: `prepare/results/cudf_accelsim_traces_64MiB/cudf_join_64MiB/traces/kernelslist.g`. | Functional hash join trace, but below the H100 1/5 100k-request cutoff. |
| `cudf_sort` | Active trace replay. | `--benchmark cudf_sort`; default trace: `prepare/results/cudf_accelsim_traces_64MiB/cudf_sort_64MiB/traces/kernelslist.g`. | Sort/radix pipeline; active memory-intensive cuDF row. |

The cuDF micro traces are generated with:

```bash
gpu_benchmark/scripts/run_cudf_accelsim_trace.py \
  --workload micro \
  --op <filter|project|groupby|join|sort> \
  --size 64MiB \
  --out-dir gpu_benchmark/benchmarks/prepare/results/cudf_accelsim_traces_64MiB
```

### cuDF TPC-H-Style Trace Rows

| Benchmark | How it runs | Arguments and input | Notes |
| --- | --- | --- | --- |
| `cudf_tpch_q1` | Main trace replay. | `--benchmark cudf_tpch_q1`; default trace: `prepare/results/cudf_tpch_accelsim_traces_128MiB/cudf_tpch_q1_128MiB/traces/kernelslist.g`. | Pricing summary shape: filter, projection, groupby aggregation, sort. |
| `cudf_tpch_q3` | Main trace replay. | `--benchmark cudf_tpch_q3`; default trace: `prepare/results/cudf_tpch_accelsim_traces_128MiB/cudf_tpch_q3_128MiB/traces/kernelslist.g`. | Shipping-priority shape: joins, revenue aggregation, top-k sort. |
| `cudf_tpch_q6` | Main trace replay. | `--benchmark cudf_tpch_q6`; default trace: `prepare/results/cudf_tpch_accelsim_traces_128MiB/cudf_tpch_q6_128MiB/traces/kernelslist.g`. | Revenue scan shape: selective filter and reduction. |
| `cudf_tpch_q10` | Main trace replay. | `--benchmark cudf_tpch_q10`; default trace: `prepare/results/cudf_tpch_accelsim_traces_128MiB/cudf_tpch_q10_128MiB/traces/kernelslist.g`. | Returned-item reporting shape: joins, aggregation, top-k sort. |

The TPC-H-style traces are generated with:

```bash
gpu_benchmark/scripts/run_cudf_accelsim_trace.py \
  --workload tpch \
  --query <q1|q3|q6|q10> \
  --size 128MiB \
  --out-dir gpu_benchmark/benchmarks/prepare/results/cudf_tpch_accelsim_traces_128MiB
```

## Add A Benchmark

1. Create a directory under `main/local/`:

```text
gpu_benchmark/benchmarks/main/local/my_benchmark/
  bin/my_benchmark
  input/
  README.md
```

2. Make sure the executable can run from an AccelSim run directory. Any input
   path in the manifest should start with `gpu_benchmark/...` so the runner can
   expand it to an absolute path.

3. Add one row to `main/manifest.tsv`.

The TSV schema is:

```text
name    suite    expected_class    workdir    command    main_reason
```

Field meanings:

| Field | Meaning |
| --- | --- |
| `name` | Unique benchmark id used by `--benchmarks` and result directories. |
| `suite` | Suite or group name, for example `local`, `rodinia`, or `graphBIG`. |
| `expected_class` | One of `Streaming`, `Mixed-locality`, or `Irregular`. |
| `workdir` | Benchmark source directory used to resolve relative executable paths. |
| `command` | Executable and arguments. Use `gpu_benchmark/...` paths for repo-local inputs. |
| `main_reason` | Short reason this benchmark belongs in the active shared set. |

4. Check that the runner can load the manifest:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

5. Run only the new benchmark first:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks my_benchmark \
  --latencies 0 \
  --queue-limits 64 \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --max-cycle 50000 \
  --timeout 600 \
  --out-dir results/local_my_benchmark_smoke
```

## Promotion Policy

Keep experimental additions in `main/local/` or `prepare/` until they pass a
bounded AccelSim + Ramulator2 run and produce Ramulator metrics. If a benchmark
becomes part of the stable shared set, add the row to `main/manifest.tsv`,
document its arguments and input here, and record any characterization notes
in `main/REPRESENTATIVENESS.md`.

For larger graph inputs or generated traces, keep payloads out of Git unless
there is a specific reason to version them. Commit the manifest row, generation
script, and documentation instead.

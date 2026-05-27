# Main Benchmark Set

`manifest.tsv` is the active AccelSim + Ramulator2 benchmark list. The
simulator runner preset `accelsim_ramulator_main` loads this file directly.

The current active set has 42 application/trace rows after applying the H100
SXM Samsung HBM3SID 1/5-stack q64 characterization screen. It intentionally
keeps both memory-intensive and compute-intensive rows:

| Access pattern | Memory-intensive | Compute-intensive | Total |
| --- | ---: | ---: | ---: |
| Streaming | 4 | 3 | 7 |
| Mixed-locality | 9 | 9 | 18 |
| Irregular | 12 | 5 | 17 |

Rows that are too small, cache-fit, or long-tail remain available in
`manifest.optional.tsv`.

## How To Run

List the active rows:

```bash
cd ../../../simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

Choose rows with the editable selection file:

```bash
cd ../../../simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --benchmark-selection-file gpu_benchmark/benchmarks/main/benchmark_selection.tsv \
  --list-benchmarks
```

In `benchmark_selection.tsv`, set `run` to `1` for rows to run and `0` for
rows to skip. The file includes both active and optional rows, grouped by
`access_pattern` and `intensity_class`; optional rows default to `0`.

Run one benchmark through the H100 SXM Samsung HBM3 1/5-stack config:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --preset accelsim_ramulator_main \
  --benchmarks <benchmark-name> \
  --latencies 0 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --gpgpusim-host-timing on \
  --max-cycle 0 \
  --timeout 0 \
  --jobs 1 \
  --out-dir results/<run-name>
```

Run the full-stack H100 SXM Samsung HBM3 config by changing:

```bash
--config-variant h100_full
--ramulator-config configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml
```

For full row-by-row benchmark arguments, inputs, and trace provenance, see
`../README.md`.

## Manifest Files

| File | Role |
| --- | --- |
| `manifest.tsv` | Active main run list. |
| `manifest.optional.tsv` | Optional functional-coverage rows moved out of the active set by the H100 1/5 size, cache-fit, or long-tail screen. |
| `benchmark_selection.tsv` | User-editable 1/0 benchmark selection list with access-pattern and memory/compute characterization columns. |
| `manifest.official_memory_trace.tsv` | Optional trace-replay run list for DLRM/GNN/CORAL2 proxy rows. |
| `../system/manifest.tsv` | Synthetic microbenchmarks for simulator and memory-system sanity checks. |
| `trace_manifest.tsv` | Default trace replay paths; aligned to the larger nvCOMP/cuDF traces plus Tango AlexNet. |
| `trace_manifest.memory_intensive.tsv` | Explicit generated source for the larger nvCOMP/cuDF trace paths. |
| `trace_manifest.official_memory.tsv` | Optional DLRM/GNN/CORAL2 proxy trace paths. |
| `manifest.graph_medium_large.tsv` | Extra GraphBIG/Lonestar medium and large validation rows. |
| `GRAPH_INPUTS.md` | GraphBIG/Lonestar input sizes, arguments, and generation notes. |
| `REPRESENTATIVENESS.md` | Current memory-intensive/compute-intensive workload characterization. |
| `representativeness_h100_1stack.tsv` | Machine-readable H100 1/5 metric table used to characterize active and optional rows. |
| `../prepare/OFFICIAL_MEMORY_BENCHMARKS.md` | Source provenance and validation notes for the promoted DLRM/GNN/CORAL2 proxy rows. |

## Native And Trace Rows

Native rows launch CUDA binaries through the AccelSim runtime interception path.
The active set includes selected PolyBench, GraphBIG, ISPASS,
Rodinia, Parboil, Lonestar, Pannotia, proxy-app, and promoted
DLRM/GNN/CORAL2 `official_memory_proxy` rows. Additional functional rows from
Rodinia, Parboil, Dragon-Li, ISPASS, nvCOMP, cuDF, and Tango are retained in
`manifest.optional.tsv`.

The official-derived proxy binary is not checked in. Build it before running
the DLRM/GNN/CORAL2 rows:

```bash
cd ../../../gpu_benchmark/benchmarks/prepare
make official_memory_proxy CUDA_ARCH=80
```

The proxy is built with shared CUDA runtime linkage so AccelSim can intercept
the launches. Its inputs are initialized on the host and copied to the device,
so the first simulated launch is the benchmark kernel rather than an input-fill
kernel.

## Promoted DLRM/GNN/CORAL2 Rows

These rows were prepared from locally staged official sources, but they are
proxy kernels rather than compliance workloads. The source checkouts and
archives under `../prepare/dlrm/`, `../prepare/gnn/`, and `../prepare/coral2/`
were used to choose dimensions and memory access motifs; the runnable main rows
only need the committed `official_memory_proxy.cu` source and the built binary.

Build before running:

```bash
cd ../../../gpu_benchmark/benchmarks/prepare
make official_memory_proxy CUDA_ARCH=80
```

Preparation choices:

| Group | Preparation source | Main-row behavior |
| --- | --- | --- |
| DLRM | MLCommons DLRM-v2 and DLRM-v3 local sources | Deterministic embedding-table gathers preserving fixed fanout, high-fanout quantile gather, and long sequence gather patterns. |
| GNN | MLCommons R-GAT plus gSuite/PubMed local sources | Deterministic graph feature/relation gathers preserving irregular neighbor access and PubMed-derived/scaled node, edge, and feature dimensions. |
| CORAL2 | CORAL2/RAJAPerf local source archives | Deterministic CUDA kernels preserving STREAM, LTimes/Kripke-like contraction, ENERGY, PLANCKIAN, and REDUCE3 memory motifs. |

DLRM rows:

| Benchmark | Arguments | Prepared behavior |
| --- | --- | --- |
| `dlrm_v2_embeddingbag_fixed` | `--mode dlrm_embedding_fixed --bags 32768 --lookups 32 --dim 64 --entries 262144 --iters 1` | DLRM-v2-style fixed multi-hot embedding-bag gather/reduce. |
| `dlrm_v2_embeddingbag_quantile` | `--mode dlrm_embedding_quantile --bags 16384 --lookups 100 --dim 64 --entries 262144 --iters 1` | High-fanout embedding-bag gather based on DLRM-v2 quantile-style fanout. |
| `dlrm_v3_sequence_gather` | `--mode dlrm_v3_sequence_gather --sequences 32768 --seq-len 64 --dim 32 --entries 524288 --iters 1` | DLRM-v3-style long sequence embedding gather. |

GNN rows:

| Benchmark | Arguments | Prepared behavior |
| --- | --- | --- |
| `mlperf_rgat_feature_fetch` | `--mode gnn_feature_fetch --edges 262144 --nodes 65536 --dim 64 --iters 1` | MLCommons R-GAT/IGBH-style irregular neighbor feature fetch. |
| `mlperf_rgat_relation_agg` | `--mode gnn_relation_agg --edges 1048576 --nodes 262144 --dim 32 --relations 4 --iters 1` | R-GAT-style relation-aware gather with destination-indexed edge outputs; scaled to a roughly 32 MiB feature working set after H100 1/5 cache-sensitivity ablation. |
| `gsuite_gcn_mp_pubmed` | `--mode gsuite_gcn_mp_pubmed --edges 44338 --nodes 19717 --dim 500 --iters 1` | gSuite PubMed GCN message-passing feature fetch. |
| `gsuite_sage_mp_pubmed` | `--mode gsuite_sage_mp_pubmed --edges 524288 --nodes 262144 --dim 128 --relations 4 --iters 1` | gSuite SAGE-style relation gather with destination-indexed edge outputs; scaled to a roughly 128 MiB feature working set after H100 1/5 cache-sensitivity ablation. |
| `gsuite_gin_wl_pubmed` | `--mode gsuite_gin_wl_pubmed --edges 44338 --nodes 19717 --dim 256 --iters 1` | gSuite PubMed GIN/WL-style gathered feature transform. |

CORAL2 rows:

| Benchmark | Arguments | Prepared behavior |
| --- | --- | --- |
| `coral2_rajaperf_stream_triad` | `--mode coral_stream_triad --elements 4194304 --iters 3` | RAJAPerf STREAM TRIAD-style streaming bandwidth kernel. |
| `coral2_rajaperf_ltimes` | `--mode coral_ltimes --zones 8192 --groups 32 --dirs 32 --moments 8 --iters 1` | CORAL2 transport/Kripke-like LTimes tensor contraction. |
| `coral2_rajaperf_energy` | `--mode coral_energy --elements 4194304 --iters 2` | RAJAPerf ENERGY-style hydro array update. |
| `coral2_rajaperf_planckian` | `--mode coral_planckian --elements 1048576 --groups 16 --iters 1` | RAJAPerf PLANCKIAN-style grouped physics table computation. |
| `coral2_rajaperf_reduce3` | `--mode coral_reduce3 --elements 4194304 --iters 2` | RAJAPerf REDUCE3_INT-style multi-array reduction. |

Validation note: the promoted proxy rows passed H100 1/5-stack Samsung HBM3SID
q64 bounded validation with `status_counts=MAX_CYCLE_OK:13` in
`simulator/accelsim_ramulator/results/h100_1stack_official_memory_smoke_q64_20260526_v6/summary.csv`.
Because that validation used `--max-cycle 50000`, it verifies backend wiring
and early memory behavior rather than full application completion.

Trace rows launch:

```bash
gpu_benchmark/scripts/run_accelsim_trace_replay.py --benchmark <name>
```

The runner still creates the per-run `gpgpusim.config`, Ramulator2 YAML, and
SGRAM/Ramulator environment. The helper then replays the selected
`kernelslist.g` with `accel-sim.out -trace`.

By default trace replay reads `trace_manifest.tsv`, which now points to the
larger trace paths used by the active set:

| Trace group | Trace input size |
| --- | --- |
| `nvcomp_ans` | 4 MiB compression trace, generated from `nvcomp_codec_bench` with 64 KiB chunks. |
| `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_sort` | 64 MiB profiler-scoped cuDF micro traces. |
| `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` | 128 MiB profiler-scoped synthetic TPC-H-shaped traces. |
| `tango_alexnet` | Existing SM86 larger Tango AlexNet trace. |

DLRM/GNN/CORAL2 proxy rows are native in `manifest.tsv`. If those rows should
be moved as trace files, generate the optional trace bundle with:

```bash
gpu_benchmark/scripts/run_official_memory_accelsim_trace.py --force
```

Then package/unpack `--group trace-official-memory` and run
`manifest.official_memory_trace.tsv`, whose commands read
`trace_manifest.official_memory.tsv`.

Regenerate the larger trace manifest with:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py
```

Refresh the default trace manifest only after replay validation passes:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py \
  --activate-main-manifest
```

## Scaled Inputs

Some rows are intentionally larger than their default sample settings so the
H100 1/5-stack config still produces meaningful DRAM pressure.

| Group | Active scaling |
| --- | --- |
| GraphBIG | Main rows use `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k`; BFS/SSSP use root `90628`. |
| Lonestar | Main rows use generated `rmat16.sym.gr`; large validation rows use `rmat20.sym.gr`. |
| Rodinia | The active set keeps `rodinia_backprop`; other scaled Rodinia rows are in `manifest.optional.tsv` after falling below the 100k-request cutoff or becoming long-tail. |
| Dragon-Li | Dragon-Li rows are preserved in `manifest.optional.tsv`; they were functional but too small/cache-fit on H100 1/5. |
| cuDF/nvCOMP | Active trace rows use the larger trace paths in `trace_manifest.tsv`; smaller codec/query rows remain in `manifest.optional.tsv`. |
| DLRM/GNN/CORAL2 proxy | Promoted rows use deterministic synthetic inputs with official-source-derived fanout, graph dimensions, and CORAL2/RAJAPerf access motifs. |

Rows with fixed local graph/input files or prepared traces should be scaled by
staging a larger dataset or regenerating traces first. Do not only change a
manifest row unless the binary actually accepts that runtime parameter.

## Excluded And Optional Rows

The active set excludes:

```text
polybench_fdtd2d
polybench_gramschmidt
polybench_covariance
polybench_2mm
```

These rows are useful PolyBench coverage, but the packaged binaries do not
expose a simple runtime input-size knob and the current binaries became
multi-day unbounded runs under H100 SXM Samsung HBM3 1/5-stack validation. Keep
them in inventory manifests for bounded smoke tests or source-rebuild
experiments, then promote them back only after smaller rebuilt inputs are
validated with AccelSim + Ramulator2.

`rodinia_particlefilter_float` is also excluded from the active set because it
crashed during previous validation.

`manifest.optional.tsv` also keeps application rows that were functional but
fell below 100k DRAM requests on H100 1/5, plus `proxy_lulesh` and
`rodinia_streamcluster`, which remained long-tail/incomplete under the current
binary/input mix. See `REPRESENTATIVENESS.md` for the row-by-row reason.

The `micro_*` rows are not failure exclusions. They live in
`../system/manifest.tsv` and are loaded with the
`accelsim_ramulator_system_check` preset so bandwidth, latency, atomic, cache,
and bridge-counter probes do not distort application benchmark summaries.

## Add A Local Benchmark

Put new repo-local benchmarks under:

```text
local/<benchmark-name>/
  bin/
  input/
  README.md
```

Add one row to `manifest.tsv`:

```text
name    suite    expected_class    workdir    command    main_reason
```

Use `gpu_benchmark/...` paths for input files so the runner can resolve them
from per-benchmark result directories.

Smoke the row first:

```bash
cd ../../../simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks <benchmark-name> \
  --latencies 0 \
  --queue-limits 64 \
  --max-cycle 50000 \
  --timeout 600 \
  --out-dir results/<benchmark-name>_smoke
```

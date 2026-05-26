# Main Benchmark Set

`manifest.tsv` is the active AccelSim + Ramulator2 benchmark list. The
simulator runner preset `accelsim_ramulator_main` loads this file directly.

The current main set has 74 application/trace rows after moving synthetic
microbenchmarks to the system-check set and removing long-tail PolyBench rows
that cannot be shortened without rebuilding their sources.

## How To Run

List the active rows:

```bash
cd ../../../simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

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
| `../system/manifest.tsv` | Synthetic microbenchmarks for simulator and memory-system sanity checks. |
| `trace_manifest.tsv` | Default trace replay paths for `nvcomp_*`, `tango_*`, and `cudf_*` rows. |
| `trace_manifest.memory_intensive.tsv` | Larger generated trace paths for H100 memory-pressure validation. |
| `manifest.graph_medium_large.tsv` | Extra GraphBIG/Lonestar medium and large validation rows. |
| `GRAPH_INPUTS.md` | GraphBIG/Lonestar input sizes, arguments, and generation notes. |
| `REPRESENTATIVENESS.md` | Current memory-intensity and representative-set classification. |
| `../prepare/OFFICIAL_MEMORY_BENCHMARKS.md` | Source provenance and validation notes for the promoted DLRM/GNN/CORAL2 proxy rows. |

## Native And Trace Rows

Native rows launch CUDA binaries through the AccelSim runtime interception path.
These include PolyBench, GraphBIG, ISPASS, Rodinia, Parboil, Lonestar,
Pannotia, Dragon-Li, proxy apps, and the promoted DLRM/GNN/CORAL2
`official_memory_proxy` rows.

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

Trace rows launch:

```bash
gpu_benchmark/scripts/run_accelsim_trace_replay.py --benchmark <name>
```

The runner still creates the per-run `gpgpusim.config`, Ramulator2 YAML, and
SGRAM/Ramulator environment. The helper then replays the selected
`kernelslist.g` with `accel-sim.out -trace`.

By default trace replay reads `trace_manifest.tsv`. To validate the larger
memory-intensive trace set, pass:

```bash
SGRAM_TRACE_MANIFEST=gpu_benchmark/benchmarks/main/trace_manifest.memory_intensive.tsv
```

The memory-intensive trace manifest currently points to:

| Trace group | Trace input size |
| --- | --- |
| `nvcomp_*` | 4 MiB compression traces, generated from `nvcomp_codec_bench` with 64 KiB chunks. |
| `cudf_filter`, `cudf_project`, `cudf_groupby`, `cudf_join`, `cudf_sort` | 64 MiB profiler-scoped cuDF micro traces. |
| `cudf_tpch_q1`, `cudf_tpch_q3`, `cudf_tpch_q6`, `cudf_tpch_q10` | 128 MiB profiler-scoped synthetic TPC-H-shaped traces. |
| `tango_*` | Existing SM86 Tango traces; not yet regenerated into a larger memory-intensive set. |

Regenerate the larger trace manifest with:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py
```

Activate it as the default trace manifest only after replay validation passes:

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
| Rodinia | Several rows use explicit larger CLI sizes, for example SRAD v2 `512x512`, Gaussian `-s 256`, LavaMD `-boxes1d 10`, NW `512 10`, and Pathfinder `1000 1000 20`. |
| Dragon-Li | `dragon_join` uses `-l 65536 -r 65536 -m 65536`; `dragon_amr` keeps `-s 4096 -r 2`. |
| cuDF/nvCOMP | Larger inputs are handled by regenerating trace files rather than changing the replay manifest row itself. |
| DLRM/GNN/CORAL2 proxy | Promoted rows use deterministic synthetic inputs with official-source-derived fanout, graph dimensions, and CORAL2/RAJAPerf access motifs. |

Rows with fixed local graph/input files or prepared traces should be scaled by
staging a larger dataset or regenerating traces first. Do not only change a
manifest row unless the binary actually accepts that runtime parameter.

## Excluded Long-Tail Rows

The active main set excludes:

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

`rodinia_particlefilter_float` is also excluded from the main set because it
crashed during previous validation. `rodinia_particlefilter_naive` remains as
the particle-filter representative.

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

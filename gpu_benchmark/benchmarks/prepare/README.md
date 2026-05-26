# Prepared Benchmark Candidates

This directory stages standalone CUDA benchmark candidates before promoting
them into `gpu_benchmark/benchmarks/main/manifest.tsv`. Some validated
prepared binaries, including `official_memory_proxy`, are also used directly
by promoted main rows.

The goals are:

- keep candidate code away from the stable main benchmark list;
- avoid external CUDA libraries so AccelSim can inspect normal CUDA kernels;
- cover non-AI GPU application areas that are currently thin in the main set.

## Candidates

| Name | Area | Pattern |
| --- | --- | --- |
| `fft_stockham` | FFT / signal processing | batched 1D FFT stages with global-memory butterfly traffic |
| `finance_monte_carlo` | financial Monte Carlo | per-thread RNG, path simulation, block reductions |
| `official_memory_proxy` | DLRM / GNN / CORAL2 | official-derived memory access proxies for embedding gather, graph message passing, and CORAL2 motifs |
| `sha256_batch` | compression / hashing / crypto | integer-heavy SHA-256 message hashing |
| `smith_waterman` | bioinformatics | batched dynamic-programming sequence alignment |

Optional nvCOMP-backed compression candidates live under `nvcomp/`. They are
not built by default because nvCOMP is not bundled with this workspace.

Optional RAPIDS cuDF candidates live under `cudf/`. They are Python/RAPIDS
benchmarks and are not built by default because cuDF is not bundled with this
workspace.

Optional Tango DNN candidates live under `tango/`. They are pure-CUDA neural
network inference benchmarks fetched from the upstream Tango repository and are
not built by default because the upstream model data is external.

Official-derived DLRM, GNN, and CORAL2 rows are listed in
`official_memory_manifest.tsv` and promoted into `main/manifest.tsv`. They use
the standalone `official_memory_proxy` CUDA binary, deterministic synthetic
inputs, and official-source-derived dimensions/access motifs. They are intended
for memory system studies, not MLPerf or CORAL2 compliance reporting.

## Build

```bash
cd gpu_benchmark/benchmarks/prepare
make
```

The binaries are written to `bin/`, which is intentionally ignored by git.

## Smoke Run

```bash
bin/fft_stockham --points 1024 --batches 256 --iters 1
bin/finance_monte_carlo --paths 262144 --steps 32
bin/official_memory_proxy --mode dlrm_embedding_fixed --bags 4096 --lookups 16 --dim 32 --entries 32768 --iters 1
bin/official_memory_proxy --mode gnn_feature_fetch --edges 32768 --nodes 8192 --dim 64 --iters 1
bin/official_memory_proxy --mode coral_stream_triad --elements 1048576 --iters 1
bin/sha256_batch --messages 262144 --iters 1
bin/smith_waterman --pairs 8192 --len 96
```

`manifest.tsv` and `official_memory_manifest.tsv` use the same schema as the
main manifest. Promote a row only after its binary builds, references local
inputs only, and survives a bounded AccelSim + Ramulator2 run.

For nvCOMP algorithms, see `nvcomp/manifest.tsv` and build with:

```bash
make nvcomp NVCOMP_ROOT=/path/to/nvcomp
```

For cuDF operations, run from a RAPIDS environment with `cudf` installed:

```bash
python gpu_benchmark/benchmarks/prepare/cudf/cudf_microbench.py \
  --op groupby --target-bytes 32MiB --iters 1 --warmup 1
```

For Tango DNN models, fetch a sparse upstream checkout and build the prepared
small-model subset:

```bash
make tango
make tango-smoke
```

For the DLRM/GNN/CORAL2 proxy rows:

```bash
make official_memory_proxy CUDA_ARCH=80
python3 simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --config-variant h100_1stack \
  --ramulator-config simulator/accelsim_ramulator/configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --manifest gpu_benchmark/benchmarks/prepare/official_memory_manifest.tsv \
  --latencies 0 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --gpgpusim-host-timing on \
  --max-cycle 50000 \
  --timeout 900 \
  --jobs 8
```

The proxy is built with shared CUDA runtime linkage so AccelSim can intercept
kernel launches. Its data arrays are initialized on the host and copied to the
device so the first simulated launch is the benchmark kernel, not an input-fill
kernel.

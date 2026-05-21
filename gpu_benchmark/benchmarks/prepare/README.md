# Prepared Benchmark Candidates

This directory stages standalone CUDA benchmark candidates before promoting
them into `gpu_benchmark/benchmarks/main/manifest.tsv`.

The goals are:

- keep candidate code away from the stable main benchmark list;
- avoid external CUDA libraries so AccelSim can inspect normal CUDA kernels;
- cover non-AI GPU application areas that are currently thin in the main set.

## Candidates

| Name | Area | Pattern |
| --- | --- | --- |
| `fft_stockham` | FFT / signal processing | batched 1D FFT stages with global-memory butterfly traffic |
| `finance_monte_carlo` | financial Monte Carlo | per-thread RNG, path simulation, block reductions |
| `sha256_batch` | compression / hashing / crypto | integer-heavy SHA-256 message hashing |
| `smith_waterman` | bioinformatics | batched dynamic-programming sequence alignment |

Optional nvCOMP-backed compression candidates live under `nvcomp/`. They are
not built by default because nvCOMP is not bundled with this workspace.

Optional RAPIDS cuDF candidates live under `cudf/`. They are Python/RAPIDS
benchmarks and are not built by default because cuDF is not bundled with this
workspace.

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
bin/sha256_batch --messages 262144 --iters 1
bin/smith_waterman --pairs 8192 --len 96
```

`manifest.tsv` uses the same schema as the main manifest. Promote a row only
after its binary builds, references local inputs only, and survives a bounded
AccelSim + Ramulator2 run.

For nvCOMP algorithms, see `nvcomp/manifest.tsv` and build with:

```bash
make nvcomp NVCOMP_ROOT=/path/to/nvcomp
```

For cuDF operations, run from a RAPIDS environment with `cudf` installed:

```bash
python gpu_benchmark/benchmarks/prepare/cudf/cudf_microbench.py \
  --op groupby --target-bytes 32MiB --iters 1 --warmup 1
```

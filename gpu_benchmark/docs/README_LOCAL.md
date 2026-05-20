# Local GPU Benchmark Setup

This note describes the `gpu_benchmark/` root. Run the commands below from that
directory unless a command says otherwise.

The benchmark tree is organized around two benchmark sources:

- `suites/graphBIG`: the existing GraphBIG GPU benchmarks.
- `gpu-app-collection`: the source tree for the non-GraphBIG CUDA workloads.

Old duplicate archives and extracted standalone suites were removed. Large
logs/traces/data are kept under the `traces` symlink, which points at
`/media/1/gju06051/Comp/Sectored-Access-DRAM-traces/gpu_benchmark/traces`.

## Build Environment

The local CUDA compiler is 12.3 and the GPUs are RTX 3090 (`sm_86`). Source:

```bash
source ./scripts/setup_gpu_app_collection_env.sh
```

The wrapper sets CUDA 12.3, uses `/usr/bin/g++-11` as nvcc's host compiler, and
creates the empty `gpu-app-collection/4.2` directory that prevents the old CUDA
4.2 SDK auto-download path from firing.

## Build

Build a subset:

```bash
./scripts/build_gpu_app_collection.sh polybench ispass-2009
```

Build the default local set:

```bash
./scripts/build_gpu_app_collection.sh
```

List built binaries:

```bash
./scripts/list_gpu_app_binaries.sh
```

## Run

Run a checked smoke set from `gpu-app-collection`:

```bash
./scripts/run_gpu_app_collection_smoke.sh
```

If binaries are already built and you only want to run:

```bash
BUILD=0 ./scripts/run_gpu_app_collection_smoke.sh
```

Run matching binaries directly with no arguments:

```bash
./scripts/run_gpu_app_collection_binaries.sh '^polybench-'
```

Run PolyBench-only helpers:

```bash
./scripts/run_polybench_cuda_smoke.sh
./scripts/run_polybench_cuda_all.sh
```

Logs are written under `traces/run_logs`.

## Data

The `gpu-app-collection/data_dirs` path is a symlink to:

```text
/media/1/gju06051/Comp/Sectored-Access-DRAM-traces/gpu-app-collection/data_dirs
```

Fetch the official gpu-app-collection dataset tarball with:

```bash
./scripts/fetch_gpu_app_collection_data.sh
```

The tarball is 2.4GB, so the wrapper stores/resumes it on `/media/1` instead of
the home disk. The upstream `gpu-app-collection/get_data.sh` was also patched
locally so `make data -C gpu-app-collection/src` follows the same `/media/1`
symlink and does not skip an empty `data_dirs` directory.

Rodinia 3.1 also has a few bundled local generators. Generate the small NN and
LUD inputs with:

```bash
./scripts/generate_rodinia_3_1_inputs.sh
```

## NVBit Memory Traces

NVBit 1.7.7.3 is unpacked under `../tools/nvbit_release_x86_64`.

Build/check command used locally:

```bash
make -C ../tools/nvbit_release_x86_64/tools/mem_trace ARCH=sm_86 CXX=/usr/bin/g++-11
```

Run a benchmark, convert NVBit `mem_trace` output to compact memory trace, and
compute 32B/16B/8B row-local packing opportunities:

```bash
./scripts/run_nvbit_row_opportunity.sh graphbig_bfs_small traces -- \
  ./suites/graphBIG/gpu_bench/gpu_BFS/bfs_topo_frontier \
  --dataset ./suites/graphBIG/dataset/small --root 31
```

The compact trace format is:

```text
0xaddress R size_in_bytes
0xaddress W size_in_bytes
```

## Current Status

- PolyBench CUDA builds and runs on RTX 3090.
- ISPASS 2009 builds these binaries: `BFS`, `LIB`, `LPS`, `NN`, `NQU`, `RAY`,
  `STO`.
- ISPASS `WP` still fails under CUDA 12.3 because its old Fortran/CUDA path
  calls nvcc without the patched host compiler path and then fails later in the
  generated Fortran/CUDA objects.
- Input-dependent workloads such as ISPASS `BFS`/`NN` need the official data
  package before full runs.

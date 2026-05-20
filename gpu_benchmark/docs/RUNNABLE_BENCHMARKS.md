# Runnable Benchmark Summary

Checked on RTX 3090 with CUDA 12.3.

Important local change: `scripts/setup_gpu_app_collection_env.sh` now exports
`NVCC_PREPEND_FLAGS="-ccbin /usr/bin/g++-11"`. This matters because many old
benchmark Makefiles call `nvcc` directly and otherwise pick unsupported GCC 13.

## Sweep Artifacts

- Build sweep:
  `traces/run_logs/gpu_app_collection_target_sweep/summary.tsv`
- No-arg run sweep:
  `traces/run_logs/gpu_app_collection_all_noarg/summary.tsv`
- Usage-arg run sweep:
  `traces/run_logs/gpu_app_collection_usage_args/summary.tsv`
- Manual-arg logs:
  `traces/run_logs/gpu_app_collection_manual_args/`
- GraphBIG/app summary:
  `traces/run_logs/available_benchmarks/summary.tsv`

Note: Rodinia 2.0-ft was removed after the first broad sweep. Older logs may
still contain historical 2.0-ft entries, but the source tree and binary
directory now only keep Rodinia 3.1.

## Build Coverage

The `gpu-app-collection` binary directory now has 249 executables.

New binaries produced by the expanded sweep before current pruning:

- `GPU_Microbenchmark`: 63 binaries
- `microbench`: 1 binary
- `custom_apps`: 1 binary
- `proxy-apps`: 2 binaries (`XSBench`, `lulesh`)
- `pannotia`: 10 binaries
- `parboil`: 8 copied binaries
- `rodinia-3.1`: 21 binaries
- `lonestargpu-2.0`: 11 binaries
- `accelwattch_ubench`: 96 binaries

Historical note: `UVMSmart_test` produced binaries and some of them ran on the
real GPU, but UVM workloads are excluded from the current Sectored-Access-DRAM
active benchmark set and were moved to `gpu_benchmark/not_use`.

No usable native CUDA binaries from:

- `cuda_samples`: checked-out directory is only a stub and has no `CMakeLists.txt`.
- `cutlass_mini`: submodule/source checkout is incomplete.
- Parboil `bfs`, `sad`, and `spmv`: CUDA 12 build fails on the removed legacy
  texture API.

## Runnable App Benchmarks

### GraphBIG

All below run with `dataset/small`:

- `bfs_topo_frontier --dataset dataset/small --root 31`
- `betweenness --dataset dataset/small`
- `connected_comp --dataset dataset/small`
- `degree_centr --dataset dataset/small`
- `gc_topo_thread_centric --dataset dataset/small`
- `sssp_data_thread_centric --dataset dataset/small --root 31`
- `sssp_data_warp_centric --dataset dataset/small --root 31`
- `sssp_topo_thread_centric --dataset dataset/small --root 31`
- `sssp_topo_warp_centric --dataset dataset/small --root 31`
- `triangle_count --dataset dataset/small`
- `kcore --dataset dataset/small`

GraphColoring currently only produces `gc_topo_thread_centric`. The missing
extra variants need a CUDA 12 pass; the warp-centric sources still use
deprecated `__all()`.

### PolyBench

Runnable within the 60s check:

- `polybench-2DConvolution`
- `polybench-3DConvolution`
- `polybench-3mm`
- `polybench-atax`
- `polybench-bicg`
- `polybench-correlation`
- `polybench-covariance`
- `polybench-fdtd2d`
- `polybench-gemm`
- `polybench-gesummv`
- `polybench-mvt`
- `polybench-syr2k`
- `polybench-syrk`

Also runnable with a longer timeout:

- `polybench-2mm` passed with a 300s timeout; observed 112 seconds.
- `polybench-gramschmidt` passed with a 300s timeout; observed 95 seconds.

Notes:

- `polybench-fdtd2d` exits normally but reports 2 CPU/GPU mismatches beyond its
  printed threshold.

### ISPASS 2009

Runnable now:

- `ispass-2009-BFS` with `graph65536.txt`
- `ispass-2009-LIB`
- `ispass-2009-LPS`
- `ispass-2009-NN` from its data directory with `1000`
- `ispass-2009-NQU`
- `ispass-2009-RAY 256 256`
- `ispass-2009-STO`

### Pannotia

Runnable with data:

- `bc data/1k_128k.gr`
- `color_max data/G3_circuit.graph 1`
- `color_maxmin data/G3_circuit.graph 1`
- `fw data/256_16384.gr`
- `fw_block data/256_16384.gr`
- `mis data/G3_circuit.graph 1`
- `pagerank data/coAuthorsDBLP.graph 1`
- `pagerank_spmv data/coAuthorsDBLP.graph 1`
- `sssp data/USA-road-d.NY.gr 0`
- `sssp_ell data/USA-road-d.NY.gr 0`

### Parboil

Runnable:

- `parboil-cutcp`
- `parboil-histo`
- `parboil-mri-gridding`
- `parboil-mri-q`
- `parboil-stencil`
- `parboil-tpacf`
- `parboil-sgemm` with the small SGEMM dataset
- `parboil-lbm` when invoked directly with `-i` and `-o`

Still problematic:

- `bfs`, `sad`, `spmv`: build failure from CUDA 12 legacy texture API removal.
- `lbm` through the Parboil driver without `-C`: benchmark runs, but the
  Python 2 output checker fails under Python 3.
- `sgemm` `cuda_k1` variant: times out at 120 seconds; the main `cuda` variant
  passes.

### Rodinia

Rodinia 2.0-ft was deleted; use Rodinia 3.1 only.

Runnable with no external input data:

- `backprop-rodinia-3.1 65536`
- `gaussian-rodinia-3.1 -s 64 -q`
- `lavaMD-rodinia-3.1`
- `lud-rodinia-3.1 -s 64`
- `myocyte-rodinia-3.1`
- `nn-rodinia-3.1 filelist_4 -r 5 -lat 30 -lng 90` from the Rodinia
  `cuda/nn` directory after `./scripts/generate_rodinia_3_1_inputs.sh`
- `nw-rodinia-3.1 64 10`
- `particlefilter_float-rodinia-3.1`
- `particlefilter_naive-rodinia-3.1`
- `pathfinder-rodinia-3.1 100 100 20`
- `srad_v2-rodinia-3.1 128 128 0 31 0 31 0.5 2`
- `streamcluster-rodinia-3.1 10 20 256 65536 65536 1000 none output.txt 1`

Needs input data or more cleanup:

- Rodinia BFS, heartwall, hotspot, hotspot3D, huffman, dwt2d, b+tree,
  CFD, kmeans, leukocyte, mummergpu, and SRAD v1.
- See `RODINIA_3_1_INPUTS.md` for the per-workload input/generator audit.

### Proxy Apps

- `XSBench`: runs to completion with default args, but needs more than the 5s
  no-arg smoke timeout.
- `lulesh`: runs to completion with default args, but needs more than the 5s
  no-arg smoke timeout.

### Microbenchmarks

Runnable no-arg examples:

- `mem_bw`
- `mem_lat`
- `l1_bw_32f`
- `l2_bw_32f`
- `l1_lat`
- `l2_lat`
- `MaxFlops_float`
- `MaxFlops_double`
- `MaxFlops_half`
- `MaxIops_int32`
- `tensor_bw_half`
- `tensor_lat_half`
- `list_devices`

Runnable with `1` or `1 1` arg:

- Most `BE_*`, `BRANCHING*`, `REG_FILE`, `TENSOR`, `add_mem_*`, `mul_mem_*`,
  and `const_mul` binaries.

Still failing even with small args:

- `ACT_CORE1`, `ACT_CORE2`, `BE_L1D_HIT`, `BE_L2D_HIT`,
  `INT_FP_*_STATIC`, `INT_STATIC`, `LIGHT_SM`.

### LonestarGPU

Runnable data-backed examples:

- `lonestar-bfs`, `lonestar-bfs-atomic`, `lonestar-bfs-wla`,
  `lonestar-bfs-wlw` on `rmat12.sym.gr`
- `lonestar-sssp`, `lonestar-sssp-wln` on road/RMAT inputs
- `lonestar-mst`, `lonestar-nsp`
- `lonestar-dmr 25k 12`
- `lonestar-pta pine_nodes.txt pine_constraints_after_hcd.txt pine_hcd.txt
  pine_correct_soln_001.txt 1 0`

Still problematic:

- `lonestar-bh`: `100 1 0` times out at 120 seconds.
- `lonestar-pta` with verification enabled: small input solves but reference
  verification fails; larger verified runs can hit illegal memory access.

## Not Treated As Native CUDA Binary Benchmarks Yet

These framework or hard-to-wire directories were moved under
`gpu_benchmark/not_use` rather than kept in the active benchmark tree:

- `huggingface`
- `vllm`
- `mlperf`
- `mlperf_inference`
- `pytorch_examples`
- `cudnn`
- `DeepBench`
- `NVIDIA_CUDA-11.0_Samples`
- `cutlass-bench`
- `cuda-samples`
- `dlrm`

`tango` is kept active under `gpu_benchmark/suites/tango`: its GPU workloads
are standalone CUDA/gpgpu-sim style neural-network benchmarks.

Most of these need Python/framework/model/dataset setup or a separate CUDA
sample/CUTLASS build pass.

## Excluded From Current Study

### UVMSmart

`UVMSmart_test` is not part of the active runnable set for this study. Some UVM
benchmarks did run on the real GPU during the early broad sweep, but they use
managed-memory behavior and are not a good match for the DRAM request profiling
we are doing in AccelSim/GPGPU-Sim. The source tree is now under
`gpu_benchmark/not_use/gpu-app-collection/src/cuda/UVMSmart_test`.

Historical real-GPU runnable examples were:

- `uvm_2dconv`
- `uvm_add_vectors`
- `uvm_atax`
- `uvm_fdtd`
- `uvm_ra`
- `uvm_sssp`
- `uvm_stream_triad`
- `uvm_backprop 65536`
- `uvm_needle 64 10`
- `uvm_pathfinder 100 100 20`
- `uvm_srad 128 128 0 31 0 31 0.5 2`

## Commands

Rebuild/sweep broad native CUDA targets:

```bash
TARGET_TIMEOUT=300s JOBS=4 ./scripts/sweep_gpu_app_collection_targets.sh
```

Run all built binaries with no args:

```bash
BENCH_TIMEOUT=5s ./scripts/run_gpu_app_all_binaries_noarg.sh
```

Retry usage-style binaries with small args:

```bash
BENCH_TIMEOUT=10s ./scripts/run_gpu_app_usage_arg_smoke.sh
```

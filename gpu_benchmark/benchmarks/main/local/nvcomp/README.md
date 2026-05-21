# nvCOMP Main Wrappers

This directory contains thin wrappers for promoted nvCOMP compression
benchmarks. The actual CUDA benchmark binary is staged in
`gpu_benchmark/benchmarks/prepare/bin/nvcomp_codec_bench`.

`run_nvcomp_codec.sh` keeps the main manifest stable by resolving the repository
root and adding the nvCOMP runtime library path before executing the staged
binary. Set `NVCOMP_ROOT` explicitly for a manual nvCOMP install. If it is not
set, the wrapper tries the `nvidia-libnvcomp-cu12` Python wheel layout.

The promoted rows were validated with the NVBit trace-driven
AccelSim + Ramulator2 flow. Use that trace path for simulator studies of these
prebuilt nvCOMP kernels.

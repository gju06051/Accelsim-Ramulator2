# nvCOMP Accel-Sim Trace Notes

This note records the local smoke path used to run nvCOMP through the Accel-Sim
NVBit SASS tracer and then into trace-driven GPGPU-Sim.

## Local nvCOMP Install

The CUDA 12 nvCOMP wheel installed cleanly:

```bash
python3 -m pip install --user nvidia-libnvcomp-cu12
```

On this machine the install prefix is:

```text
/home/gju06051/.local/lib/python3.11/site-packages/nvidia/libnvcomp
```

Build and smoke-test the prepared nvCOMP wrapper:

```bash
export NVCOMP_ROOT=/home/gju06051/.local/lib/python3.11/site-packages/nvidia/libnvcomp
export LD_LIBRARY_PATH="${NVCOMP_ROOT}/lib64:${LD_LIBRARY_PATH:-}"
make -C gpu_benchmark/benchmarks/prepare nvcomp NVCOMP_ROOT="${NVCOMP_ROOT}"
make -C gpu_benchmark/benchmarks/prepare nvcomp-smoke NVCOMP_ROOT="${NVCOMP_ROOT}"
```

All staged codecs passed native verification with `mismatches=0`: LZ4, Snappy,
GDeflate, Deflate, Zstd, Cascaded, Bitcomp, and ANS.

## NVBit Instrumentation

The bundled NVBit analysis tools can instrument prebuilt nvCOMP kernels. For
example, `opcode_hist` and `instr_count` both captured the internal LZ4
compression/decompression kernels. A 1 MiB LZ4 run reported:

```text
lz4CompressBatchKernel:   7,894,424 dynamic instructions
lz4DecompressBatchKernel: 4,141,074 dynamic instructions
Total app instructions:  13,867,843
```

The opcode histogram included modern SASS operations such as `MATCH.ANY`,
`REDUX.OR`, `REDUX.MAX.S32`, `RED.E.MAX.S32.STRONG.GPU`, `VOTE.ANY`, and
`SHFL.*`.

## Accel-Sim SASS Trace Flow

The simple bundled NVBit tools are not enough for GPGPU-Sim trace-driven mode.
They produce analysis logs, not Accel-Sim trace input. Use Accel-Sim's
`util/tracer_nvbit/tracer_tool` instead.

For CUDA 12.3 plus NVBit 1.7.7.3, the Accel-Sim `dev` branch tracer worked
after building it against the local NVBit release. The older Accel-Sim
`release` tracer needed source changes for the newer NVBit API and did not work
cleanly here.

Important local detail: use `CUDA_INJECTION64_PATH` for the Accel-Sim tracer.
With this tracer, `LD_PRELOAD` loaded the tool but did not attach kernel launch
callbacks reliably in this environment.

Minimal trace generation for the nvCOMP LZ4 compression kernel:

```bash
TRACE_PARENT=/tmp/nvcomp_accelsim_dev_lz4_tiny_kernel3
rm -rf "${TRACE_PARENT}" && mkdir -p "${TRACE_PARENT}"

export NVCOMP_ROOT=/home/gju06051/.local/lib/python3.11/site-packages/nvidia/libnvcomp
export LD_LIBRARY_PATH="${NVCOMP_ROOT}/lib64:${LD_LIBRARY_PATH:-}"
unset LD_PRELOAD
export CUDA_INJECTION64_PATH=/tmp/accel-sim-framework-dev/util/tracer_nvbit/tracer_tool/tracer_tool.so
export ACK_CTX_INIT_LIMITATION=1
export CUDA_VISIBLE_DEVICES=0
export USER_DEFINED_FOLDERS=1
export TRACES_FOLDER="${TRACE_PARENT}"
export DYNAMIC_KERNEL_RANGE=3
export TOOL_COMPRESS=1
export TRACE_FILE_COMPRESS=1

./gpu_benchmark/benchmarks/prepare/bin/nvcomp_codec_bench \
  --codec lz4 --bytes 4096 --chunk-size 4096 --iters 1

KLIST="$(find "${TRACE_PARENT}/traces" -maxdepth 1 -name 'kernelslist_ctx_*' | head -1)"
/tmp/accel-sim-framework-dev/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing "${KLIST}"
```

`DYNAMIC_KERNEL_RANGE=3` selects the LZ4 compression kernel in this wrapper's
launch order:

1. `fill_compressible_bytes`
2. `setup_comp_llif_buffers`
3. `lz4CompressBatchKernel`

The post-processed trace is then:

```text
/tmp/nvcomp_accelsim_dev_lz4_tiny_kernel3/traces/kernelslist.g
```

## Trace-Driven Simulation Smoke

The tiny LZ4 compression trace completed with Accel-Sim dev's SM86 config:

```bash
cd /tmp/accel-sim-framework-dev/gpu-simulator
source setup_environment.sh release
./bin/release/accel-sim.out \
  -trace /tmp/nvcomp_accelsim_dev_lz4_tiny_kernel3/traces/kernelslist.g \
  -config ./gpgpu-sim/configs/tested-cfgs/SM86_RTX3070/gpgpusim.config \
  -config ./configs/tested-cfgs/SM86_RTX3070/trace.config
```

Observed completion stats:

```text
kernel_name = _ZN6nvcomp8lowlevel22lz4CompressBatchKernelIhLb0EEEvPKPKhPKmPKPhPmPtjj
gpu_tot_sim_cycle = 165357
gpu_tot_sim_insn = 733373
L2_total_cache_accesses = 1477
L2_total_cache_misses = 418
gpgpu_simulation_time = 10 sec
```

A larger 256 KiB LZ4 compression trace also parsed, launched, and bound four
CTAs, but did not finish within a 180 second smoke timeout. That looks like
simulation cost rather than a trace-format or unsupported-opcode failure.

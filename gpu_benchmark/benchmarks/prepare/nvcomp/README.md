# nvCOMP Compression Candidates

This optional candidate set stages nvCOMP-backed compression/decompression
workloads. It is separate from the default `prepare/manifest.tsv` because this
workspace currently does not ship `nvcomp.hpp` or `libnvcomp`.

## Algorithms

| Name | nvCOMP codec | Coverage role |
| --- | --- | --- |
| `nvcomp_lz4` | LZ4 | General byte-level compression |
| `nvcomp_snappy` | Snappy | Tabular byte-level compression |
| `nvcomp_gdeflate` | GDeflate | GPU-friendly Deflate-family compression |
| `nvcomp_deflate` | Deflate | Compatibility with existing Deflate datasets |
| `nvcomp_zstd` | Zstandard | Modern LZ77/Huffman/ANS compression |
| `nvcomp_cascaded` | Cascaded | Structured/tabular analytical data |
| `nvcomp_bitcomp` | Bitcomp | Scientific-computing oriented compression |
| `nvcomp_ans` | ANS | Entropy coding based on asymmetric numeral systems |

## Build

Install nvCOMP, then point `NVCOMP_ROOT` at its install prefix if it is not
under the CUDA toolkit directory. The Python wheel layout is supported as long
as `NVCOMP_ROOT` points at the `nvidia/libnvcomp` package directory:

```bash
python3 -m pip install --user nvidia-libnvcomp-cu12
NVCOMP_ROOT="$(python3 - <<'PY'
import pathlib
import nvidia.libnvcomp
print(pathlib.Path(nvidia.libnvcomp.__file__).parent)
PY
)"
export LD_LIBRARY_PATH="${NVCOMP_ROOT}/lib64:${LD_LIBRARY_PATH:-}"
cd gpu_benchmark/benchmarks/prepare
make nvcomp NVCOMP_ROOT="${NVCOMP_ROOT}"
```

For a manually installed nvCOMP prefix:

```bash
cd gpu_benchmark/benchmarks/prepare
make nvcomp NVCOMP_ROOT=/path/to/nvcomp
```

If nvCOMP is installed under `/usr/local/cuda-12.3`, the default is enough:

```bash
make nvcomp
```

Run small real-GPU checks:

```bash
make nvcomp-smoke
```

## Large-Input Nsight Compute Sweep

For 1 GiB+ profiling, use:

```bash
gpu_benchmark/scripts/run_nvcomp_ncu_ablation.py \
  --out-dir results/nvcomp_ncu_20260521 \
  --codecs lz4 snappy gdeflate cascaded bitcomp ans \
  --sizes 1GiB 2GiB 4GiB
```

The 2026-05-21 run and interpretation are recorded in
`NSIGHT_COMPUTE_ABLATION_20260521.md`,
`NSIGHT_COMPUTE_COMPRESSION_PHASE_20260521.md`, and
`NSIGHT_COMPUTE_SIZE_SWEEP_2M_TO_512M_20260521.md`.

## Memory-Intensive Accel-Sim Trace Generation

Use the Accel-Sim NVBit tracer helper when promoting nvCOMP rows into the main
trace-driven benchmark set. The default traces the compression kernel
(`DYNAMIC_KERNEL_RANGE=3`) with a 64 MiB input and 64 KiB chunks:

```bash
gpu_benchmark/scripts/run_nvcomp_accelsim_trace.py \
  --codec lz4 \
  --bytes 64MiB \
  --chunk-size 64KiB \
  --out-dir gpu_benchmark/benchmarks/prepare/results/nvcomp_accelsim_traces_64MiB
```

For all staged nvCOMP codecs plus the cuDF memory-intensive trace set, use:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py
```

The current checked `trace_manifest.memory_intensive.tsv` records the validated
4 MiB nvCOMP trace paths. Regenerate that exact nvCOMP size with:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py \
  --nvcomp-size 4MiB
```

That writes
`gpu_benchmark/benchmarks/main/trace_manifest.memory_intensive.tsv`. After the
new traces exist and a bounded AccelSim + Ramulator2 replay passes, either run
the main benchmark with:

```bash
SGRAM_TRACE_MANIFEST=gpu_benchmark/benchmarks/main/trace_manifest.memory_intensive.tsv \
  simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main ...
```

or activate the generated manifest explicitly:

```bash
gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py \
  --activate-main-manifest
```

## NVBit / GPGPU-Sim note

The bundled NVBit tools can instrument the prebuilt nvCOMP kernels during native
execution. `opcode_hist`, `instr_count`, and `mem_trace` are useful for checking
that compression/decompression kernels execute and for quick mix/memory-access
inspection.

Those outputs are not the Accel-Sim/GPGPU-Sim SASS trace-driven input format.
To feed nvCOMP into trace-driven GPGPU-Sim, generate traces with the Accel-Sim
NVBit tracer and run them with an Accel-Sim trace configuration. The GPGPU-Sim
tree in this repository documents compatibility with Accel-Sim traces, but it
does not currently include that full trace generator flow.

See `ACCELSIM_TRACE_NOTES.md` for the local smoke-tested flow. In short, the
Accel-Sim `dev` tracer plus `CUDA_INJECTION64_PATH` generated a valid LZ4
compression trace, and a tiny LZ4 trace completed under trace-driven
GPGPU-Sim/Accel-Sim with the SM86 config.

`manifest.tsv` uses the normal benchmark schema, but these rows should only be
promoted after `bin/nvcomp_codec_bench` builds and the chosen codec survives a
bounded AccelSim + Ramulator2 run. Because nvCOMP is a prebuilt GPU library,
AccelSim compatibility must be checked separately from native CUDA execution.

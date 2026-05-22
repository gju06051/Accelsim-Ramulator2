# Tango DNN Benchmark Candidates

This directory stages selected GPU models from
[Tango](https://gitlab.com/Tango-DNNbench/Tango), a pure-CUDA and OpenCL deep
neural network benchmark suite for architecture studies.

Tango is intentionally kept as an external source tree. The upstream repository
contains model weights and inputs, and a full checkout is large. Use
`fetch_tango.sh` to sparse-checkout only the GPU models used by the prepared
manifest.

## Source

| Field | Value |
| --- | --- |
| Upstream | `https://gitlab.com/Tango-DNNbench/Tango.git` |
| Default commit | `59db69914bf5391b8f39b8b8463482794afe3956` |
| License | GPLv3, from upstream `LICENSE` |
| Default models | `CifarNet`, `GRU`, `LSTM`, `AlexNet` |

The default models were chosen because they build with modern CUDA when using a
supported host compiler and have bounded H100 1/5 trace-replay validation.
`SqueezeNet` and `ResNet` are larger optional Tango models; stage them
separately before considering main promotion.

## Fetch

```bash
cd gpu_benchmark/benchmarks/prepare
make tango-fetch
```

This writes the sparse upstream checkout to:

```text
gpu_benchmark/benchmarks/prepare/tango/upstream/Tango/
```

Override the model list if needed:

```bash
TANGO_MODELS="CifarNet GRU LSTM AlexNet SqueezeNet" make tango-fetch
```

## Build

```bash
cd gpu_benchmark/benchmarks/prepare
make tango
```

The build wrapper compiles inside the fetched Tango model directories. It uses
`CUDAHOSTCXX=/usr/bin/g++-11` by default so CUDA 12.3 does not trip over the
system default GCC version. It also defaults to `CUDA_ARCH=86`, matching the
local RTX 3090 trace-capture GPU used for the H100 1/5 trace-driven validation;
override `CUDA_ARCH` when validating on a different GPU.

## Smoke

```bash
cd gpu_benchmark/benchmarks/prepare
make tango-smoke
```

The smoke target runs:

```bash
tango/run_tango.sh cifarnet 1
tango/run_tango.sh gru
tango/run_tango.sh lstm 1
```

AlexNet is part of the default fetch/build set because it is promoted to the
main manifest, but it is intentionally left out of the quick smoke target due
to its larger data footprint.

## Manifest

`manifest.tsv` uses the normal benchmark schema for Tango rows that can be
fetched, built, and run from the prepare tree. Only rows with bounded AccelSim
+ Ramulator2 validation are eligible for the main manifest.

The default `CifarNet`, `GRU`, `LSTM`, and `AlexNet` rows were validated with
SM86 NVBit traces against the H100 1/5 AccelSim + Ramulator2 configuration on
2026-05-22. The small-model validation output was written under:

```text
/tmp/tango_h100_1stack_validation_sm86_20260522/
```

The large-CNN validation output was written under:

```text
/tmp/tango_large_h100_1stack_validation_sm86_20260522/
```

In that run, AlexNet completed replay in 3:09:17 with a 3.3G trace. SqueezeNet
produced and postprocessed a 3.1G trace, but H100 1/5 replay timed out after
4:00:01 at kernel 18 of 59. ResNet trace capture timed out after 4 hours, so
SqueezeNet and ResNet are not promoted to the main manifest yet.

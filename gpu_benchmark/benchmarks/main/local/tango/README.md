# Tango Main Wrappers

This directory contains thin wrappers for promoted Tango DNN benchmark rows.
The upstream Tango source checkout, model data, and binaries stay staged under
`gpu_benchmark/benchmarks/prepare/tango/`.

Build the promoted models before running the main manifest rows:

```bash
cd gpu_benchmark/benchmarks/prepare
make tango
```

The default prepare build uses `CUDA_ARCH=86`, matching the local RTX 3090
trace ISA used for NVBit trace generation. Override `CUDA_ARCH` if validating
on a different trace-capture GPU.

The promoted CifarNet, GRU, LSTM, and AlexNet rows were validated with SM86
NVBit traces through AccelSim + Ramulator2 using the H100 1/5 HBM3
configuration.

The large CNN candidates were checked on 2026-05-22. AlexNet completed the
H100 1/5 trace replay in 3:09:17. SqueezeNet produced a valid trace but did not
finish replay within the 4-hour validation window, and ResNet did not finish
trace capture within that window, so those two remain prepare-stage candidates.

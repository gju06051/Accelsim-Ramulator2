# Benchmark Suite Layout

The transfer bundle exposes benchmark suites directly under `benchmarks/suites`.
The old Accel-Sim `gpu-app-collection` tree is kept only as a build/compatibility
harness under `benchmarks/common/gpu-app-collection-harness`.

## Suites

| Suite path | Origin |
|---|---|
| `suites/graphBIG` | Standalone GraphBIG checkout |
| `suites/irregular` | Local irregular gather/hash/pointer/SpMV benchmarks |
| `suites/tango` | TANGO GPU workloads |
| `suites/rodinia` | Extracted from `gpu-app-collection/src/cuda/rodinia` |
| `suites/parboil` | Extracted from `gpu-app-collection/src/cuda/parboil` |
| `suites/pannotia` | Extracted from `gpu-app-collection/src/cuda/pannotia` |
| `suites/polybench-gpu-1.0` | Extracted from `gpu-app-collection/src/cuda/polybench-gpu-1.0` |
| `suites/proxy-apps-doe` | Extracted from `gpu-app-collection/src/cuda/proxy-apps-doe` |
| `suites/ispass-2009` | Extracted from `gpu-app-collection/src/cuda/ispass-2009` |
| `suites/lonestargpu-2.0` | Extracted from `gpu-app-collection/src/cuda/lonestargpu-2.0` |
| `suites/shoc` | Extracted from `gpu-app-collection/src/cuda/shoc-master` |
| `suites/accelwattch-ubench` | Extracted from `gpu-app-collection/src/cuda/accelwattch-ubench` |
| `suites/gpuwattch-ubench` | Extracted from `gpu-app-collection/src/cuda/gpuwattch-ubench` |
| `suites/gpu-microbenchmark` | Extracted from `gpu-app-collection/src/cuda/GPU_Microbenchmark` |
| `suites/cub` | Extracted from `gpu-app-collection/src/cuda/cub` |
| `suites/dragon-li` | Extracted from `gpu-app-collection/src/cuda/dragon_li` |
| `suites/tensorcore-microbenchmarks` | Extracted from `gpu-app-collection/src/cuda/tensorcore-microbenchmarks` |
| `suites/custom-apps` | Extracted from `gpu-app-collection/src/cuda/custom-apps` |
| `suites/microbench` | Extracted from `gpu-app-collection/src/cuda/microbench` |
| `suites/common`, `suites/lib` | Shared support code used by gpu-app-collection suites |

## Compatibility Paths

Older helper scripts still expect:

```text
benchmarks/gpu-app-collection
benchmarks/gpu-app-collection/src/cuda/<suite>
```

Those paths are preserved with symlinks:

```text
benchmarks/gpu-app-collection -> common/gpu-app-collection-harness
benchmarks/common/gpu-app-collection-harness/src/cuda/rodinia -> ../../../../suites/rodinia
```

## Prebuilt Binaries

The canonical prebuilt binaries remain in:

```text
benchmarks/common/gpu-app-collection-harness/bin/12.3/release
```

For convenience, selected suite-level binary links are also exposed under:

```text
benchmarks/suites/<suite>/prebuilt/12.3/release
```

Currently linked suites include Rodinia, Parboil, PolyBench, Pannotia,
ISPASS-2009, LonestarGPU, Proxy Apps DOE, and Custom Apps.


# Benchmark Suite Layout

The current `gpu_benchmark/` tree keeps user-facing benchmark manifests under
`benchmarks/`, while preserving the source/binary/data locations used by the
runner.

## Suites

| Suite path | Origin |
|---|---|
| `suites/graphBIG` | Standalone GraphBIG checkout used directly by manifests |
| `common/gpu-app-collection-harness/src/cuda` | Source tree for Rodinia, Parboil, PolyBench, Pannotia, ISPASS, Lonestar, proxy apps, microbenchmarks, and other gpu-app-collection suites |
| `benchmarks/main/local` | Local benchmark drop zone for new repo-specific workloads |

## Compatibility Paths

Older helper scripts still expect:

```text
gpu_benchmark/gpu-app-collection
gpu_benchmark/gpu-app-collection/src/cuda/<suite>
```

Those paths are preserved with symlinks:

```text
gpu_benchmark/gpu-app-collection -> common/gpu-app-collection-harness
```

## Prebuilt Binaries

The canonical prebuilt binaries remain in:

```text
gpu_benchmark/common/gpu-app-collection-harness/bin/12.3/release
```

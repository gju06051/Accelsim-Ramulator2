# Official-Derived Memory Benchmarks

This prepare set turns the locally staged DLRM, GNN, and CORAL2 sources into
AccelSim-friendly CUDA proxy rows promoted into the main manifest.  The goal is
not to claim MLPerf or CORAL2 submission compliance.  The goal is to preserve
the memory behavior that is useful for AccelSim + Ramulator2 studies while
keeping the inputs runnable on the local simulator.

## Source Provenance

| Group | Local source | What is reused |
| --- | --- | --- |
| DLRM | `gpu_benchmark/benchmarks/prepare/dlrm/inference/recommendation/dlrm_v2` and `dlrm_v3` | Multi-hot embedding-bag fanout, DLRMv2 debug multihot sizes, quantile fanout, and DLRMv3 long sequence gather structure. |
| GNN | `gpu_benchmark/benchmarks/prepare/dlrm/inference/graph/R-GAT` and `gpu_benchmark/benchmarks/prepare/gnn/gsuite` | R-GAT feature fetch / relation aggregation pattern and gSuite PubMed node/edge/feature dimensions. |
| CORAL2 | `gpu_benchmark/benchmarks/prepare/coral2/*.zip` | RAJAPerf CUDA kernel families and CORAL2 transport/hydro/reduction access motifs. |

The full official DLRM/R-GAT datasets and models are too large for routine
AccelSim runs.  These rows therefore use deterministic synthetic indices and
features with official-derived shapes.

The proxy initializes arrays on the host and transfers them with `cudaMemcpy`.
This keeps bounded AccelSim validation focused on the benchmark kernel instead
of spending the first 50k cycles in synthetic input-fill kernels.  The GNN
relation aggregation rows use destination-indexed edge outputs rather than
floating-point global atomics because current AccelSim PTX handling is not
stable for CUDA 12 `red.global.add.f32` in this path.

## Build

```bash
cd gpu_benchmark/benchmarks/prepare
make official_memory_proxy CUDA_ARCH=80
```

The binary is:

```text
gpu_benchmark/benchmarks/prepare/bin/official_memory_proxy
```

## Manifest

`official_memory_manifest.tsv` mirrors the promoted main rows. Run just this
group with:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --manifest ../../gpu_benchmark/benchmarks/prepare/official_memory_manifest.tsv \
  --latencies 0 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --gpgpusim-host-timing on \
  --max-cycle 50000 \
  --timeout 900 \
  --jobs 8 \
  --out-dir results/h100_1stack_official_memory_smoke
```

Use `--max-cycle 0` only after the bounded backend smoke passes.

## Local Validation

The H100 1/5-stack Samsung HBM3SID q64 bounded smoke passed on 2026-05-26:

```text
results/h100_1stack_official_memory_smoke_q64_20260526_v6/summary.csv
status_counts=MAX_CYCLE_OK:13
```

Every row launched one CUDA kernel, enabled all 16 Ramulator2-backed memory
partitions, emitted Ramulator stats, and emitted core granularity metrics.
The run is bounded by `--max-cycle 50000`, so it validates backend wiring and
early memory behavior, not full application completion.

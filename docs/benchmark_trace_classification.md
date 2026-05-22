# SG-HBM GPU Trace Benchmark Classification

This document records the first benchmark-classification workflow for SG-HBM.
The goal is not performance measurement yet. The goal is to run real GPU
benchmarks under NVBit, extract memory-access trace metrics, and classify each
benchmark into one of three SG-HBM access-locality classes.

## Classes

| Class | Meaning | Examples |
| --- | --- | --- |
| Streaming | Regular, mostly sequential or dense access | STREAM, GEMM, dense kernels, sequential scans |
| Mixed-locality | Structured reuse, partially regular access | stencil, stride, some SpMV, some GNN kernels |
| Irregular | Data-dependent random or scattered access | graph, gather/scatter, embedding, hash |

## Quantitative Rule

The initial classifier uses compact NVBit memory traces with records of the
form:

```text
0xADDR R/W SIZE
```

Primary metrics:

| Metric | Definition | Why it matters |
| --- | --- | --- |
| `seq_ratio` | Fraction of transitions that continue to the next 32B atom | Captures streaming/coalesced progression |
| `row_temporal_hit_1KB` | Fraction of recent-window accesses revisiting a 1KB row | Captures A1024 row temporal locality |
| `sector_temporal_hit_256B` | Fraction of recent-window accesses revisiting a 256B sector | Captures mid-grain sector locality |
| `row_util_1KB` | Average unique 32B atoms touched per 1KB row, normalized by 32 | Captures eventual row coverage |
| `sector_reuse_256B` | Average unique 32B atoms touched per 256B sector, normalized by 8 | Captures eventual sector coverage |

Initial class thresholds:

```text
Streaming:
  seq_ratio >= 0.50 and row_temporal_hit_1KB >= 0.50

Irregular:
  seq_ratio < 0.20 and sector_temporal_hit_256B < 0.25

Mixed-locality:
  otherwise
```

This rule intentionally separates temporal locality from eventual row/sector
coverage. A graph workload may eventually touch many atoms in a row, but if
the accesses are not temporally clustered, it is still a poor fit for large
activation.

## Files

| File | Purpose |
| --- | --- |
| `gpu_benchmark/sg_hbm_benchmark_manifest.tsv` | Benchmark list and expected semantic class |
| `gpu_benchmark/run_sg_hbm_trace_classification.sh` | End-to-end NVBit trace and classification runner |
| `tools/sg_hbm_classify_trace.py` | Compact trace metric extractor and classifier |
| `gpu_benchmark/run_with_nvbit_mem_trace.sh` | NVBit wrapper used by the runner |
| `gpu_benchmark/sg_hbm_trace_classification/status.tsv` | Latest per-benchmark run status |
| `gpu_benchmark/sg_hbm_trace_classification/summary.csv` | Latest successful classification summary |

## Runner

Use capped NVBit output for early classification runs:

```bash
MEMTRACE_MAX_RECORDS=50000 \
INSTR_END=100000 \
TIMEOUT_SECONDS=120 \
MAX_RECORDS=1000000 \
FORCE=1 \
gpu_benchmark/run_sg_hbm_trace_classification.sh
```

To run only selected cases:

```bash
CASE_REGEX='polybench_gemm|polybench_2dconv|graphbig_bfs_small' \
MEMTRACE_MAX_RECORDS=50000 \
INSTR_END=100000 \
TIMEOUT_SECONDS=120 \
MAX_RECORDS=1000000 \
FORCE=1 \
gpu_benchmark/run_sg_hbm_trace_classification.sh
```

`MEMTRACE_MAX_RECORDS` is important because raw NVBit memory logs can grow very
quickly.

## Current Manifest

| Benchmark | Suite | Expected class | Main reason |
| --- | --- | --- | --- |
| `polybench_gemm` | polybench | Streaming | Dense regular matrix access |
| `polybench_2mm` | polybench | Streaming | Dense regular matrix multiplication |
| `polybench_3mm` | polybench | Streaming | Dense regular matrix multiplication |
| `polybench_2dconv` | polybench | Mixed-locality | Structured sliding-window locality |
| `polybench_3dconv` | polybench | Mixed-locality | Structured sliding-window locality |
| `polybench_fdtd2d` | polybench | Mixed-locality | Structured grid reuse |
| `graphbig_bfs_small` | graphBIG | Irregular | Frontier-driven graph traversal |
| `graphbig_sssp_small` | graphBIG | Irregular | Data-dependent graph traversal |
| `graphbig_connected_comp_small` | graphBIG | Irregular | Graph component traversal and updates |
| `parboil_stencil` | parboil | Mixed-locality | Structured stencil reuse |
| `parboil_histo` | parboil | Irregular | Random/scattered histogram updates |
| `lonestar_bfs_rmat12` | lonestar | Irregular | Graph traversal |

## Latest Run Result

Run settings:

```text
MEMTRACE_MAX_RECORDS=50000
INSTR_END=100000
TIMEOUT_SECONDS=120
MAX_RECORDS=1000000
```

Successful classifications:

| Benchmark | Suite | Expected | Predicted | Records | seq | rowT | secT | Reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `polybench_gemm` | polybench | Streaming | Streaming | 1000000 | 0.683 | 0.700 | 0.685 | high sequentiality and high temporal row locality |
| `polybench_2dconv` | polybench | Mixed-locality | Streaming | 1000000 | 0.785 | 0.769 | 0.716 | high sequentiality and high temporal row locality |
| `polybench_3dconv` | polybench | Mixed-locality | Streaming | 1000000 | 0.781 | 0.782 | 0.728 | high sequentiality and high temporal row locality |
| `graphbig_bfs_small` | graphBIG | Irregular | Irregular | 93204 | 0.037 | 0.548 | 0.135 | low sequentiality and low temporal sector locality |
| `graphbig_sssp_small` | graphBIG | Irregular | Irregular | 106236 | 0.014 | 0.110 | 0.035 | low sequentiality and low temporal sector locality |
| `graphbig_connected_comp_small` | graphBIG | Irregular | Mixed-locality | 869295 | 0.300 | 0.496 | 0.356 | moderate temporal sector locality without streaming |

Failed or incomplete cases:

| Benchmark | Status | Cause |
| --- | --- | --- |
| `polybench_2mm` | `TRACE_FAIL`, exit 124 | Timed out at 120s under NVBit instrumentation |
| `polybench_3mm` | `TRACE_FAIL`, exit 124 | Timed out at 120s under NVBit instrumentation |
| `polybench_fdtd2d` | `TRACE_FAIL`, exit 124 | Timed out at 120s under NVBit instrumentation |
| `parboil_stencil` | `TRACE_FAIL`, exit 255 | Missing command-line grid/time arguments |
| `parboil_histo` | `TRACE_FAIL`, exit 255 | Missing input file |
| `lonestar_bfs_rmat12` | `TRACE_FAIL`, exit 255 | Referenced graph input file is not present |

## Observations

1. The automatic NVBit trace-to-classification path works for runnable
   benchmarks.
2. The semantic class and trace-measured class can differ. For example,
   PolyBench 2D/3D convolution is semantically stencil-like, but the observed
   global-memory trace is streaming-like under the current input and sampling
   window.
3. Temporal sector locality is more useful than eventual row coverage for
   separating graph workloads. GraphBIG BFS eventually covers many atoms in a
   row, but its low temporal sector locality keeps it irregular.
4. The next manifest cleanup should either provide valid Parboil/Lonestar
   inputs or remove those entries from the default runnable set.

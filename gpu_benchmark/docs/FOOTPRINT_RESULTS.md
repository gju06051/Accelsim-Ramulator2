# GPU Benchmark Footprint Results

Measured on the real GPU run path with the CUDA allocation tracer in
`gpu_benchmark/footprint_tracer`.

## Method

The footprint reported here is peak live CUDA device/managed allocation bytes
observed through an `LD_PRELOAD` tracer. This is a practical first-pass filter
for A100 40 MiB L2 capacity, but it is not the exact cache working set or the
exact number of bytes touched by kernels.

Generated result files:

- Full summary: `traces/run_logs/footprint/summary.tsv`
- Ranked summary: `traces/run_logs/footprint/ranked_footprints.tsv`
- Passing workloads above 40 MiB: `traces/run_logs/footprint/over_40mb.tsv`
- Passing workloads at or below 40 MiB: `traces/run_logs/footprint/under_or_equal_40mb.tsv`
- Failed workloads: `traces/run_logs/footprint/failed.tsv`

Note: this footprint sweep was produced before the current benchmark pruning.
It includes historical UVM measurements, but UVM workloads are now excluded
from the active Sectored-Access-DRAM simulation set.

## Run Summary

- Total measured cases: 97
- Passing cases: 96
- Failed cases: 1
- Passing cases above 40 MiB: 27
- Passing cases at or below 40 MiB: 69

## Passing Workloads Above 40 MiB

| Rank | Suite | Benchmark | Dataset | Peak MiB |
|---:|---|---|---|---:|
| 1 | graphBIG | connected_comp | LDBC_1000k | 490.229 |
| 2 | graphBIG | sssp_data_thread_centric | LDBC_1000k | 479.076 |
| 3 | parboil | lbm | short | 370.312 |
| 4 | parboil | mri-gridding | small | 316.790 |
| 5 | graphBIG | bfs_data_thread_centric | LDBC_100k | 279.177 |
| 6 | graphBIG | bfs_data_warp_centric | LDBC_100k | 279.177 |
| 7 | parboil | histo | default | 253.012 |
| 8 | graphBIG | bfs_topo_frontier | LDBC_1000k | 234.230 |
| 9 | graphBIG | sssp_data_thread_centric | LDBC_100k | 168.504 |
| 10 | graphBIG | sssp_data_warp_centric | LDBC_100k | 168.504 |
| 11 | polybench | polybench-gesummv | default | 128.047 |
| 12 | polybench | polybench-2DConvolution | default | 128.000 |
| 13 | polybench | polybench-3DConvolution | default | 128.000 |
| 14 | lonestar | bfs_wlw | rmat12 | 102.931 |
| 15 | proxy | lulesh | dt0.001 | 84.629 |
| 16 | polybench | polybench-2mm | default | 80.000 |
| 17 | polybench | polybench-bicg | default | 64.062 |
| 18 | polybench | polybench-mvt | default | 64.062 |
| 19 | polybench | polybench-atax | default | 64.047 |
| 20 | pannotia | mis | G3_circuit | 59.464 |
| 21 | pannotia | color_maxmin | G3_circuit | 53.416 |
| 22 | graphBIG | connected_comp | LDBC_100k | 49.107 |
| 23 | polybench | polybench-fdtd2d | default | 48.018 |
| 24 | polybench | polybench-gramschmidt | default | 48.000 |
| 25 | polybench | polybench-syr2k | default | 48.000 |
| 26 | pannotia | color_max | G3_circuit | 47.368 |
| 27 | rodinia | heartwall | test20 | 41.343 |

## Notes

- `lonestar/pta/pine_no_verify` allocated about 3954.915 MiB but failed with
  an illegal memory access, so it is excluded from the candidate list.
- `rodinia/hotspot3D`, `rodinia/particlefilter_float`, and
  `rodinia/particlefilter_naive` passed but the tracer saw 0 bytes of
  CUDA allocation. Treat those entries as "not captured by this allocation
  tracer" rather than real zero-footprint workloads.
- For Sectored-Access-DRAM profiling, the strongest first candidates are the
  graph workloads and irregular/scatter-heavy workloads above 40 MiB:
  GraphBIG BFS/SSSP/connected components, Pannotia MIS/coloring, Parboil histo,
  Parboil mri-gridding, and Lonestar BFS.

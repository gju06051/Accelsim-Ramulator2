# Graph Benchmark Inputs

This note records the graph benchmark rows that were scaled beyond the original
small sample inputs for AccelSim + Ramulator2 runs.

## Main Manifest Rows

`manifest.tsv` keeps the routine main benchmark names stable, but changes the
GraphBIG and Lonestar input size:

| Benchmark | Suite | Input | Arguments | How the input was prepared |
| --- | --- | --- | --- | --- |
| `graphbig_bfs_data_warp` | GraphBIG | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k --root 90628` | Staged from the existing local GraphBIG LDBC dataset copy. Root `90628` is a high-degree vertex in this dataset. |
| `graphbig_bfs_topo_atomic` | GraphBIG | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k --root 90628` | Same staged LDBC_100k input as the BFS data-warp row. |
| `graphbig_sssp_data_warp` | GraphBIG | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k --root 90628` | Same staged LDBC_100k input; edge weights are initialized by the benchmark. |
| `graphbig_triangle_count` | GraphBIG | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | Same staged LDBC_100k CSR and CSV files. |
| `graphbig_kcore` | GraphBIG | `gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | `--dataset gpu_benchmark/suites/graphBIG/dataset/LDBC_100k` | Same staged LDBC_100k CSR and CSV files. |
| `lonestar_bfs_wlw` | LonestarGPU | `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr` | `gpu_benchmark/common/gpu-app-collection-harness/bin/12.3/release/lonestar-bfs-wlw <input.gr>` | Generated with `gpu_benchmark/scripts/generate_lonestar_rmat_gr.py --scale 16 --edge-factor 16`. |
| `lonestar_sssp_wln` | LonestarGPU | `gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr` | `gpu_benchmark/common/gpu-app-collection-harness/bin/12.3/release/lonestar-sssp-wln <input.gr>` | Same generated RMAT16 `.gr` input as BFS. Edge weights are stored as 32-bit values in the `.gr` file. |

## Staged Dataset Sizes

| Dataset | Vertices | Directed edges | Role |
| --- | ---: | ---: | --- |
| GraphBIG `small` | 1,000 | 29,790 | Original smoke/sample dataset, no longer used by main GraphBIG rows. |
| GraphBIG `LDBC_100k` | 100,000 | 2,887,796 | Main GraphBIG dataset. |
| GraphBIG `LDBC_1000k` | 1,000,000 | 28,826,024 | Large GraphBIG validation dataset. |
| Lonestar `rmat12.sym.gr` | 4,096 | 59,320 | Original small Lonestar input, no longer used by main Lonestar rows. |
| Lonestar `rmat16.sym.gr` | 65,536 | 1,048,450 | Main Lonestar medium input. |
| Lonestar `rmat20.sym.gr` | 1,048,576 | 16,777,048 | Large Lonestar validation input. |

The large dataset payloads are staged locally and ignored by Git. Commit the
manifest rows and generation script, not the generated graph files.

## Extra Medium/Large Manifest

`manifest.graph_medium_large.tsv` is a validation-only manifest. It includes:

| Benchmark | Purpose |
| --- | --- |
| `graphbig_bfs_data_warp_ldbc100k` | Main-sized GraphBIG BFS check. |
| `graphbig_sssp_data_warp_ldbc100k` | Main-sized GraphBIG SSSP check. |
| `graphbig_kcore_ldbc100k` | Main-sized GraphBIG k-core check. |
| `graphbig_bfs_data_warp_ldbc1000k` | Large GraphBIG BFS check. |
| `graphbig_sssp_data_warp_ldbc1000k` | Large GraphBIG SSSP check. |
| `lonestar_bfs_wlw_rmat16` | Main-sized Lonestar BFS check. |
| `lonestar_sssp_wln_rmat16` | Main-sized Lonestar SSSP check. |
| `lonestar_bfs_wlw_rmat20` | Large Lonestar BFS check. |
| `lonestar_sssp_wln_rmat20` | Large Lonestar SSSP check. |

## Lonestar `.gr` Generation

The generator writes the Galois/Lonestar binary graph layout consumed by the
packaged LonestarGPU 2.x binaries:

```text
uint64 version = 1
uint64 edge_data_size = 4
uint64 num_nodes
uint64 num_edges
uint64 out_index[num_nodes]
uint32 destinations[num_edges]
uint32 edge_data[num_edges]
```

Regenerate the staged RMAT inputs from the repository root:

```bash
gpu_benchmark/scripts/generate_lonestar_rmat_gr.py \
  --scale 16 \
  --edge-factor 16 \
  --output gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat16.sym.gr

gpu_benchmark/scripts/generate_lonestar_rmat_gr.py \
  --scale 20 \
  --edge-factor 16 \
  --output gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/lonestargpu-2.0/inputs/rmat20.sym.gr
```

The RMAT graph is symmetrized, deterministic by default, and stores unit
32-bit edge weights for SSSP compatibility.

## Validation

The scaled inputs were checked through the H100 SXM Samsung HBM3 AccelSim +
Ramulator2 configs with queue size 64.

| Check | Result |
| --- | --- |
| H100 1-stack GraphBIG high-root smoke | 4/4 `MAX_CYCLE_OK`, 16 Ramulator2 partitions enabled, Ramulator stats present. |
| H100 full-stack GraphBIG high-root smoke | 4/4 `MAX_CYCLE_OK`, 80 Ramulator2 partitions enabled, Ramulator stats present. |
| H100 1-stack Lonestar RMAT16 deeper run | BFS/SSSP both `MAX_CYCLE_OK`, 16 partitions active, no backend rejects. |

Relevant result summaries:

```text
simulator/accelsim_ramulator/results/h100_1stack_graphbig_highroot_smoke_q64_20260524/summary.csv
simulator/accelsim_ramulator/results/h100_full_graphbig_highroot_smoke_q64_20260524/summary.csv
simulator/accelsim_ramulator/results/h100_1stack_lonestar_rmat16_deeper_q64_20260524/summary.csv
```

`MAX_CYCLE_OK` is expected for these bounded validation runs.

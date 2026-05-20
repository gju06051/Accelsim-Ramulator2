# AccelSim + Ramulator2 Final Benchmark Manifest

Last updated: 2026-05-20

Recommended final manifest:

```text
benchmarks/final_manifest.tsv
```

This is the smaller representative set for AccelSim + Ramulator2 sweeps. It is
derived from `benchmarks/operational_manifest.tsv`, which remains the broader
validated pool.

## Selection Policy

- Keep benchmarks that validated under the bounded AccelSim + Ramulator2 run.
- Exclude benchmarks that require missing current-repo inputs or still fail
  outside Ramulator2-specific paths.
- Collapse near-duplicate algorithm variants while preserving distinct memory
  behavior.
- Keep all major suites represented instead of letting graph or microbenchmark
  variants dominate the run list.
- Balance the final set across streaming, mixed-locality, and irregular memory
  behavior.

## Final Set Size

The final manifest has 45 benchmarks.

| Class | Count |
| --- | ---: |
| Streaming | 11 |
| Mixed-locality | 17 |
| Irregular | 17 |

| Suite | Count |
| --- | ---: |
| polybench | 7 |
| graphBIG | 5 |
| ispass-2009 | 3 |
| rodinia | 7 |
| proxy-apps | 2 |
| microbench | 8 |
| parboil | 4 |
| lonestar | 2 |
| pannotia | 5 |
| dragon-li | 2 |

## De-duplication Choices

| Family | Keep | Defer from final set |
| --- | --- | --- |
| PolyBench dense linear algebra | `polybench_2mm`, `polybench_bicg`, `polybench_atax`, `polybench_covariance`, `polybench_gramschmidt` | `polybench_3mm`, `polybench_gemm`, `polybench_syrk`, `polybench_syr2k`, `polybench_correlation`, `polybench_gesummv`, `polybench_mvt` |
| PolyBench stencil/grid | `polybench_2dconv`, `polybench_fdtd2d` | `polybench_3dconv` |
| graphBIG BFS/SSSP | `graphbig_bfs_data_warp`, `graphbig_bfs_topo_atomic`, `graphbig_sssp_data_warp` | Other BFS/SSSP thread/frontier/unroll/topology variants |
| graphBIG structural graph kernels | `graphbig_triangle_count`, `graphbig_kcore` | `graphbig_betweenness`, `graphbig_connected_comp`, `graphbig_degree_centr`, `graphbig_gc_topo_thread` |
| ISPASS | `ispass_lps`, `ispass_lib`, `ispass_ray` | BFS/NQU/NN/STO variants for routine sweeps |
| Rodinia | `rodinia_streamcluster`, `rodinia_backprop`, `rodinia_srad_v1`, `rodinia_srad_v2`, `rodinia_particlefilter_float`, `rodinia_gaussian`, `rodinia_lavamd` | `rodinia_particlefilter_naive`, `rodinia_pathfinder`, `rodinia_nw`, `rodinia_myocyte`, `rodinia_nn`, `rodinia_heartwall` |
| Microbenchmarks | `micro_mem_atom_size`, `micro_mem_bw`, `micro_mem_lat`, `micro_l1_bw_128`, `micro_l2_bw_32f`, `micro_l2_lat`, `micro_atomic_add_bw_conflict`, `micro_l2_access_grain` | Other L1/L2/cacheline/atomic width variants |
| Parboil | `parboil_stencil`, `parboil_lbm`, `parboil_mri_q`, `parboil_sgemm` | `parboil_bfs`, `parboil_mri_gridding` |
| Lonestar | `lonestar_bfs_wlw`, `lonestar_sssp_wln` | `lonestar_bfs`, `lonestar_bfs_wla`, `lonestar_sssp` |
| Pannotia | `pannotia_mis`, `pannotia_color_maxmin`, `pannotia_sssp_ell`, `pannotia_pagerank_spmv`, `pannotia_fw_block` | `pannotia_color_max`, `pannotia_sssp`, `pannotia_fw` |
| Dragon-li | `dragon_join`, `dragon_amr` | `dragon_bfs`, `dragon_sssp` |

## Current Validation Caveats

- `parboil_mri_gridding` is not in the final set. The current repo is missing
  `small.uks.data`, and with an external data overlay the benchmark still
  crashes under both Ramulator2 and fixed-latency backends.
- `rodinia_nn` is not in the final set. It requires generated `cane4_*.db`
  inputs that are not present in the current repo tree, although it can run
  with an external benchmark overlay.
- The broader operational manifest is still useful when coverage matters more
  than runtime. Use this final manifest when sweep cost, result readability, and
  variant de-duplication are the priority.

## Runner Usage

List the final benchmark set:

```bash
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_final \
  --list-benchmarks
```

Run a bounded Ramulator2 smoke sweep:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_final \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_1stack \
  --config-overrides '-gpgpu_memory_partition_indexing 2' \
  --a100-l2-8mb \
  --max-cycle 50000 \
  --timeout 600 \
  --jobs 64 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/final_validate_ramulator2
```

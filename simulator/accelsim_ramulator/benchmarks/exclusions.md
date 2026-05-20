# SG-HBM Benchmark Exclusions

This file tracks benchmarks intentionally excluded from the distributable
`benchmarks/operational_manifest.tsv` set after AccelSim compatibility checks.

Last updated: 2026-05-20

## Excluded Candidates

| Benchmark | Suite | Candidate status | Main reason | Evidence |
| --- | --- | --- | --- | --- |
| `lonestar_bfs_atomic` | lonestar | Excluded | Full simulation hits an AccelSim resource-model failure in the atomic BFS path; the PTX also contains `red.global.min.u32`, so it is likely to hit the unsupported RED path after the resource issue. | Crashes under Ramulator2, fixed-latency, and native-style checks. With resource-limit ignore enabled, the log reports `CTA/core = 0, limited by: shmem`. |
| `lonestar_dmr` | lonestar | Excluded | Uses PTX `red.global.min.s32` and `red.global.add.u32`; GPGPU-Sim/AccelSim currently routes RED instructions to an unimplemented `RED_OP` path. | Crashes under Ramulator2, fixed-latency, and native-style checks at `red_impl()`. |
| `lonestar_mst` | lonestar | Excluded | Uses PTX `red.global.add.u32` and `red.global.min.u32`; GPGPU-Sim/AccelSim currently routes RED instructions to an unimplemented `RED_OP` path. | Crashes under Ramulator2, fixed-latency, and native-style checks at `red_impl()`. |
| `lonestar_nsp` | lonestar | Excluded | Uses PTX `red.global.max.s32` and `red.global.add.f32`; GPGPU-Sim/AccelSim currently routes RED instructions to an unimplemented `RED_OP` path. | Crashes under Ramulator2, fixed-latency, and native-style checks at `red_impl()`. |
| `parboil_tpacf` | parboil | Excluded | Uses PTX `red.shared.add.u32`; GPGPU-Sim/AccelSim currently routes RED instructions to an unimplemented `RED_OP` path. | Native gdb reproduction stops at `parboil-tpacf.5.sm_75.ptx:315` with `red.shared.add.u32 [%r158], 1;`. |
| `pannotia_bc` | pannotia | Excluded | Uses PTX `red.global.add.f32`; GPGPU-Sim/AccelSim currently routes RED instructions to an unimplemented `RED_OP` path. | Crashes under Ramulator2, fixed-latency, and native-style checks at `red_impl()`. |
| `pannotia_pagerank` | pannotia | Excluded | Uses PTX `red.global.add.f32`; GPGPU-Sim/AccelSim currently routes RED instructions to an unimplemented `RED_OP` path. | Native gdb reproduction stops at `pagerank.2.sm_62.ptx:82` with `red.global.add.f32 [%rd22], %f3;`. |

## Manifest Policy

- Keep these benchmarks in build-inventory manifests, such as
  `sg_hbm_benchmark_manifest_extra_built.tsv` or
  `sg_hbm_benchmark_manifest_more_suites_built.tsv`, if their binaries exist.
- Exclude them from validated/candidate manifests used for SG-HBM trace
  classification and AccelSim/Ramulator full-simulation sweeps.
- Reconsider them only if RED instruction support or the relevant AccelSim
  resource-model limitation is fixed.

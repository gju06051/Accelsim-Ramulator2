# SG-HBM Operational Benchmark Manifest

Last updated: 2026-05-20

Canonical operational manifest:

```text
benchmarks/operational_manifest.tsv
```

This is the distributable copy of the validated SG-HBM operational manifest.
The large benchmark source/binary/data tree remains external and is located at
runtime through `SGRAM_GPU_BENCHMARK_ROOT`.

## Sources

The operational manifest is the union of the checked candidate manifests below:

| Source manifest | Rows | Role |
| --- | ---: | --- |
| `sg_hbm_benchmark_manifest_broad.tsv` | 59 | Previously checked broad benchmark set |
| `sg_hbm_benchmark_manifest_extra_validated.tsv` | 16 | Additional validated benchmarks |
| `sg_hbm_benchmark_manifest_final.tsv` | 17 | Newly validated lonestar/pannotia/dragon-li set |

Total rows: 92

## Class Distribution

| Class | Count |
| --- | ---: |
| Streaming | 22 |
| Mixed-locality | 27 |
| Irregular | 43 |

## Suite Distribution

| Suite | Count |
| --- | ---: |
| polybench | 15 |
| graphBIG | 17 |
| ispass-2009 | 7 |
| rodinia | 13 |
| proxy-apps | 2 |
| microbench | 15 |
| parboil | 6 |
| lonestar | 5 |
| pannotia | 8 |
| dragon-li | 4 |

## Validation Notes

- No duplicate benchmark names are present in the operational manifest.
- The excluded AccelSim-incompatible benchmarks are absent:
  `lonestar_bfs_atomic`, `lonestar_dmr`, `lonestar_mst`, `lonestar_nsp`,
  `parboil_tpacf`, `pannotia_bc`, and `pannotia_pagerank`.
- Executable paths and input path arguments were checked with each row's
  `workdir` applied.
- Output-only arguments such as `*.out` and `output.txt` are not treated as
  required input files.

## Policy

- Use `benchmarks/operational_manifest.tsv` for future SG-HBM trace
  extraction, Ramulator replay, and AccelSim/Ramulator sweeps unless a narrower
  subset is explicitly needed.
- Keep build-inventory manifests separate from operational manifests.
- Add newly validated benchmarks to the operational manifest only after checking
  that they do not hit known AccelSim unsupported instruction paths.

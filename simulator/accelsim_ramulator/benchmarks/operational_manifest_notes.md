# AccelSim + Ramulator2 Operational Benchmark Manifest

Last updated: 2026-05-20

Canonical operational manifest:

```text
benchmarks/operational_manifest.tsv
```

This is the distributable copy of the validated operational manifest used by
the AccelSim + Ramulator2 runner. The large benchmark source/binary/data tree
remains external and is located at runtime through
`SGRAM_GPU_BENCHMARK_ROOT`.

## Sources

The operational manifest is the union of the checked candidate manifests below:

| Source manifest | Rows | Role |
| --- | ---: | --- |
| `gpu_benchmark/benchmarks/inventory/sg_hbm_benchmark_manifest_broad.tsv` | 59 | Previously checked broad benchmark set |
| `gpu_benchmark/benchmarks/inventory/sg_hbm_benchmark_manifest_extra_validated.tsv` | 16 | Additional validated benchmarks |
| `gpu_benchmark/benchmarks/inventory/sg_hbm_benchmark_manifest_final.tsv` | 17 | Newly validated lonestar/pannotia/dragon-li set |

Total rows: 92

The narrower recommended sweep set is tracked separately in
`benchmarks/final_manifest.tsv`.

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

- Use `benchmarks/operational_manifest.tsv` for AccelSim + Ramulator2 sweeps,
  Ramulator replay generation, and trace extraction when broad coverage is
  needed.
- Use `benchmarks/final_manifest.tsv` for routine experiments where runtime,
  result readability, and variant de-duplication are more important than
  maximum coverage.
- Keep build-inventory manifests separate from operational manifests.
- Add newly validated benchmarks to the operational manifest only after checking
  that they do not hit known AccelSim unsupported instruction paths.

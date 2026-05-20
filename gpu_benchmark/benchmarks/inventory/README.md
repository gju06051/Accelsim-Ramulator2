# Benchmark Inventory Manifests

This directory keeps the legacy benchmark manifest TSV files that were used
while building up the AccelSim + Ramulator2 benchmark set.

This directory replaces the older top-level TSV manifest location.

The canonical manifest for current AccelSim + Ramulator2 validation runs is:

```text
simulator/accelsim_ramulator/benchmarks/operational_manifest.tsv
```

## Files

| File | Purpose |
| --- | --- |
| `sg_hbm_benchmark_manifest.tsv` | Original trace-classification seed set |
| `sg_hbm_benchmark_manifest_broad.tsv` | Broad early benchmark candidate set |
| `sg_hbm_benchmark_manifest_extra_built.tsv` | Additional binaries observed as built |
| `sg_hbm_benchmark_manifest_extra_validated.tsv` | Additional benchmarks validated before merge |
| `sg_hbm_benchmark_manifest_final.tsv` | Later lonestar/pannotia/dragon-li validation set |
| `sg_hbm_benchmark_manifest_more_suites_built.tsv` | More-suite build inventory |
| `sg_hbm_benchmark_manifest_more_suites_validated.tsv` | More-suite validated subset |
| `sg_hbm_benchmark_manifest_operational.tsv` | Historical 92-row operational manifest copy |

Keep new validation-facing manifests under `simulator/accelsim_ramulator/benchmarks/`.
Keep the user-editable main run list under
`gpu_benchmark/benchmarks/main/manifest.tsv`.

Use this directory only for archived candidate inventories and
trace-classification input lists.

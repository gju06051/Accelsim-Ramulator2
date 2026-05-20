# Local Benchmark Drop Zone

Put new local benchmarks in subdirectories here.

Recommended shape:

```text
<benchmark-name>/
  bin/<benchmark-executable>
  input/<small-input-files>
  README.md
```

Then add a TSV row to `../manifest.tsv`. Prefer command and input paths that
start with `gpu_benchmark/...`; the AccelSim + Ramulator2 runner expands those
paths to the active benchmark root.

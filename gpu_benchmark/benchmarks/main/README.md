# Main Benchmark Set

`manifest.tsv` is the main AccelSim + Ramulator2 run list for this benchmark
tree. The simulator preset `accelsim_ramulator_main` loads this file.

Use `local/` for benchmarks that are added directly in this repo:

```text
local/<benchmark-name>/
  bin/
  input/
  README.md
```

After adding a local benchmark, add a row to `manifest.tsv` and test it with:

```bash
cd ../../../simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --benchmarks <benchmark-name> \
  --list-benchmarks
```

For the full add-and-validate workflow, see `../README.md`.

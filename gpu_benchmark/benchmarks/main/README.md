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

## Trace-Driven Rows

Rows such as `nvcomp_*`, `tango_*`, and `cudf_*` use prepared Accel-Sim traces
instead of native CUDA execution. Their `manifest.tsv` command calls
`gpu_benchmark/scripts/run_accelsim_trace_replay.py --benchmark <name>`, and
the helper resolves the trace path from `trace_manifest.tsv`.

This keeps the normal AccelSim + Ramulator2 runner path intact: the runner still
creates the per-run `gpgpusim.config`, Ramulator2 YAML, and backend environment,
then the helper replays `kernelslist.g` with `accel-sim.out -trace`.

The replay helper reads `trace_manifest.tsv` by default. For a generated
memory-intensive trace set, pass an alternate manifest through:

```bash
SGRAM_TRACE_MANIFEST=gpu_benchmark/benchmarks/main/trace_manifest.memory_intensive.tsv
```

Generate that alternate manifest and its target trace paths with
`gpu_benchmark/scripts/prepare_memory_intensive_accelsim_traces.py`; activate it
as the default only after the larger traces exist and replay validation passes.

## Scaled Native Inputs

Some native CUDA rows are intentionally larger than their default sample
settings so the 1/5-stack H100 configuration still produces enough DRAM traffic
for representative AccelSim + Ramulator2 metrics. These rows are scaled directly
through command-line arguments in `manifest.tsv`:

```text
rodinia_srad_v2, rodinia_gaussian, rodinia_lavamd, rodinia_nw
rodinia_pathfinder
dragon_join
```

Rows that depend on fixed local graph/input files or prepared traces should be
scaled by adding a larger dataset or regenerating traces first, rather than only
changing the manifest row.

`ispass_ray`, `ispass_nqu`, `rodinia_particlefilter_naive`, and `dragon_amr`
were left at their original sample settings because larger command-line inputs
did not produce enough Ramulator DRAM traffic to make them useful as
representative memory benchmarks, or made the run much longer without a
proportional memory-traffic gain.

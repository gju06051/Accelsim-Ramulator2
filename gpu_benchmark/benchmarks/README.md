# Benchmark Management

This directory is the user-facing benchmark management area.

## Directory Roles

| Path | Role |
| --- | --- |
| `main/manifest.tsv` | Main benchmark list loaded by the runner preset `accelsim_ramulator_main` |
| `main/local/` | Recommended location for new local benchmark binaries, inputs, and wrappers |
| `prepare/` | Isolated staging area for new benchmark candidates before main promotion |
| `inventory/` | Archived candidate manifests used while building the benchmark pool |

Do not put large generated traces or run results here. Use the simulator
`results/` directory or the existing trace storage paths instead.

The top-level `README.md` keeps the current main benchmark count and a
field-by-field view of the `main/manifest.tsv` benchmark names.

## Add a Benchmark

1. Create a directory under `main/local/`:

```text
gpu_benchmark/benchmarks/main/local/my_benchmark/
  bin/my_benchmark
  input/
  README.md
```

2. Make sure the executable can run from an AccelSim run directory. Any input
   path in the manifest should start with `gpu_benchmark/...` so the runner can
   expand it to an absolute path.

3. Add one row to `main/manifest.tsv`.

The TSV schema is:

```text
name	suite	expected_class	workdir	command	main_reason
```

Field meanings:

| Field | Meaning |
| --- | --- |
| `name` | Unique benchmark id used by `--benchmarks` and result directories |
| `suite` | Suite or group name, for example `local`, `rodinia`, or `graphBIG` |
| `expected_class` | One of `Streaming`, `Mixed-locality`, or `Irregular` |
| `workdir` | Benchmark source directory used to resolve relative executable paths |
| `command` | Executable and arguments |
| `main_reason` | Short reason this benchmark belongs in the main set |

Example row:

```text
my_benchmark	local	Mixed-locality	gpu_benchmark/benchmarks/main/local/my_benchmark	bin/my_benchmark --input gpu_benchmark/benchmarks/main/local/my_benchmark/input/small.dat	Local mixed-locality CUDA benchmark
```

4. Check that the runner can load the manifest:

```bash
cd simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_main \
  --list-benchmarks
```

5. Run only the new benchmark first:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks my_benchmark \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_1stack \
  --config-overrides '-gpgpu_memory_partition_indexing 2' \
  --a100-l2-8mb \
  --max-cycle 50000 \
  --timeout 600 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/local_my_benchmark_smoke
```

## Promotion Policy

Keep experimental additions in `main/local/` until they pass a bounded
Ramulator2 run. If a benchmark becomes part of the stable shared set, mirror the
row into `simulator/accelsim_ramulator/benchmarks/final_manifest.tsv` and add a
short note to `simulator/accelsim_ramulator/benchmarks/final_manifest_notes.md`.

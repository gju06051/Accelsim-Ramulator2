# Configuring AccelSim + Ramulator2 Runs

The benchmark runner now lets AccelSim and Ramulator2 configs be selected as
files instead of editing the script.

## AccelSim Config

The base AccelSim/GPGPU-Sim config is copied into every run directory as
`gpgpusim.config`.

```bash
--gpgpusim-config /path/to/gpgpusim.config
```

Relative paths are resolved from the current directory, then from
`simulator/accelsim_ramulator`, then from the workspace root.

Additional AccelSim overrides can be supplied inline:

```bash
--config-overrides '-gpgpu_memory_partition_indexing 2;-gpgpu_dram_return_queue_size 256'
```

or as reusable files:

```bash
--accelsim-config-override-file configs/accelsim/a100_1stack_8mb_l2.config
```

The generated run config records the source base config and override files in
comments near the appended runner block.

## Ramulator2 Config

The Ramulator2 YAML is selected with:

```bash
--ramulator-config configs/ramulator/a100_hbm2e_1stack.yaml
```

For `--backend ramulator2`, the runner copies the selected YAML into each run
directory as `ramulator2.yaml` and exports:

```bash
SGRAM_RAMULATOR_CONFIG=<run-dir>/ramulator2.yaml
```

The result `summary.csv` also records:

- `gpgpusim_config_source`
- `gpgpusim_config_run`
- `config_override_files`
- `ramulator_config_source`
- `ramulator_config_run`

## A100 HBM2e Examples

Quick 1-stack smoke:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks micro_mem_bw \
  --config-variant a100_1stack \
  --ramulator-config configs/ramulator/a100_hbm2e_1stack.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --timeout 600 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/a100_hbm2e_1stack_smoke
```

Full 40-memory-partition A100 HBM2e-style run:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --config-variant a100_full \
  --ramulator-config configs/ramulator/a100_hbm2e_80gb.yaml \
  --latencies 0 \
  --queue-limits 128 \
  --max-cycle 50000 \
  --timeout 600 \
  --jobs 64 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/a100_hbm2e_80gb_smoke
```

The 1-stack config is intended for fast validation. The 40-channel config should
be used when the AccelSim config exposes 40 memory partitions.

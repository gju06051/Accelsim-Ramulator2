# Accel-Sim Config Overrides

Place AccelSim/GPGPU-Sim config fragments here for experiments using the
Ramulator2 backend.

The runner normally creates a per-run effective `gpgpusim.config` by merging a
base config with the selected overrides. Select the base config with:

```bash
--gpgpusim-config /path/to/gpgpusim.config
```

Apply one or more fragments with:

```bash
--accelsim-config-override-file configs/accelsim/a100_1stack_8mb_l2.config
```

For final or shared experiments, prefer the clean generated configs in
`canonical/`:

```bash
simulator/accelsim_ramulator/scripts/generate_canonical_accelsim_configs.py

python3 simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py \
  --gpgpusim-config simulator/accelsim_ramulator/configs/accelsim/canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config \
  --config-variant canonical
```

`--config-variant canonical` does not append architecture overrides. It is for
canonical configs that already contain the intended A100/H100 geometry, L2,
clock, queue, and address mapping lines. See `../CONFIG_MATRIX.md` for the
recommended AccelSim/Ramulator2 pairings and validation criteria.

The normal A100-style 5-stack baseline is:

```bash
--config-variant a100_5stack
--ramulator-config configs/ramulator/a100_hbm2e_5stack.yaml
```

The equivalent reusable override fragment is:

```bash
--accelsim-config-override-file configs/accelsim/a100_5stack_hbm2e.config
```

The H100 SXM-style HBM3 presets are:

```bash
--config-variant h100_1stack
--ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml
```

and:

```bash
--config-variant h100_full
--ramulator-config configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml
```

`h100_1stack` models one HBM3 stack as 16 x 64-bit channels, 26 SMs
(`132 / 5` rounded to the nearest integer), and 10 MiB L2. The equivalent
fragment is `configs/accelsim/h100_sxm_hbm3_1stack_16ch.config`.

For 5-stack/40-channel runs, use `-gpgpu_memory_partition_indexing 2` for the
balanced IPoly path. The local address decoder supports 40 channels by hashing
in the next power-of-two channel domain and folding the result back to 40.

Inline one-off overrides still work:

```bash
--config-overrides '-gpgpu_dram_return_queue_size 256'
```

Precedence for the generated run config is:

1. base `gpgpusim.config`
2. `--a100-l2-8mb` / `--l2-cache-config`
3. `--config-variant`
4. `--config-overrides`
5. each `--accelsim-config-override-file`
6. runner safety/runtime lines such as `-gpgpu_max_cycle`

If the same option appears more than once across those inputs, only the last
effective option line is kept in the generated file. This matches AccelSim's
parser behavior while avoiding stale base values beside architecture-specific
overrides.

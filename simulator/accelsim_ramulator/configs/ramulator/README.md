# Ramulator2 Configs

These YAML files are passed to the Ramulator2 bridge when the runner uses
`--backend ramulator2`.

## Files

| File | Purpose |
| --- | --- |
| `hbm4.yaml` | Existing 8-channel HBM4-style smoke config |
| `hbm4_external.yaml` | External-channel HBM4 variant kept for compatibility |
| `a100_hbm2e_80gb.yaml` | A100 80GB HBM2e-style full 40-channel config |
| `a100_hbm2e_1stack.yaml` | 8-channel A100 HBM2e-style smoke config for `a100_1stack` |

## Selection

Use `--ramulator-config`:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --ramulator-config configs/ramulator/a100_hbm2e_1stack.yaml
```

The runner copies the selected YAML into each run directory as
`ramulator2.yaml` and exports that copied path as `SGRAM_RAMULATOR_CONFIG`.
This keeps every result directory self-contained even if the source YAML changes
later.

## A100 HBM2e Notes

NVIDIA's A100 datasheet lists the A100 80GB as HBM2e with 2,039 GB/s bandwidth
for the SXM form factor:

```text
https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/a100/pdf/nvidia-a100-datasheet-us-nvidia-1758950-r4-web.pdf
```

Ramulator2 has an `HBM2` device model, but no separate `HBM2e` model in this
tree. The A100 configs therefore use `impl: HBM2` with:

- 16Gb/channel organization, represented by `density: 16384` and doubled row
  count over the built-in `HBM2_8Gb` preset.
- 128-bit channel width so each HBM2 burst maps to a 32B access atom.
- 3.2Gbps/pin transfer rate for the A100 80GB HBM2e bandwidth class. This is
  the nearest round data rate implied by 2,039 GB/s over a 5,120-bit aggregate
  A100 memory interface.
- `ExternalChannelRoBaRaCoCh`, so AccelSim memory partition ids select
  Ramulator2 channels directly.

Use `a100_hbm2e_80gb.yaml` with a 40-memory-partition AccelSim config. Use
`a100_hbm2e_1stack.yaml` with `--config-variant a100_1stack` for quick smoke
tests.

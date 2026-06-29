# Ramulator2 Configs

These YAML files are passed to the Ramulator2 bridge when the runner uses
`--backend ramulator2`.

For the end-to-end process of adding a new memory YAML, adding a new Ramulator2
DRAM model, pairing it with AccelSim address mapping, rebuilding, and validating
the result, see `../../docs/new_memory_integration_guide.md`.

For the clean AccelSim config files that should be paired with these YAMLs, see
`../CONFIG_MATRIX.md`.

## Files

| File | Purpose |
| --- | --- |
| `hbm4.yaml` | Existing 8-channel HBM4-style smoke config |
| `hbm4_external.yaml` | External-channel HBM4 variant kept for compatibility |
| `h100_sxm_hbm4_1stack_32ch.yaml` | H100 SXM-style 1-stack conventional HBM4 baseline with 32 pseudochannels |
| `h100_sxm_hbm4_5stack_160ch.yaml` | H100 SXM-style 5-stack conventional HBM4 baseline with 160 pseudochannels |
| `hbm3_sid_external_40ch.yaml` | HBM3 + SID 40-channel experimental config |
| `hbm3_sid_external_8ch.yaml` | HBM3 + SID 8-channel config for 1-stack comparisons |
| `h100_sxm_hbm3_sid_16ch.yaml` | H100 SXM-style 1-stack HBM3 config with 16 x 64-bit channels |
| `h100_sxm_hbm3_sid_80ch.yaml` | H100 SXM-style full HBM3 config with 80 x 64-bit channels |
| `gddr7_32gbps_16ch.yaml` | GDDR7 32Gbps/pin 16-channel config for bridge smoke and model bring-up |
| `rtx5090_gddr7_1of8_8ch.yaml` | 1/8 RTX 5090-style GDDR7 config with 8 x 8-bit channels, 4GiB, and 224 GB/s peak pin bandwidth |
| `rtx5090_gddr7_full_64ch.yaml` | RTX 5090-style GDDR7 config with 64 x 8-bit channels, 32GiB, and 1.792 TB/s peak pin bandwidth |
| `hbm4_external_40ch.yaml` | HBM4 40-channel config for full-stack comparisons |
| `a100_hbm2e_5stack.yaml` | A100 80GB HBM2e-style 5-stack / 40-channel config |
| `a100_hbm2e_80gb.yaml` | A100 80GB HBM2e-style full 40-channel config |
| `a100_hbm2e_1stack.yaml` | 8-channel A100 HBM2e-style smoke config for `a100_1stack` |

## HBM4 Baseline Notes

The HBM4 YAMLs use the conventional HBM4 baseline timing from the SPIRE-HBM
paper, not the SPIRE sub-pseudo-channel architecture. The baseline keeps normal
32-bit pseudochannels and models the paper's 8.0Gbps, 16Hi/4-SID HBM4 setup:

- `preset: HBM4_32Gb_16Hi`
- `timing.preset: HBM4_8000Mbps`
- 2 bank groups x 8 banks per SID
- open-row policy, all-bank refresh, FR-FCFS scheduling
- 64-entry read/write queues per pseudochannel

The SPIRE-specific sub-pCH data path, SID-bit repurposing, and doubled burst
length are intentionally not modeled by these baseline configs.

## GDDR7 Timing Presets

The `GDDR7` Ramulator2 model currently accepts these `timing.preset` names:

```text
GDDR7_28Gbps
GDDR7_30p3Gbps
GDDR7_32Gbps
GDDR7_35p4Gbps
GDDR7_37Gbps
GDDR7_38p8Gbps
GDDR7_40Gbps
GDDR7_42p5Gbps
GDDR7_48Gbps
```

The non-round bins are included as candidate silicon points from public ISSCC
GDDR7 papers. They keep the same JEDEC-derived row and refresh timing anchors
as the round bins; vendor-specific AC timings remain conservative defaults.

## RTX 5090 GDDR7 Notes

Use `rtx5090_gddr7_full_64ch.yaml` with
`canonical/rtx5090_gddr7_full_64ch.gpgpusim.config` for the full RTX 5090-style
memory system. It models the 512-bit bus as 64 independent 8-bit GDDR7
channels and uses the 28Gbps speed bin for 1.792 TB/s peak pin bandwidth.

Use `rtx5090_gddr7_1of8_8ch.yaml` with
`canonical/rtx5090_gddr7_1of8_8ch.gpgpusim.config` for quick 1/8-scale runs.
It keeps the same channel granularity and timing but reduces the memory system
to 8 channels, 4GiB, and 224 GB/s peak pin bandwidth.

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

Use `a100_hbm2e_5stack.yaml` with `--config-variant a100_5stack` for the normal
A100-style baseline. `a100_hbm2e_80gb.yaml` is kept as an equivalent 40-channel
name. Use `a100_hbm2e_1stack.yaml` with `--config-variant a100_1stack` only for
quick smoke tests.

The 5-stack AccelSim side should use the balanced IPoly path
(`-gpgpu_memory_partition_indexing 2`). The local address decoder supports
40-channel IPoly by hashing in the next power-of-two channel domain and folding
the result back to 40.

## Current Smoke-Validated Pairings

Use these pairings when you want a config whose external-channel address mapping
has been checked against the current bridge build:

| Ramulator2 config | Legacy runner variant | Preferred canonical AccelSim config | Channels |
| --- | --- | --- | ---: |
| `a100_hbm2e_1stack.yaml` | `a100_1stack` | `canonical/a100_hbm2e_1stack_8ch.gpgpusim.config` | 8 |
| `a100_hbm2e_5stack.yaml` | `a100_5stack` | `canonical/a100_hbm2e_full_40ch.gpgpusim.config` | 40 |
| `a100_hbm2e_80gb.yaml` | `a100_full` | `canonical/a100_hbm2e_full_40ch.gpgpusim.config` | 40 |
| `hbm3_sid_external_8ch.yaml` | `a100_1stack` | `canonical/a100_hbm2e_1stack_8ch.gpgpusim.config` | 8 |
| `hbm3_sid_external_40ch.yaml` | `a100_5stack` | `canonical/a100_hbm2e_full_40ch.gpgpusim.config` | 40 |
| `h100_sxm_hbm3_sid_16ch.yaml` | `h100_1stack` | `canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config` | 16 |
| `h100_sxm_hbm3_sid_80ch.yaml` | `h100_full` | `canonical/h100_sxm_hbm3sid_full_80ch.gpgpusim.config` | 80 |
| `h100_sxm_hbm4_1stack_32ch.yaml` | `h100_1stack` | `canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config` | 32 |
| `h100_sxm_hbm4_5stack_160ch.yaml` | `h100_full` | `canonical/h100_sxm_hbm3sid_full_80ch.gpgpusim.config` | 160 |
| `gddr7_32gbps_16ch.yaml` | `h100_1stack` | `canonical/h100_sxm_hbm3sid_1stack_16ch.gpgpusim.config` | 16 |
| `rtx5090_gddr7_1of8_8ch.yaml` | `canonical` | `canonical/rtx5090_gddr7_1of8_8ch.gpgpusim.config` | 8 |
| `rtx5090_gddr7_full_64ch.yaml` | `canonical` | `canonical/rtx5090_gddr7_full_64ch.gpgpusim.config` | 64 |
| `hbm4.yaml` | `a100_1stack` | `canonical/a100_hbm2e_1stack_8ch.gpgpusim.config` | 8 |
| `hbm4_external.yaml` | `a100_1stack` | `canonical/a100_hbm2e_1stack_8ch.gpgpusim.config` | 8 |
| `hbm4_external_40ch.yaml` | `a100_5stack` | `canonical/a100_hbm2e_full_40ch.gpgpusim.config` | 40 |

## HBM3 SID Notes

The upstream HBM3 model in this tree does not expose an SID hierarchy. The
`HBM3SID` model adds:

```text
channel -> pseudochannel -> sid -> bankgroup -> bank -> row -> column
```

`hbm3_sid_external_40ch.yaml` uses `impl: HBM3SID` with four SIDs per
pseudochannel and the same external-channel address mapper used by the A100
HBM2e configs. Use it with `--config-variant a100_5stack` when you want the
AccelSim side to expose 40 memory partitions and Ramulator2 to expose 40
source-id-selected channels.

Both HBM3 SID YAMLs use `HBM3SID_6.4Gbps`, matching the JEDEC HBM3 6.4Gbps/pin
speed bin. In this model `rate` is the per-pin data rate. HBM3 uses WDQS/RDQS
at twice CK and DQ is DDR on those strobes, so the Ramulator2 command clock is:

```text
fCK = rate / 4 = 1600 MHz
tCK = 0.625 ns
```

With the A100 AccelSim DRAM clock at 1512MHz, `SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=auto`
therefore resolves to about `1.0582` Ramulator ticks per AccelSim DRAM tick.

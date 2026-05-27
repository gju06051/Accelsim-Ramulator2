# Canonical AccelSim Configs

These files are generated clean `gpgpusim.config` inputs for the AccelSim +
Ramulator2 matrix runner.  They collapse the stock SM80 A100 base config and the
architecture-specific overrides into one readable file.

Refresh them with:

```bash
simulator/accelsim_ramulator/scripts/generate_canonical_accelsim_configs.py
```

Use them with:

```bash
--gpgpusim-config simulator/accelsim_ramulator/configs/accelsim/canonical/<file>
--config-variant canonical
```

`--config-variant canonical` is intentionally empty. It prevents the runner from
adding another A100/H100 architecture preset on top of the already-clean config,
while still allowing runtime lines such as `-gpgpu_max_cycle`,
`-gpgpu_host_timing`, and `-liveness_message_freq` to be appended per run.

See `../../CONFIG_MATRIX.md` for the AccelSim/Ramulator2 pairing table.

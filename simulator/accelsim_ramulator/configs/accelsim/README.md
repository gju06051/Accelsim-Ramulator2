# Accel-Sim Config Overrides

Place AccelSim/GPGPU-Sim config fragments here for experiments using the
Ramulator2 backend.

The runner always creates a per-run `gpgpusim.config` by copying a base config
and appending overrides. Select the base config with:

```bash
--gpgpusim-config /path/to/gpgpusim.config
```

Append one or more fragments with:

```bash
--accelsim-config-override-file configs/accelsim/a100_1stack_8mb_l2.config
```

Inline one-off overrides still work:

```bash
--config-overrides '-gpgpu_memory_partition_indexing 2;-gpgpu_dram_return_queue_size 256'
```

Order inside the generated run config is:

1. copied base `gpgpusim.config`
2. `--a100-l2-8mb` / `--l2-cache-config`
3. `--config-variant`
4. `--config-overrides`
5. each `--accelsim-config-override-file`
6. runner safety/runtime lines such as `-gpgpu_max_cycle`

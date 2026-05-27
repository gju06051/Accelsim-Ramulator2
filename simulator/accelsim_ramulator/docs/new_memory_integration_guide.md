# Adding a New Memory Configuration or Model

This guide explains how to attach a new memory system to the AccelSim +
Ramulator2 integration.  It is written so the same workflow can be reused in a
different repository layout, as long as that project keeps the same three
logical components:

```text
<workspace>/
  simulator/
    gpgpu-sim_distribution/   # AccelSim/GPGPU-Sim tree
    ramulator2/               # Ramulator2 tree
    accelsim_ramulator/       # integration layer
```

If your checkout uses another layout, set:

```bash
export SGRAM_WORKSPACE_ROOT=/path/to/workspace
export SGRAM_GPGPU_ROOT=/path/to/gpgpu-sim_distribution
export SGRAM_RAMULATOR2_ROOT=/path/to/ramulator2
export SGRAM_GPGPU_BUILD=/path/to/gpgpu-sim_distribution/build/sgram_fixed
```

There are two different tasks:

1. Add only a new Ramulator2 YAML and AccelSim config pairing.
2. Add a new Ramulator2 DRAM implementation in C++.

Use the first path when an existing Ramulator2 model can already represent the
new memory hierarchy and timing.  Use the second path only when the memory has
new command, hierarchy, timing, row-buffer, refresh, or address behavior that
cannot be expressed with an existing model.

## Key Invariant

AccelSim and Ramulator2 must agree on the external memory topology.

The most important fields are:

| Concept | AccelSim side | Ramulator2 side |
| --- | --- | --- |
| External memory channel count | `-gpgpu_n_mem` | `MemorySystem.DRAM.org.channel` |
| Channel selection bit | `-gpgpu_mem_addr_mapping dramid@...` | `AddrMapper.channel_start_bit` |
| L2 slices under each memory channel | `-gpgpu_n_sub_partition_per_mchannel` | not modeled directly by Ramulator2 |
| Queue depth | `-gpgpu_frfcfs_dram_sched_queue_size` and `-gpgpu_dram_partition_queues` | `Controller.read_buffer_size`, `Controller.write_buffer_size` |
| DRAM command clock | `-gpgpu_clock_domains` DRAM domain | `timing.tCK_ps`, runner auto tick ratio |
| Internal memory hierarchy | `-gpgpu_mem_addr_mapping` lower bits for local decoder consistency | DRAM model levels and address mapper order |

This repository normally uses `ExternalChannelRoBaRaCoCh`.  In that mode,
AccelSim's memory partition id is passed as the Ramulator2 request source id and
selects the external Ramulator2 channel directly.  The remaining low address
bits are decoded into row, bank, and column fields by the Ramulator2 mapper.

## Path A: Add a New YAML Pairing

Use this path when the memory can be represented by an existing Ramulator2
implementation such as `HBM2`, `HBM3SID`, or `HBM4`.

### 1. Create the Ramulator2 YAML

Put the YAML under:

```text
simulator/accelsim_ramulator/configs/ramulator/
```

Example skeleton:

```yaml
Frontend:
  impl: GEM5
  clock_ratio: 8

MemorySystem:
  impl: GenericDRAM
  clock_ratio: 3

  DRAM:
    impl: HBM3SID
    org:
      preset: HBM3SID_8Gb_2SID_16Gb_8Hi
      channel_width: 32
      channel: 16
    timing:
      preset: HBM3SID_SAMSUNG_8Gbps

  Controller:
    impl: Generic
    read_buffer_size: 64
    write_buffer_size: 64
    Scheduler:
      impl: FRFCFS
    RefreshManager:
      impl: AllBank
    RowPolicy:
      impl: OpenRowPolicy
    plugins:

  AddrMapper:
    impl: ExternalChannelRoBaRaCoCh
    channel_start_bit: 8
```

Checklist:

- `DRAM.impl` must match a registered Ramulator2 implementation name.
- `org.preset` and `timing.preset` must exist in that model.
- `org.channel` must match the AccelSim `-gpgpu_n_mem` for the paired config.
- `channel_width` should be the data width represented by one Ramulator2
  access channel.  For the H100 HBM3 SID configs in this tree, one physical
  64-bit channel is represented as two 32-bit pseudochannels, so the YAML uses
  `channel_width: 32`.
- `read_buffer_size` and `write_buffer_size` should usually match the intended
  AccelSim scheduler queue depth.  The runner can override these with
  `--queue-limits`.
- `channel_start_bit` should match the bit position used by AccelSim's
  `dramid@...` address mapping.

Good examples:

```text
configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml
configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml
configs/ramulator/a100_hbm2e_5stack.yaml
```

### 2. Create the AccelSim Config Fragment

Put reusable AccelSim fragments under:

```text
simulator/accelsim_ramulator/configs/accelsim/
```

Example skeleton:

```text
-gpgpu_n_clusters 26
-gpgpu_clock_domains 1980:1980:1980:2000

-gpgpu_n_mem 16
-gpgpu_n_sub_partition_per_mchannel 2

-gpgpu_dram_partition_queues 64:64:64:64
-gpgpu_frfcfs_dram_sched_queue_size 64
-gpgpu_dram_return_queue_size 192

-gpgpu_cache:dl2 S:128:128:20,L:B:m:L:X,A:192:4,32:0,32

-gpgpu_memory_partition_indexing 2
-gpgpu_mem_address_mask 1
-gpgpu_mem_addr_mapping dramid@8;00000000.00000000.00000000.00000000.00RRRRRR.RRRRRRRR.BBBBBBCC.CCCSSSSS

-gpgpu_dram_timing_opt nbk=64:CCD=2:RRD=5:RCD=30:RAS=66:RP=30:RC=96:CL=29:WL=13:CDLR=9:WR=13:nbkgrp=4:CCDL=4:RTPL=5
```

Checklist:

- `-gpgpu_n_mem` must match the Ramulator2 YAML channel count.
- `-gpgpu_n_sub_partition_per_mchannel` determines the number of L2
  subpartitions behind each memory channel.  The total L2 subpartition count is
  `n_mem * n_sub_partition_per_mchannel`.
- `-gpgpu_cache:dl2` should be sized for the intended total L2 capacity and
  subpartition count.
- `-gpgpu_clock_domains` DRAM frequency should be compatible with the selected
  Ramulator2 timing preset.  The runner can use
  `--ramulator-ticks-per-dram-cycle auto` to derive the tick ratio from
  Ramulator2 `tCK_ps`.
- `-gpgpu_mem_addr_mapping` must reserve the external channel digit at the same
  bit position used by `AddrMapper.channel_start_bit`.
- Keep `-gpgpu_memory_partition_indexing 2` for the balanced IPoly path unless
  intentionally testing another partition indexer.  The local address decoder
  supports non-power-of-two channel counts by hashing in the next power-of-two
  domain and folding back to the configured partition count.

Good examples:

```text
configs/accelsim/h100_sxm_hbm3_1stack_16ch.config
configs/accelsim/h100_sxm_hbm3_80ch.config
configs/accelsim/a100_5stack_hbm2e.config
```

### 3. Run a Smoke Test

Use the system-check microbenchmarks first:

```bash
cd simulator/accelsim_ramulator

./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_system_check \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/new_memory.yaml \
  --accelsim-config-override-file configs/accelsim/new_memory.config \
  --latencies 0 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --gpgpusim-host-timing on \
  --max-cycle 50000 \
  --jobs 4 \
  --out-dir results/new_memory_system_smoke
```

For one or two application rows:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset accelsim_ramulator_main \
  --benchmarks graphbig_bfs_data_warp,polybench_atax \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/new_memory.yaml \
  --accelsim-config-override-file configs/accelsim/new_memory.config \
  --latencies 0 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --max-cycle 50000 \
  --jobs 2 \
  --out-dir results/new_memory_app_smoke
```

Inspect `summary.csv` for:

- `status` is `OK` or bounded `MAX_CYCLE_OK` for smoke tests.
- `ramulator_stats_present=1`.
- `backend_active_partitions` equals the expected channel count when the
  benchmark has enough memory traffic.
- `backend_total_accepted_reads` and `backend_total_completed_reads` are close
  for completed unbounded runs.  Bounded `MAX_CYCLE_OK` runs may leave
  outstanding reads.
- `backend_global_accepted_writes` and `backend_global_completed_writes` are
  interpreted carefully.  Writes are accepted by Ramulator2 and returned to
  AccelSim immediately in this bridge path.
- `backend_partition_cv` and `backend_max_partition_share` are not extreme for
  balanced streaming workloads.
- `backend_total_rejected`, `backend_total_rejected_inflight`, and
  `backend_total_rejected_ramulator` are reasonable for the intended queue
  pressure.

## Path B: Add a New Ramulator2 DRAM Model

Use this path when an existing model cannot express the target memory.  For
example, HBM3 with an explicit SID hierarchy required a new model in this tree.

### 1. Add the Implementation File

Create:

```text
simulator/ramulator2/src/dram/impl/NewMemory.cpp
```

Start from the closest existing model:

```text
simulator/ramulator2/src/dram/impl/HBM2.cpp
simulator/ramulator2/src/dram/impl/HBM3.cpp
simulator/ramulator2/src/dram/impl/HBM3SID.cpp
simulator/ramulator2/src/dram/impl/HBM4.cpp
```

The implementation must register itself:

```cpp
class NewMemory : public IDRAM, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IDRAM, NewMemory, "NewMemory", "New Memory Device Model")
  ...
};
```

### 2. Define Organization Presets

`org_presets` describes the hierarchy size and DQ width.  For example:

```cpp
inline static const std::map<std::string, Organization> org_presets = {
  // name        density  DQ  Ch Pch SID Bg Ba Row    Col
  {"New_8Gb",   {8<<10,  32, {1, 2,  2, 4, 4, 1<<14, 1<<8}}},
};
```

The hierarchy vector must match `m_levels`.

Common pitfalls:

- Confusing physical channel width with pseudochannel DQ width.
- Using column count values that imply the wrong row-buffer page size.
- Forgetting that density is interpreted according to the model's organization
  convention, not necessarily the full package capacity.

### 3. Define Timing Presets

`timing_presets` should include the data rate, command timing in cycles, and
`tCK_ps`.

Example shape from `HBM3SID`:

```cpp
inline static const std::map<std::string, std::vector<int>> timing_presets = {
  // name   rate nBL nCL nRCDRD ... nCCDS nCCDR nCCDL ... tCK_ps
  {"New_8Gbps", {8000, 4, 29, 30, /* ... */ 2, 3, 4, /* ... */ 500}},
};
```

Timing values must be internally consistent:

- If a datasheet gives nanoseconds, convert to cycles with
  `ceil(timing_ns / tCK_ns)`.
- Keep separate short, long, and special crossing timing when the memory has
  topology-sensitive constraints such as same-bankgroup, different-bankgroup,
  or SID-crossing delays.
- Refresh timings and refresh intervals should be scaled to the selected
  command clock.

### 4. Define Levels, Commands, Requests, and Timing Rules

The model must define:

- `m_levels`
- `m_commands`
- `m_command_scopes`
- `m_command_meta`
- `m_requests`
- `m_request_translations`
- `m_timings`
- initial node states
- prerequisite commands
- row-hit and row-open checks
- action functions
- timing constraint table

If the new model is a small variation of HBM3/HBM4, copy the closest model and
change only the hierarchy and timing rules that differ.

### 5. Register the File in CMake

Add the new file to:

```text
simulator/ramulator2/src/dram/CMakeLists.txt
```

Example:

```cmake
target_sources(
  ramulator-dram PRIVATE
  ...
  impl/NewMemory.cpp
)
```

### 6. Build Ramulator2 and the Bridge

Build Ramulator2 first:

```bash
cd simulator/ramulator2
cmake --build build -j32
```

Then rebuild the bridge:

```bash
cd simulator/accelsim_ramulator
./scripts/build_ramulator2_bridge.sh
```

If the AccelSim overlay changed, rebuild AccelSim/GPGPU-Sim too:

```bash
cd simulator/accelsim_ramulator
./scripts/apply_overlay.sh
cmake --build ../gpgpu-sim_distribution/build/sgram_fixed -j32
```

## When to Add a New Address Mapper

Most AccelSim pairings should use `ExternalChannelRoBaRaCoCh`, because it lets
AccelSim choose the external memory channel and lets Ramulator2 decode the rest.

Add or modify a mapper under:

```text
simulator/ramulator2/src/addr_mapper/
```

only when:

- the new memory needs a different order of row, bank, SID, pseudochannel, or
  column bits;
- the external channel should not be selected directly from the AccelSim memory
  partition id;
- a new XOR/hash/swizzle function must be applied below the channel level.

If a new mapper is added, update its CMake registration and use it from the YAML:

```yaml
AddrMapper:
  impl: NewMapper
  channel_start_bit: 8
```

## Runner Integration

For one-off experiments, pass the YAML and AccelSim fragment directly:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --ramulator-config configs/ramulator/new_memory.yaml \
  --accelsim-config-override-file configs/accelsim/new_memory.config \
  ...
```

For a frequently reused geometry, add a config variant in:

```text
simulator/accelsim_ramulator/scripts/run_fixed_backend_matrix.py
```

Add a constant list of overrides and register it in `CONFIG_VARIANTS`.

The runner creates per-run effective files:

```text
<out-dir>/<variant>/<benchmark>/ramulator2_lat<lat>_q<queue>/
  gpgpusim.config
  ramulator2.yaml
  summary.csv
```

These copied files are the effective configuration used by that run.

## Validation Ladder

Use a staged validation flow:

1. Bridge-only smoke:

   ```bash
   build/ramulator2_bridge/sgram_ramulator2_bridge_smoke configs/ramulator/new_memory.yaml
   ```

2. System-check microbenchmarks:

   ```bash
   ./scripts/run_fixed_backend_matrix.py \
     --backend ramulator2 \
     --preset accelsim_ramulator_system_check \
     --ramulator-config configs/ramulator/new_memory.yaml \
     --accelsim-config-override-file configs/accelsim/new_memory.config \
     --max-cycle 50000 \
     --jobs 4 \
     --out-dir results/new_memory_system_smoke
   ```

3. Short application smoke:

   ```bash
   ./scripts/run_fixed_backend_matrix.py \
     --backend ramulator2 \
     --preset accelsim_ramulator_main \
     --benchmarks graphbig_bfs_data_warp,polybench_atax \
     --ramulator-config configs/ramulator/new_memory.yaml \
     --accelsim-config-override-file configs/accelsim/new_memory.config \
     --max-cycle 50000 \
     --jobs 2 \
     --out-dir results/new_memory_app_smoke
   ```

4. Unbounded representative run for rows that are known to complete.

5. Queue and channel sensitivity checks if the memory model changes queueing,
   bank-level parallelism, or address distribution.

## Common Failure Modes

| Symptom | Likely cause |
| --- | --- |
| `NO_BACKEND` | Benchmark did not enter the AccelSim/Ramulator2 path, often because it must be trace replayed. |
| `BACKEND_STARTED_ERROR` | Backend started but the application or simulator exited abnormally. Check stdout/stderr. |
| No Ramulator stats in `summary.csv` | `ramulator2.yaml` path, bridge library, or finalize/stat output path is wrong. |
| Active partitions lower than expected | Address mapping or benchmark traffic does not touch all channels. |
| Extreme partition imbalance | Bad `dramid@...`, wrong mapper order, or an address swizzle/hash issue. |
| Many rejected requests | Queue sizes are too small for the workload, inflight limit is too low, or the memory backend is saturated. |
| `accepted_reads != completed_reads` | Normal for bounded `MAX_CYCLE_OK` runs; suspicious for completed unbounded `OK` runs. |
| Very high L2 miss or zero DRAM requests unexpectedly | L2 config or address mapping may not match the intended channel/subpartition topology. |

## Documentation Checklist

When a new memory configuration is promoted, update:

- `configs/ramulator/README.md` with the new YAML and validated pairing.
- `configs/accelsim/README.md` with the AccelSim fragment or variant.
- `docs/project_worklog.md` if the configuration becomes part of the project
  baseline.
- benchmark result notes if the new memory changes interpretation of bandwidth,
  latency, queue pressure, or partition balance.

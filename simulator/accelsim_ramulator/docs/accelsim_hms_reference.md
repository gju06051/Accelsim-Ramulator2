# AccelSim-HMS Reference Notes

Reference repositories:

- `PSAL-POSTECH/accelsim_HMS`
- URL: `https://github.com/PSAL-POSTECH/accelsim_HMS`
- Inspected commit: `71f72616b60987ef5f934b36cd7ae866eea856aa`
- Actual GPGPU-Sim changes are pulled by its setup script from
  `PSAL-POSTECH/gpgpu-sim_HMS`
- URL: `https://github.com/PSAL-POSTECH/gpgpu-sim_HMS`
- Inspected commit: `b530a82b9a674ed751e3b031b823a44282e91e7c`

The HMS code integrates Accel-Sim/GPGPU-Sim with a Ramulator-derived memory
model for HBM/PCM/HMS and adds UVMSmart/GMMU/page migration behavior. The UVM
features are outside this integration baseline path, but the memory-interface pattern
is useful.

## How HMS Connects Ramulator

HMS adds two config knobs:

```text
-use_ramulator 1
-ramulator_memory_type HBM|PCM|HMS
```

When enabled, `memory_partition_unit` constructs a `Ramulator` object instead of
native `dram_t`.

```text
memory_partition_unit
  -> m_dram = new Ramulator(...)
```

Their `Ramulator` class inherits from `dram_t` and overrides the same interface
that the native DRAM model uses:

```text
full()
push(mem_fetch*)
cycle()
return_queue_top()
return_queue_pop()
print()
```

Request path:

```text
L2_dram_queue
  -> dram_latency_queue
  -> Ramulator::push(mem_fetch*)
  -> from_gpgpusim FIFO
  -> ramulator::Request(addr, type, callback, source_id, mem_fetch*)
  -> memory->send(req)
```

Completion path:

```text
Ramulator callback
  -> r_rwq.push(req.mf)
  -> Ramulator::cycle()
  -> set_reply()/set_done()
  -> r_returnq
  -> memory_partition_unit::dram_cycle()
  -> dram_L2_queue
```

Clocking:

```text
Ramulator::cycle()
  -> memory->tick()
```

Because HMS has one Ramulator instance per memory partition, each partition
ticks its own memory object once per Accel-Sim DRAM clock pass.

## Useful Lessons for AccelSim + Ramulator2

The pieces worth carrying into our integration are:

1. Preserve Accel-Sim memory latency stats.

   HMS calls `m_stats->memlatstat_dram_access(mf)` in `Ramulator::push()`, just
   like native `dram_t::push()`. Our `sgram_backend_t::push()` now does this as
   well so external backend runs do not silently skip that accounting path.

2. Keep Ramulator request identity attached to `mem_fetch*`.

   HMS passes `mem_fetch*` directly in the Ramulator request object. Our
   Ramulator2 C ABI bridge already mirrors this by passing `mem_fetch*` as the
   callback payload.

3. Treat Ramulator clocking as an explicit integration choice.

   HMS ticks once per partition because each partition owns a separate memory
   object. Our design uses one shared Ramulator2 memory system with multiple
   channels, so only partition 0 ticks it. The normal path now uses
   `SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=auto`, which derives the ratio from
   AccelSim's DRAM clock and Ramulator2 `tCK`; numeric values remain available
   for sensitivity experiments.

4. Keep policy-heavy memory-management code out of the baseline bridge.

   HMS includes page-table, PCIe validation/invalidation, migration, tag-cache,
   and UVM policy machinery. Those are valuable for HMS but would blur the
   baseline bridge. We should not import them.

## Reflected Changes

Applied to our bridge:

```text
sgram_backend_t::push()
  -> m_stats->memlatstat_dram_access(data)

SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=auto
SGRAM_ACCELSIM_DRAM_FREQ_MHZ=<MHz>
  -> partition 0 ticks the shared Ramulator2 memory system with a fractional
     ratio derived from Ramulator2 tCK and the Accel-Sim DRAM clock
```

Applied to the runner:

```text
--ramulator-inflight-read-limit <N>
--ramulator-ticks-per-dram-cycle auto
```

## Not Imported

- `Ramulator : public dram_t` inheritance structure.

  Our overlay deliberately keeps the simulator submodules cleaner by storing the
  integration backend in this repository and applying it as an overlay.

- UVMSmart/GMMU/PCIe/page migration queues.

  These are not needed for HBM4 baseline or additional timing experiments.

- Per-partition independent Ramulator memory objects.

  Our HBM4 baseline uses one Ramulator2 `GenericDRAM` system with multiple
  channels, so per-partition memory systems would duplicate timing state rather
  than model a single HBM stack/channel system.

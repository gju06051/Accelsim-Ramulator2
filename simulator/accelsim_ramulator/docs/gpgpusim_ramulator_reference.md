# GPGPUSim-Ramulator Reference Notes

Reference repository:

- `CMU-SAFARI/GPGPUSim-Ramulator`
- URL: `https://github.com/CMU-SAFARI/GPGPUSim-Ramulator`
- Inspected commit: `0f20fae`
- Stack: GPGPU-Sim 3.2.2 + Ramulator 1

Our target stack is different:

- Accel-Sim / GPGPU-Sim 4.x-style tree
- Ramulator2
- SG-HBM / HBM4 experiments

So the old code should be treated as an integration pattern, not as code to port
line-for-line.

## What the Old Integration Does

The old repository replaces the native GPGPU-Sim DRAM timing path with a
Ramulator wrapper.

Key files:

- `src/ramulator/Ramulator.h`
- `src/ramulator/Ramulator.cc`
- `src/gpgpu-sim/gpu-sim.cc`
- `src/gpgpu-sim/gpu-sim.h`
- `src/gpgpu-sim/l2cache.cc`
- `src/gpgpu-sim/l2cache.h`

The important flow is:

```text
L2_dram_queue
  -> memory_partition_unit::dram_cycle()
  -> Ramulator::FromGpusimDram_push(partition_id, mem_fetch*)
  -> Ramulator Request(addr, type, callback, source_id)
  -> Ramulator::tick()
  -> readComplete/writeComplete callback
  -> per-partition completed queue
  -> dram_L2_queue
```

The wrapper keeps several queues:

```text
from_gpgpusim[partition]  pending requests accepted from GPGPU-Sim
from_ramulator[partition] completed requests returned by Ramulator callbacks
to_gpgpusim[partition]   completed requests ready for GPGPU-Sim return queue
pending[partition]       outstanding requests occupying scheduling capacity
returned[partition]      completed requests occupying return capacity
```

The old integration adds two config knobs:

```text
-gpgpu_ramulator_config
-gpgpu_ramulator_cache_line_size
```

It also ticks Ramulator at the DRAM clock point inside `gpgpu_sim::cycle()`,
before each memory partition's `dram_cycle()`.

## What Carries Over

The core idea carries over cleanly:

1. A `mem_fetch*` remains the identity of an Accel-Sim memory request.
2. The bridge sends only address, request type, source/partition ID, and a
   completion callback into the memory simulator.
3. A completion callback does not directly push into Accel-Sim queues. It only
   stages the completed `mem_fetch*` into a bridge-owned queue.
4. The Accel-Sim memory partition drains that bridge completion queue when its
   `dram_L2_queue` has capacity.
5. Backpressure must model both request-side capacity and return-side capacity.

This matches our existing `sgram_backend_t` hook:

```text
memory_partition_unit::dram_cycle()
  -> external_memory_backend_cycle()
  -> sgram_backend_t::push(mem_fetch*)
  -> sgram_backend_t::cycle()
  -> sgram_backend_t::return_queue_top/pop()
```

So we should extend `sgram_backend_t` rather than reintroducing the old
Ramulator-1-specific `l2cache.cc` edits.

## What Does Not Carry Over

The Ramulator API is different.

Old Ramulator 1 style:

```cpp
ramulator::Request req(addr, Request::Type::READ, callback, source_id);
wrapper->send(req);
wrapper->tick();
```

Ramulator2 style:

```cpp
auto frontend = Ramulator::Factory::create_frontend(config);
auto memory_system = Ramulator::Factory::create_memory_system(config);
frontend->connect_memory_system(memory_system);
memory_system->connect_frontend(frontend);

frontend->receive_external_requests(type, addr, source_id, callback);
memory_system->tick();
```

Ramulator2 already has an external wrapper frontend:

```text
src/frontend/impl/external_wrapper/gem5_frontend.cpp
```

This frontend forwards external requests into `IMemorySystem::send()` using:

```cpp
Request(addr, req_type_id, source_id, callback)
```

That is the right Ramulator2 hook for our bridge.

The current implementation uses a C ABI shared library around the same
Ramulator2 objects. The Accel-Sim-side backend loads it with `dlopen()` so the
GPGPU-Sim 4.x build does not directly depend on Ramulator2's C++20 build.

## Proposed Bridge Shape

Keep a per-memory-partition `sgram_backend_t` in Accel-Sim, but give all
partitions access to a shared Ramulator2 simulation object.

```text
sgram_backend_t partition 0
sgram_backend_t partition 1
...
sgram_backend_t partition N
        |
        v
shared ramulator2_system_t
        |
        v
Ramulator2 Frontend=GEM5 + MemorySystem=GenericDRAM
```

Request path:

```text
sgram_backend_t::push(mem_fetch*)
  -> sgram_backend_t pending queue
  -> sgram_ramulator2_send(addr, type, source_id=0, payload=mem_fetch*)
  -> Ramulator2 IMemorySystem::send(Request)
```

Completion path:

```text
Ramulator2 callback(Request&)
  -> req.m_payload or side table recovers mem_fetch*
  -> completed[partition_id].push_back(mem_fetch*)
  -> sgram_backend_t::return_queue_top/pop()
```

Clocking:

```text
partition-0 sgram_backend_t::cycle()
  -> shared sgram_ramulator2_tick()
```

The shared object prevents Ramulator2 from being ticked once per memory
partition. The old repo ticks Ramulator globally in `gpgpu_sim::cycle()`, while
our less intrusive overlay ticks from partition 0 during each Accel-Sim DRAM
clock pass.

## Initial Runtime Knobs

Use environment variables first, then graduate stable knobs into
`gpgpusim.config`.

```text
SGRAM_BACKEND=ramulator2
SGRAM_RAMULATOR_LIB=/path/to/libsgram_ramulator2_bridge.so
SGRAM_RAMULATOR_CONFIG=/path/to/hbm4.yaml
SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT=32
SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=1
SGRAM_QUEUE_LIMIT=<entries>
```

For HBM4 baseline:

```text
logical row size = 1KB
access atom      = 32B
tFAW             = 16ns
tRRD             = 2ns
ACTs/tFAW        = 8
```

## Implementation Order

1. Add a Ramulator2 bridge facade under `bridge/`.
2. Make `sgram_backend_t` dispatch on `SGRAM_BACKEND=fixed|ramulator2`.
3. Instantiate Ramulator2 from `SGRAM_RAMULATOR_CONFIG`.
4. Send read requests with callbacks and return writes once Ramulator2 accepts
   them.
5. Return completed `mem_fetch*` through the existing external backend return
   path.
6. Add bridge stats:
   - accepted requests
   - rejected requests
   - outstanding requests
   - completed reads/writes
   - return queue stalls
   - Ramulator2 ticks
7. Validate with the existing fixed-backend benchmark matrix, then switch to
   the Ramulator2 backend.

## Caution Points

- Do not tick Ramulator2 once per partition per GPU cycle.
- Do not let callback code directly mutate Accel-Sim subpartition queues.
- Writes and writebacks do not receive callbacks in Ramulator2's generic
  controller, matching the old integration's comment that write callbacks were
  never called. The scaffold therefore returns writes to Accel-Sim after
  Ramulator2 accepts them.
- `mem_fetch::get_sid()` in the old repo was used as Ramulator source ID. For
  SG-HBM we should not reuse that meaning blindly because `SID` will later mean
  HBM stack/slice identity. Use partition/subpartition or shader/core source ID
  explicitly.
- Ramulator2 request payload support (`Request::m_payload`) can carry
  `mem_fetch*`, but a side table keyed by address plus sequence number is safer
  if payload ownership becomes ambiguous.
- Ramulator2's generic controller increments some per-channel request counters
  before enqueue success. Avoid tight rejected-retry loops in the bridge, or
  those internal counters will be inflated. The current scaffold uses
  `SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT` as a conservative guard.

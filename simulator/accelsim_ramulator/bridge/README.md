# Bridge Code

This directory will hold the Accel-Sim to Ramulator bridge.

Expected responsibilities:

- Convert Accel-Sim `mem_fetch` requests into Ramulator requests.
- Maintain request IDs and completion callbacks.
- Tick Ramulator at the configured memory-clock ratio.
- Return completed requests to the Accel-Sim memory partition path.
- Collect bridge-level statistics for sanity checks.

`sgram_backend_t` currently supports a fixed-latency backend and a Ramulator2
backend.

```text
SGRAM_BACKEND=fixed
SGRAM_FIXED_LATENCY=<cycles>
SGRAM_QUEUE_LIMIT=<entries>
```

Ramulator2 mode:

```text
SGRAM_BACKEND=ramulator2
SGRAM_RAMULATOR_LIB=/path/to/libsgram_ramulator2_bridge.so
SGRAM_RAMULATOR_CONFIG=/path/to/a100_hbm2e_1stack.yaml
SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT=<entries>
SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=<ticks>
SGRAM_QUEUE_LIMIT=<entries>
```

`ramulator2_c_api.cc` is built as `libsgram_ramulator2_bridge.so` and loaded
with `dlopen()` by `sgram_backend_t`.

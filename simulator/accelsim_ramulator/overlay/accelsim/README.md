# Accel-Sim Overlay

This directory stores patches or overlay files needed to let Accel-Sim call an
external memory backend.

The baseline simulator submodule should remain clean. Scripts in `../scripts`
will apply or remove these changes in a controlled way for experiment builds.

Likely touch points:

- `src/gpgpu-sim/l2cache.h`
- `src/gpgpu-sim/l2cache.cc`
- `src/gpgpu-sim/dram.h`
- `src/gpgpu-sim/dram.cc`
- build files for linking the bridge

Current overlay:

```text
accelsim_external_backend.patch
```

It adds a `sgram_backend_t` pointer to `memory_partition_unit` and redirects
`dram_cycle()` to the external backend when `SGRAM_BACKEND=fixed` is set.

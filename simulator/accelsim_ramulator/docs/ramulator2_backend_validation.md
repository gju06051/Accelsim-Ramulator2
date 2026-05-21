# Ramulator2 Backend Validation

Date: 2026-05-19

This note records the first Accel-Sim/GPGPU-Sim4 + Ramulator2 backend smoke
validation for the AccelSim + Ramulator2 integration repository.

## Build

Ramulator2 C ABI bridge:

```bash
./scripts/build_ramulator2_bridge.sh
```

Accel-Sim overlay build:

```bash
./scripts/apply_overlay.sh
cmake --build ../gpgpu-sim_distribution/build/sgram_fixed -j32
```

Both builds completed successfully.

## Configuration

Common runtime configuration:

```text
SGRAM_BACKEND=ramulator2
SGRAM_RAMULATOR_CONFIG=configs/ramulator/hbm4.yaml
SGRAM_QUEUE_LIMIT=32
SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT=5120
SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE=auto
```

Accel-Sim configuration:

```text
SM80_A100 base config
gpgpu_n_clusters = 22
gpgpu_n_mem = 8
L2 cache reduced to about 8 MiB
```

Ramulator2 HBM4 configuration:

```text
Frontend: GEM5
MemorySystem: GenericDRAM
DRAM: HBM4
pseudo-channel width: 32 bits
channels: 8
tCK: 0.5 ns
```

## Runs

Core preset:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset core \
  --latencies 0 \
  --queue-limits 32 \
  --config-variant a100_1stack \
  --a100-l2-8mb \
  --max-cycle 2000 \
  --timeout 120 \
  --jobs 8 \
  --out-dir results/ramulator2_backend_core_a100_1stack_l2_8mb_j8_mc2k_v1
```

Result:

```text
22 / 22 MAX_CYCLE_OK
8 / 8 backend partitions enabled for every run
No crash, timeout, NO_BACKEND, assertion, or fatal error found in logs
```

graphBIG preset:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset graphbig \
  --latencies 0 \
  --queue-limits 32 \
  --config-variant a100_1stack \
  --a100-l2-8mb \
  --max-cycle 2000 \
  --timeout 120 \
  --jobs 8 \
  --out-dir results/ramulator2_backend_graphbig_a100_1stack_l2_8mb_j8_mc2k_v1
```

Result:

```text
17 / 17 MAX_CYCLE_OK
8 / 8 backend partitions enabled for every run
No crash, timeout, NO_BACKEND, assertion, or fatal error found in logs
```

Broad manifest:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset stackganged_broad \
  --latencies 0 \
  --queue-limits 32 \
  --config-variant a100_1stack \
  --a100-l2-8mb \
  --max-cycle 1000 \
  --timeout 120 \
  --jobs 16 \
  --out-dir results/ramulator2_backend_broad_a100_1stack_l2_8mb_j16_mc1k_v1
```

Result:

```text
59 / 59 MAX_CYCLE_OK
8 / 8 backend partitions enabled for every run
Ramulator2 final stats printed for every run
No crash, timeout, NO_BACKEND, assertion, or fatal error found in logs
```

Queue stress subset:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset stackganged_broad \
  --benchmarks micro_mem_bw,polybench_covariance,graphbig_connected_comp,rodinia_backprop \
  --latencies 0 \
  --queue-limits 8,32,128 \
  --config-variant a100_1stack \
  --a100-l2-8mb \
  --max-cycle 1000 \
  --timeout 120 \
  --jobs 6 \
  --out-dir results/ramulator2_backend_queue_stress_a100_1stack_l2_8mb_j6_mc1k_v1
```

Result:

```text
12 / 12 MAX_CYCLE_OK
8 / 8 backend partitions enabled for every run
No crash, timeout, NO_BACKEND, assertion, or fatal error found in logs
```

Broad manifest, longer 52-way run after the CUDA-Sim argument-buffer fix:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset stackganged_broad \
  --latencies 0 \
  --queue-limits 32 \
  --config-variant a100_1stack \
  --a100-l2-8mb \
  --max-cycle 50000 \
  --timeout 240 \
  --jobs 52 \
  --ramulator-inflight-read-limit 32 \
  --ramulator-ticks-per-dram-cycle auto \
  --out-dir results/ramulator2_backend_broad_after_argbuffer_fix_a100_1stack_l2_8mb_j52_mc50k_v1
```

Result:

```text
59 / 59 healthy
status_counts: MAX_CYCLE_OK:54, OK:5
8 / 8 backend partitions enabled for every run
No crash, timeout, NO_BACKEND, assertion, or fatal error found in logs
```

The earlier 50k-cycle run exposed a `rodinia_particlefilter_float` crash in
CUDA-Sim's PTX call path:

```text
double free or corruption (fasttop)
arg_buffer_t::~arg_buffer_t
call_impl
```

The root cause was that `arg_buffer_t` owned `m_param_value` but lacked a
normal deep-copy constructor. Inserting `arg_buffer_t` into STL containers used
the compiler-generated shallow copy constructor, allowing two objects to free
the same parameter buffer. The fix adds explicit copy/move constructors and
copy/move assignment operators in `src/cuda-sim/ptx_ir.h`.

## Sanity Checks

For the broad manifest run:

```text
rows: 59
status_counts: MAX_CYCLE_OK:59
backend_enabled_partitions: always 8
backend_runtime_print_partitions: always 8
max_cycle_hit: always 1
```

The sum of per-partition `accepted_reads` matched Ramulator2
`total_num_read_requests` for checked runs. This is important because
Ramulator2's generic controller increments some internal counters before
enqueue success; the bridge avoids tight rejected retries with
`SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT`.

Slowest broad runs:

```text
micro_mem_bw        59.199 s
polybench_2dconv    52.894 s
polybench_syr2k     49.306 s
polybench_syrk      48.974 s
polybench_2mm       48.958 s
polybench_3mm       46.903 s
proxy_lulesh        46.225 s
```

## Current Limitations

- These are bounded smoke/operation runs, not final performance results.
- The bridge uses one shared Ramulator2 memory system and ticks it from
  partition 0 during Accel-Sim DRAM clock passes.
- Ramulator2 `source_id` is currently fixed to 0 because the GEM5 frontend
  reports one core. This avoids out-of-range per-core stats and keeps HBM SID
  semantics free for future memory-mode experiments.
- Writes are returned to Accel-Sim once Ramulator2 accepts them. Ramulator2's
  generic controller does not invoke write callbacks, matching the old
  GPGPUSim-Ramulator integration behavior.
- Address mapping is functional but not yet semantically aligned to the exact
  Accel-Sim memory-partition mapping. That should be tightened before using
  results as quantitative HBM4 baseline performance.

# System Check Microbenchmarks

`manifest.tsv` contains microbenchmarks used to validate the simulator and
memory-system plumbing. These rows are intentionally separate from the main
workload manifest because they are synthetic probes, not representative
application workloads.

Use this set when checking:

- AccelSim + Ramulator2 bridge startup and finalization.
- Read/write counter accounting.
- Queue pressure, rejected request counters, and backend-full behavior.
- HBM channel mapping and partition distribution.
- L1/L2/cache-path sanity separate from DRAM-path behavior.

## How To Run

List the rows:

```bash
cd ../../../simulator/accelsim_ramulator
./scripts/run_fixed_backend_matrix.py \
  --preset accelsim_ramulator_system_check \
  --list-benchmarks
```

Run the H100 SXM Samsung HBM3 1/5-stack check:

```bash
./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --config-variant h100_1stack \
  --ramulator-config configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml \
  --preset accelsim_ramulator_system_check \
  --latencies 0 \
  --queue-limits 64 \
  --ramulator-inflight-read-limit auto \
  --ramulator-ticks-per-dram-cycle auto \
  --gpgpusim-host-timing on \
  --max-cycle 0 \
  --timeout 0 \
  --jobs 8 \
  --out-dir results/h100_1stack_system_check
```

For full H100, switch to:

```bash
--config-variant h100_full
--ramulator-config configs/ramulator/h100_sxm_hbm3_sid_80ch.yaml
```

## Row Notes

| Benchmark | Primary check | Interpretation note |
| --- | --- | --- |
| `micro_mem_bw` | Streaming DRAM bandwidth and queue pressure. | Best DRAM-path pressure probe in this set. |
| `micro_mem_lat` | Pointer-chasing memory latency. | Useful for read-latency sanity; throughput is intentionally low. |
| `micro_mem_atom_size` | DRAM request granularity and atom size sensitivity. | Can create heavy rejected/backend-full counts; use as a stress probe. |
| `micro_l1_bw_128` | L1 bandwidth/cache path. | May generate little Ramulator2 DRAM traffic after cache warmup. |
| `micro_l2_bw_32f` | L2 bandwidth/cache path. | Treat as cache-path validation, not sustained DRAM bandwidth. |
| `micro_l2_lat` | L2 latency/cache path. | Often served by cache and may show zero Ramulator2 accepted requests. |
| `micro_l2_access_grain` | L2 line/sector behavior. | Useful for checking request granularity and L2 accounting. |
| `micro_atomic_add_bw_conflict` | Atomic/cache serialization behavior. | Not a representative DRAM benchmark; use for atomic-path sanity only. |

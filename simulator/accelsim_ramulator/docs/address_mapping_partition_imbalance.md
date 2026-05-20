# Address Mapping And Partition Imbalance Check

Last updated: 2026-05-20

This note checks the apparent partition imbalance observed in early
AccelSim + Ramulator2 experiments. The immediate concern was that
`polybench_atax`, `polybench_mvt`, and `polybench_gesummv` routed almost all
accepted backend traffic to partition 0 in the bounded 50k-cycle smoke run.

## Current Mapping

The A100 1-stack runs append:

```text
-gpgpu_n_clusters 22
-gpgpu_n_mem 8
```

but keep the base A100 address mapping:

```text
-gpgpu_mem_addr_mapping dramid@8;00000000.00000000.00000000.00000000.0000RRRR.RRRRRRRR.RBBBCCCC.BCCSSSSS
-gpgpu_memory_partition_indexing 0
-gpgpu_n_sub_partition_per_mchannel 4
```

For `n_mem = 8`, AccelSim prints:

```text
addr_dec_mask[CHIP]  = 0000000000000700  high:11 low:8
sub_partition_id_mask = 0000000000008080
```

So the memory channel/partition id comes from address bits `[10:8]`. With
`CONSECUTIVE` indexing, a stride that is a multiple of 2048B keeps these bits
constant and can temporarily camp on one memory partition.

## Why PolyBench Hits This Case

The three suspicious PolyBench kernels use `N = 4096` and `float`, so the row
stride is:

```text
4096 elements * 4B = 16384B
```

That stride leaves channel bits `[10:8]` unchanged. For warp lanes that touch
different rows at the same column, or for column-stride loops, requests can
initially map to the same memory channel.

Relevant kernels:

| Benchmark | Kernel pattern | Mapping risk |
| --- | --- | --- |
| `polybench_atax` | `A[i * NY + j]`, then `A[i * NY + j]` with loop order swapped | 16KB row stride can camp on one channel in early phases |
| `polybench_mvt` | `a[i * N + j]` and `a[j * N + i]` | Row/column traversal exposes the 16KB stride |
| `polybench_gesummv` | `a[i * N + j]`, `b[i * N + j]` | Same 16KB row stride, two matrices |

## Smoke Results

The original bounded q32 smoke result showed severe early imbalance:

| Run | Benchmark | Active partitions | Max share | Accepted reads |
| --- | --- | ---: | ---: | --- |
| `CONSECUTIVE`, q32, 50k | `polybench_atax` | 1/8 | 1.000 | `[5009, 0, 0, 0, 0, 0, 0, 0]` |
| `CONSECUTIVE`, q32, 50k | `polybench_mvt` | 1/8 | 1.000 | `[5114, 0, 0, 0, 0, 0, 0, 0]` |
| `CONSECUTIVE`, q32, 50k | `polybench_gesummv` | 1/8 | 1.000 | `[5219, 0, 0, 0, 0, 0, 0, 0]` |

The same 50k-cycle smoke with q128 still camps on partition 0, so this is not
only the q32 queue limit:

| Run | Benchmark | Active partitions | Max share | Accepted reads |
| --- | --- | ---: | ---: | --- |
| `CONSECUTIVE`, q128, 50k | `polybench_atax` | 1/8 | 1.000 | `[6443, 0, 0, 0, 0, 0, 0, 0]` |
| `CONSECUTIVE`, q128, 50k | `polybench_mvt` | 1/8 | 1.000 | `[7213, 0, 0, 0, 0, 0, 0, 0]` |
| `CONSECUTIVE`, q128, 50k | `polybench_gesummv` | 1/8 | 1.000 | `[5869, 0, 0, 0, 0, 0, 0, 0]` |

Enabling AccelSim's IPoly partition indexing distributes the same early window:

| Run | Benchmark | Active partitions | Max share | Accepted reads |
| --- | --- | ---: | ---: | --- |
| `IPOLY`, q128, 50k | `polybench_atax` | 8/8 | 0.143 | `[1984, 1984, 1984, 1912, 1505, 1502, 1505, 1487]` |
| `IPOLY`, q128, 50k | `polybench_mvt` | 8/8 | 0.144 | `[1988, 1992, 1988, 1824, 1505, 1502, 1505, 1488]` |
| `IPOLY`, q128, 50k | `polybench_gesummv` | 8/8 | 0.134 | `[1721, 1722, 1721, 1642, 1606, 1606, 1605, 1234]` |

Command used for the IPoly check:

```bash
python3 ./scripts/run_fixed_backend_matrix.py \
  --backend ramulator2 \
  --preset stackganged_broad \
  --benchmarks polybench_atax,polybench_mvt,polybench_gesummv \
  --latencies 0 \
  --queue-limits 128 \
  --config-variant a100_1stack \
  --config-overrides '-gpgpu_memory_partition_indexing 2' \
  --a100-l2-8mb \
  --max-cycle 50000 \
  --timeout 240 \
  --jobs 3 \
  --ramulator-inflight-read-limit 128 \
  --ramulator-ticks-per-dram-cycle 1 \
  --out-dir results/address_mapping_ipoly_smoke_a100_1stack_l2_8mb_q128_if128_mc50k_v1
```

## Unbounded Run Status

The current unbounded q128 run, still using `CONSECUTIVE`, eventually spreads
the same benchmarks across all eight partitions:

| Run | Benchmark | Active partitions | Max share | Accepted reads |
| --- | --- | ---: | ---: | --- |
| `CONSECUTIVE`, q128, unbounded partial/final log | `polybench_atax` | 8/8 | 0.125 | `[524628, 524640, 524646, 524615, 524683, 524682, 524710, 524736]` |
| `CONSECUTIVE`, q128, unbounded partial/final log | `polybench_mvt` | 8/8 | 0.125 | `[524630, 524635, 524689, 524676, 524690, 524678, 524714, 524815]` |
| `CONSECUTIVE`, q128, unbounded partial/final log | `polybench_gesummv` | 8/8 | 0.180 | `[913235, 873923, 716792, 634598, 623193, 544074, 826550, 1129856]` |

This means the 50k-cycle smoke result is a real early-phase channel-camping
signature, but it is not the whole-run traffic distribution for atax/mvt.

## Interpretation

The address decoder is behaving consistently with the current config:

```text
channel = addr[10:8]
```

The partition-0-only behavior in short runs comes from workload access phase
and the 16KB matrix row stride. It is not evidence that the Ramulator2 backend
is hardwired to partition 0. The backend object is per AccelSim memory
partition; Ramulator2 ticking is centralized on partition 0 only to avoid
advancing the shared Ramulator2 instance multiple times per GPU cycle.

For benchmark classification:

1. Do not classify benchmark partition balance from a short `MAX_CYCLE_OK`
   smoke window.
2. Record both early-window and whole-run partition metrics when a benchmark has
   phase behavior.
3. Treat `CONSECUTIVE` mapping as useful for exposing channel-camping stress,
   but not as the only baseline.
4. Use `IPOLY` as a sensitivity run to separate HBM timing effects from
   address-mapping artifacts.

## AccelSim Partition vs Ramulator2 Channel

The bridge previously had a second address-mapping mismatch.

AccelSim chooses the memory partition before the request enters the SG backend:

```text
CONSECUTIVE channel = addr[10:8]
IPOLY channel       = ipoly_hash(higher_bits, chip/subpartition)
```

The bridge then sends the original raw address to a shared Ramulator2 instance.
With the original `RoBaRaCoCh` mapper, Ramulator2 applied its own channel
decode:

```text
tx_offset = log2(prefetch * channel_width / 8) = log2(8 * 32 / 8) = 5
Ramulator2 channel = (addr >> 5) & 0x7 = addr[7:5]
```

For the current HBM4 config, Ramulator2's `RoBaRaCoCh` bit allocation is:

| Ramulator2 field | Raw address bits |
| --- | --- |
| channel | `[7:5]` |
| column | `[12:8]` |
| pseudochannel | `[13]` |
| sid | `[15:14]` |
| bankgroup | `[17:16]` |
| bank | `[19:18]` |
| row | `[30:20]` |

Therefore the current bridge double-decodes memory addresses. AccelSim's
backend partition statistics and Ramulator2's internal channel statistics should
be treated as separate views until the mapping is unified.

Example from the current q128 unbounded logs:

| Benchmark | AccelSim backend accepted reads | Ramulator2 `num_read_reqs_*` |
| --- | --- | --- |
| `polybench_atax` | `[524628, 524640, 524646, 524615, 524683, 524682, 524710, 524736]` | `[764413, 727440, 716743, 734218, 682654, 702308, 709206, 735560]` |
| `polybench_mvt` | `[524630, 524635, 524689, 524676, 524690, 524678, 524714, 524815]` | `[788005, 736013, 715849, 747922, 727393, 718618, 722183, 708560]` |

The Ramulator2 per-channel `num_read_reqs_*` counters are request attempts at
the controller and include requests that fail to enqueue. They are not the same
as successful accepted reads. Still, the distribution confirms that Ramulator2
is using its own channel decode.

This has been fixed with a minimal external-channel mapper:

```text
Ramulator2 AddrMapper = ExternalChannelRoBaRaCoCh
Ramulator2 channel    = Request::source_id
Bridge source_id      = AccelSim memory partition id
```

The mapper still consumes the same raw channel bits that `RoBaRaCoCh` would
have consumed before mapping lower levels. This keeps the lower-level
column/pseudochannel/SID/bankgroup/bank/row bit layout aligned with the previous
Ramulator2 baseline while making channel ownership external to AccelSim.

Changed files:

```text
simulator/ramulator2/src/addr_mapper/impl/linear_mappers.cpp
simulator/accelsim_ramulator/configs/ramulator/hbm4.yaml
simulator/accelsim_ramulator/configs/ramulator/hbm4_external.yaml
simulator/accelsim_ramulator/bridge/sgram_backend.cc
simulator/gpgpu-sim_distribution/src/gpgpu-sim/sgram_backend.cc
```

Validation:

| Run | Result |
| --- | --- |
| Bridge smoke, `source_id=0..7` | Ramulator2 `num_read_reqs_0..7 = [1, 1, 1, 1, 1, 1, 1, 1]` |
| `CONSECUTIVE`, `polybench_atax`, 5k | AccelSim accepted reads `[530, 0, 0, 0, 0, 0, 0, 0]`; expected channel camping remains visible |
| `IPOLY`, `polybench_atax`, 5k | `MAX_CYCLE_OK`, active partitions `8/8`, accepted reads `[502, 502, 502, 503, 503, 502, 405, 298]` |
| `IPOLY`, `polybench_atax`, 50k | `MAX_CYCLE_OK`, active partitions `8/8`, accepted reads `[5928, 5922, 5920, 5866, 5832, 5809, 5756, 5502]` |

The old crash in the IPOLY 5k/50k bounded runs was not an address-mapping
failure. GDB showed:

```text
atexit -> sgram_ramulator2_finalize -> Ramulator2 print_stats -> SIGSEGV
```

The bounded run stops with outstanding Ramulator2 requests. The bridge now skips
Ramulator2 stats finalization when outstanding requests remain, so max-cycle
smoke runs complete cleanly and still preserve AccelSim-side backend counters.

For AccelSim benchmark sweeps, `run_fixed_backend_matrix.py` now controls this
with `--ramulator-finalize-stats {auto,on,off}`. The default `auto` mode keeps
bounded smoke runs from depending on Ramulator2's YAML stats dump:

```text
SGRAM_RAMULATOR_SKIP_FINALIZE_STATS=1
```

For unbounded `--max-cycle 0` runs, `auto` unsets the skip variable, lets
Ramulator2 print internal stats at process shutdown, and promotes selected
Ramulator2 fields into `summary.csv`:

```text
memory_system_cycles
num_read_reqs_i / num_write_reqs_i
row_hits_i / row_misses_i / row_conflicts_i
read_row_hits_i / read_row_misses_i / read_row_conflicts_i
queue_len_avg_i / read_queue_len_avg_i
read_latency_i / avg_read_latency_i
```

The standalone bridge smoke also leaves finalization enabled, so it can still
validate Ramulator2 per-channel counters directly.

## Stress Results After External-Channel Fix

Additional stress checks:

| Run | Result |
| --- | --- |
| Bridge smoke loop | 50/50 passed; each run produced `num_read_reqs_0..7 = [1, 1, 1, 1, 1, 1, 1, 1]` |
| `CONSECUTIVE`, 8 benchmarks, q128/if128, 50k | 8/8 `MAX_CYCLE_OK` |
| `IPOLY`, 15 benchmarks x q64/q128, if128, 50k | 26/30 passed; 4 crashes were `parboil_tpacf` and `pannotia_pagerank` |
| Fixed backend comparison for crash cases | `parboil_tpacf` and `pannotia_pagerank` also crashed |
| Native backend comparison for crash cases | `parboil_tpacf` and `pannotia_pagerank` also crashed |
| `IPOLY`, 10 benchmarks, q256/if512, 50k | 10/10 passed after disabling Ramulator2 finalize stats in the runner |

Interpretation:

```text
parboil_tpacf / pannotia_pagerank failures are existing AccelSim benchmark
compatibility failures, not Ramulator2 external-channel mapper failures.
Native gdb reproduction shows both enter AccelSim's unimplemented PTX RED path:
red.shared.add.u32 for parboil_tpacf and red.global.add.f32 for pannotia_pagerank.
```

No `ExternalChannelRoBaRaCoCh` source-id range errors or channel-mapping
exceptions appeared in the stress logs.

## Recommended Experiment Policy

For final AccelSim + Ramulator2 baseline comparisons:

| Purpose | Mapping |
| --- | --- |
| Main balanced baseline | `-gpgpu_memory_partition_indexing 2` |
| Address-mapping sensitivity | `-gpgpu_memory_partition_indexing 0` |
| Stress/channel-camping case | Keep `CONSECUTIVE` and report partition imbalance explicitly |

The runner now records these fields in newly generated summaries:

```text
backend_active_partitions
backend_max_partition_share
backend_partition_cv
backend_accepted_reads_by_partition
backend_rejected_by_partition
```

That will prevent early smoke runs from being mistaken for whole-workload
traffic behavior.

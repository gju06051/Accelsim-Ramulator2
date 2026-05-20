# Ramulator2 Backend Reject And Inflight Notes

Last updated: 2026-05-20

This note explains the SG backend queue and reject counters.

## What `rejected` Means

`rejected` is not a dropped request count. The SG backend keeps the request at
the front of its pending queue and retries it in later cycles. Therefore
`rejected` is a retry/backpressure count.

The original single `rejected` counter mixed two cases:

```text
1. global inflight read limit is full
2. Ramulator2 controller queue rejects the request
```

The backend now reports these separately:

```text
rejected_inflight
rejected_ramulator
backend_full
global_inflight_reads
inflight_limit
```

The runner also copies them into `summary.csv`:

```text
backend_total_rejected_inflight
backend_total_rejected_ramulator
backend_total_full_stalls
backend_rejected_inflight_by_partition
backend_rejected_ramulator_by_partition
backend_full_by_partition
backend_global_inflight_reads
backend_inflight_limit
```

## Queue Levels

There are three different backpressure points:

| Level | Counter | Meaning |
| --- | --- | --- |
| AccelSim SG backend queue | `backend_full` | `m_pending + m_completed >= SGRAM_QUEUE_LIMIT`; L2 cannot push into backend |
| SG bridge global read cap | `rejected_inflight` | `g_ramulator2_inflight_reads >= SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT` |
| Ramulator2 controller queue | `rejected_ramulator` | `memory_system->send(req)` returned false, usually read/write buffer full |

Current defaults used in the main q128 runs:

```text
SGRAM_QUEUE_LIMIT=128
SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT=128
```

`g_ramulator2_inflight_reads` is global across all AccelSim memory partitions,
not per channel.

## Smoke Check

A short `polybench_atax` run with q128 and inflight 128:

```text
accepted_reads=530
rejected=4211
rejected_inflight=0
rejected_ramulator=4211
backend_full=2853
global_inflight_reads=42
inflight_limit=128
```

So this case is Ramulator2 controller-queue limited, not inflight-limited.

The same run with inflight limit forced to 16:

```text
accepted_reads=249
rejected=4606
rejected_inflight=4606
rejected_ramulator=0
backend_full=2313
global_inflight_reads=16
inflight_limit=16
```

This confirms the new counters distinguish the two reject causes.

## Interpretation

For performance analysis:

1. Use `backend_full` to detect AccelSim-side queue backpressure.
2. Use `rejected_inflight` to detect an artificial bridge-level MLP cap.
3. Use `rejected_ramulator` to detect Ramulator2 controller queue pressure.
4. Do not compare raw `rejected` across different queue/inflight settings
   without the reason breakdown.

For HBM4 baseline experiments, `ramulator_inflight_read_limit=128` is probably
still conservative because it is global across all 8 channels. A later sweep
should compare:

```text
inflight_read_limit = 128 / 256 / 512 / 0(unlimited)
queue_limit         = 128 / 256 / 512
```

Use the reason counters to pick a setting that does not dominate the memory
timing behavior.

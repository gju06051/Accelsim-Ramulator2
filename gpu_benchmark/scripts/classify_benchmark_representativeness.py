#!/usr/bin/env python3
"""Classify AccelSim + Ramulator2 benchmark rows by workload character.

This helper reads one or more `summary.csv` files produced by
`run_fixed_backend_matrix.py` and emits a compact TSV.  It is intentionally a
heuristic pass: the goal is to flag benchmark rows that are too small to be
useful as stable representatives, and to separately label rows as
memory-intensive or compute-intensive after normalizing DRAM requests by
simulated instructions and checking backend queue pressure.
"""

from __future__ import annotations

import argparse
import csv
import glob
from pathlib import Path
from typing import Iterable


OK_STATUSES = {"OK", "MAX_CYCLE_OK"}


def parse_int(value: str | None) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def parse_float(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def expand_inputs(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(Path(p) for p in glob.glob(pattern))
        if matches:
            paths.extend(matches)
        else:
            paths.append(Path(pattern))
    return paths


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as file:
        return {row["name"]: row for row in csv.DictReader(file, delimiter="\t")}


def classify(row: dict[str, str], args: argparse.Namespace) -> tuple[str, str]:
    status = row.get("status", "")
    if status not in OK_STATUSES:
        return "failed", f"status={status}"

    stats_present = parse_int(row.get("ramulator_stats_present"))
    partitions = parse_int(row.get("backend_runtime_print_partitions"))
    if partitions <= 0:
        return "no_backend", "no Ramulator2 backend partition print"
    if stats_present != 1:
        return "metric_missing", "ramulator_stats_present != 1"

    reads = max(
        parse_int(row.get("ramulator_total_num_read_requests")),
        parse_int(row.get("backend_total_accepted_reads")),
    )
    writes = max(
        parse_int(row.get("ramulator_total_num_write_requests")),
        parse_int(row.get("backend_total_accepted_writes")),
    )
    dram_reqs = reads + writes
    l2_misses = parse_int(row.get("l2_misses"))
    active_partitions = parse_int(row.get("backend_active_partitions"))
    active_ratio = active_partitions / partitions if partitions else 0.0
    max_cycle = parse_int(row.get("max_cycle_hit"))

    bounded = "bounded " if max_cycle else ""
    if dram_reqs < args.tiny_dram_requests and l2_misses < args.tiny_l2_misses:
        return "tiny", f"{bounded}dram_reqs={dram_reqs} l2_misses={l2_misses}"
    if dram_reqs < args.small_dram_requests and l2_misses < args.small_l2_misses:
        return "small", f"{bounded}dram_reqs={dram_reqs} l2_misses={l2_misses}"
    if active_ratio < args.min_active_partition_ratio and dram_reqs < args.large_dram_requests:
        return "partition_sparse", (
            f"{bounded}active_ratio={active_ratio:.3f} "
            f"active={active_partitions}/{partitions} dram_reqs={dram_reqs}"
        )
    if dram_reqs < args.large_dram_requests:
        return "moderate", f"{bounded}dram_reqs={dram_reqs} l2_misses={l2_misses}"
    return "representative", f"{bounded}dram_reqs={dram_reqs} l2_misses={l2_misses}"


def classify_intensity(
    dram_reqs: int,
    instructions: int,
    l2_miss_rate: float,
    queue_avg_sum: float,
    args: argparse.Namespace,
) -> tuple[str, str, float, float]:
    if instructions <= 0:
        return "compute-intensive", "no instruction count; not memory-bound", 0.0, 0.0

    dram_req_per_kinst = dram_reqs * 1000.0 / instructions
    dram_bytes_per_inst = dram_reqs * args.dram_request_bytes / instructions

    if dram_req_per_kinst >= args.high_dram_req_per_kinst:
        return (
            "memory-intensive",
            f"req_per_kinst={dram_req_per_kinst:.3f}",
            dram_req_per_kinst,
            dram_bytes_per_inst,
        )
    if (
        queue_avg_sum >= args.memory_queue_pressure_threshold
        and l2_miss_rate >= args.memory_l2_miss_rate_threshold
    ):
        return (
            "memory-intensive",
            (
                f"queue_avg_sum={queue_avg_sum:.3f} "
                f"l2_miss_rate={l2_miss_rate:.3f}"
            ),
            dram_req_per_kinst,
            dram_bytes_per_inst,
        )
    if (
        dram_req_per_kinst >= args.queue_assisted_dram_req_per_kinst
        and queue_avg_sum >= args.queue_assisted_queue_pressure
        and l2_miss_rate >= args.queue_assisted_l2_miss_rate
    ):
        return (
            "memory-intensive",
            (
                f"req_per_kinst={dram_req_per_kinst:.3f} "
                f"queue_avg_sum={queue_avg_sum:.3f} "
                f"l2_miss_rate={l2_miss_rate:.3f}"
            ),
            dram_req_per_kinst,
            dram_bytes_per_inst,
        )
    return (
        "compute-intensive",
        (
            f"req_per_kinst={dram_req_per_kinst:.3f} "
            f"queue_avg_sum={queue_avg_sum:.3f} "
            f"l2_miss_rate={l2_miss_rate:.3f}"
        ),
        dram_req_per_kinst,
        dram_bytes_per_inst,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summaries", nargs="+", help="summary.csv path or glob.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("gpu_benchmark/benchmarks/main/manifest.tsv"),
    )
    parser.add_argument("--tiny-dram-requests", type=int, default=1_000)
    parser.add_argument("--tiny-l2-misses", type=int, default=10_000)
    parser.add_argument("--small-dram-requests", type=int, default=10_000)
    parser.add_argument("--small-l2-misses", type=int, default=50_000)
    parser.add_argument("--large-dram-requests", type=int, default=100_000)
    parser.add_argument("--min-active-partition-ratio", type=float, default=0.5)
    parser.add_argument("--high-dram-req-per-kinst", type=float, default=5.0)
    parser.add_argument("--memory-queue-pressure-threshold", type=float, default=256.0)
    parser.add_argument("--memory-l2-miss-rate-threshold", type=float, default=0.50)
    parser.add_argument("--queue-assisted-dram-req-per-kinst", type=float, default=3.0)
    parser.add_argument("--queue-assisted-queue-pressure", type=float, default=128.0)
    parser.add_argument("--queue-assisted-l2-miss-rate", type=float, default=0.70)
    parser.add_argument("--dram-request-bytes", type=int, default=32)
    parser.add_argument("--only-flagged", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    writer = csv.writer(__import__("sys").stdout, delimiter="\t", lineterminator="\n")
    writer.writerow(
        [
            "source",
            "benchmark",
            "suite",
            "status",
            "class",
            "reason",
            "intensity_class",
            "intensity_reason",
            "dram_requests",
            "reads",
            "writes",
            "instructions",
            "dram_req_per_kinst",
            "dram_bytes_per_inst",
            "l2miss_per_kinst",
            "l2_misses",
            "l2_miss_rate",
            "queue_avg_sum",
            "active_partitions",
            "partitions",
            "max_cycle_hit",
        ]
    )

    for summary in expand_inputs(args.summaries):
        if not summary.exists():
            continue
        with summary.open("r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                row_class, reason = classify(row, args)
                if args.only_flagged and row_class in {"representative", "moderate"}:
                    continue
                bench = row.get("benchmark", "")
                manifest_row = manifest.get(bench, {})
                reads = max(
                    parse_int(row.get("ramulator_total_num_read_requests")),
                    parse_int(row.get("backend_total_accepted_reads")),
                )
                writes = max(
                    parse_int(row.get("ramulator_total_num_write_requests")),
                    parse_int(row.get("backend_total_accepted_writes")),
                )
                dram_reqs = reads + writes
                instructions = max(
                    parse_int(row.get("tot_sim_insn")),
                    parse_int(row.get("sim_insn")),
                )
                l2_misses = parse_int(row.get("l2_misses"))
                l2_miss_rate = parse_float(row.get("l2_miss_rate"))
                if l2_miss_rate <= 0.0:
                    l2_accesses = parse_int(row.get("l2_accesses"))
                    l2_miss_rate = l2_misses / l2_accesses if l2_accesses else 0.0
                queue_avg_sum = parse_float(row.get("ramulator_queue_len_avg_sum"))
                (
                    intensity_class,
                    intensity_reason,
                    dram_req_per_kinst,
                    dram_bytes_per_inst,
                ) = classify_intensity(
                    dram_reqs, instructions, l2_miss_rate, queue_avg_sum, args
                )
                l2miss_per_kinst = (
                    l2_misses * 1000.0 / instructions if instructions else 0.0
                )
                writer.writerow(
                    [
                        summary,
                        bench,
                        manifest_row.get("suite", row.get("suite", "")),
                        row.get("status", ""),
                        row_class,
                        reason,
                        intensity_class,
                        intensity_reason,
                        dram_reqs,
                        reads,
                        writes,
                        instructions,
                        f"{dram_req_per_kinst:.6f}",
                        f"{dram_bytes_per_inst:.6f}",
                        f"{l2miss_per_kinst:.6f}",
                        l2_misses,
                        f"{l2_miss_rate:.6f}",
                        f"{queue_avg_sum:.6f}",
                        parse_int(row.get("backend_active_partitions")),
                        parse_int(row.get("backend_runtime_print_partitions")),
                        parse_int(row.get("max_cycle_hit")),
                    ]
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

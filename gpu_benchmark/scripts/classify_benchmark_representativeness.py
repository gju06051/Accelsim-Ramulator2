#!/usr/bin/env python3
"""Classify AccelSim + Ramulator2 benchmark rows by memory-traffic size.

This helper reads one or more `summary.csv` files produced by
`run_fixed_backend_matrix.py` and emits a compact TSV.  It is intentionally a
heuristic pass: the goal is to flag benchmark rows that are too small to be
useful as memory-system representatives before spending time on long natural
runs.
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
            "dram_requests",
            "reads",
            "writes",
            "l2_misses",
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
                writer.writerow(
                    [
                        summary,
                        bench,
                        manifest_row.get("suite", row.get("suite", "")),
                        row.get("status", ""),
                        row_class,
                        reason,
                        reads + writes,
                        reads,
                        writes,
                        parse_int(row.get("l2_misses")),
                        parse_int(row.get("backend_active_partitions")),
                        parse_int(row.get("backend_runtime_print_partitions")),
                        parse_int(row.get("max_cycle_hit")),
                    ]
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

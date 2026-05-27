#!/usr/bin/env python3
"""Post-run quality gate for AccelSim + Ramulator2 summary.csv files."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "INFO": 3}
GOOD_STATUS = {"OK"}
BOUNDED_STATUS = {"MAX_CYCLE_OK", "TIMEBOX_OK"}


@dataclass(frozen=True)
class Issue:
    severity: str
    check: str
    benchmark: str
    message: str
    value: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check AccelSim + Ramulator2 summary.csv files for failed rows, "
            "missing Ramulator stats, completion gaps, zero-request rows, and "
            "partition/channel imbalance."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="summary.csv files or result directories containing summary.csv",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "bounded", "unbounded"),
        default="auto",
        help=(
            "How to interpret MAX_CYCLE_OK/completion gaps. In auto mode, "
            "rows with max_cycle_hit=1 or status=MAX_CYCLE_OK are treated as bounded."
        ),
    )
    parser.add_argument(
        "--expected-partitions",
        type=int,
        default=None,
        help="Expected Ramulator/AccelSim backend partitions for every Ramulator2 row.",
    )
    parser.add_argument(
        "--min-requests",
        type=float,
        default=1.0,
        help="Minimum total read+write backend/Ramulator requests before a row is nonzero.",
    )
    parser.add_argument(
        "--cv-warn",
        type=float,
        default=1.0,
        help="Warn when partition/channel coefficient of variation exceeds this value.",
    )
    parser.add_argument(
        "--cv-p0",
        type=float,
        default=3.0,
        help="Escalate partition/channel coefficient of variation to P0 at this value.",
    )
    parser.add_argument(
        "--min-cv-requests",
        type=float,
        default=100000.0,
        help="Only check CV thresholds when the row has at least this many read requests.",
    )
    parser.add_argument(
        "--max-share-warn",
        type=float,
        default=0.25,
        help="Warn when one partition receives at least this share of accepted reads.",
    )
    parser.add_argument(
        "--reject-ratio-warn",
        type=float,
        default=1.0,
        help="Warn when rejected/accepted request ratio exceeds this value.",
    )
    parser.add_argument(
        "--details",
        type=int,
        default=8,
        help="Maximum issue examples to print per severity and check.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("P0", "P1", "P2", "never"),
        default="P0",
        help="Exit nonzero if any issue at or above this severity is found.",
    )
    return parser.parse_args()


def resolve_summary_paths(paths: Iterable[Path]) -> list[Path]:
    resolved: list[Path] = []
    for path in paths:
        candidate = path
        if candidate.is_dir():
            candidate = candidate / "summary.csv"
        if not candidate.exists():
            raise FileNotFoundError(f"summary.csv not found: {candidate}")
        resolved.append(candidate)
    return resolved


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return rows, fields


def get(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def as_float(row: dict[str, str], key: str) -> float | None:
    text = get(row, key)
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def as_int(row: dict[str, str], key: str) -> int | None:
    value = as_float(row, key)
    if value is None:
        return None
    return int(value)


def is_truthy(row: dict[str, str], key: str) -> bool:
    text = get(row, key).lower()
    return text in {"1", "true", "yes", "on"}


def row_name(row: dict[str, str]) -> str:
    bench = get(row, "benchmark") or "<unknown>"
    latency = get(row, "latency")
    queue = get(row, "queue_limit")
    variant = get(row, "config_variant")
    suffix = []
    if variant:
        suffix.append(variant)
    if latency:
        suffix.append(f"lat{latency}")
    if queue:
        suffix.append(f"q{queue}")
    if suffix:
        return f"{bench} ({', '.join(suffix)})"
    return bench


def is_bounded(row: dict[str, str], mode: str) -> bool:
    if mode == "bounded":
        return True
    if mode == "unbounded":
        return False
    return get(row, "status") in BOUNDED_STATUS or is_truthy(row, "max_cycle_hit")


def total_requests(row: dict[str, str]) -> float:
    ram_reads = as_float(row, "ramulator_total_num_read_requests")
    ram_writes = as_float(row, "ramulator_total_num_write_requests")
    if ram_reads is None:
        ram_reads = as_float(row, "ramulator_num_read_reqs") or 0.0
    if ram_writes is None:
        ram_writes = as_float(row, "ramulator_num_write_reqs") or 0.0
    backend_reads = as_float(row, "backend_total_accepted_reads") or 0.0
    backend_writes = as_float(row, "backend_total_accepted_writes") or 0.0
    return max((ram_reads or 0.0) + (ram_writes or 0.0), backend_reads + backend_writes)


def read_requests(row: dict[str, str]) -> float:
    ram_reads = as_float(row, "ramulator_total_num_read_requests")
    if ram_reads is None:
        ram_reads = as_float(row, "ramulator_num_read_reqs")
    if ram_reads is not None:
        return ram_reads
    return as_float(row, "backend_total_accepted_reads") or 0.0


def add_issue(
    issues: list[Issue],
    severity: str,
    check: str,
    row: dict[str, str],
    message: str,
    value: str | float | int | None = "",
) -> None:
    value_text = "" if value is None else str(value)
    issues.append(Issue(severity, check, row_name(row), message, value_text))


def check_row(
    row: dict[str, str],
    fields: set[str],
    args: argparse.Namespace,
    issues: list[Issue],
) -> None:
    status = get(row, "status")
    backend = get(row, "backend")
    bounded = is_bounded(row, args.mode)

    if not status:
        add_issue(issues, "P0", "status", row, "missing status")
    elif status in GOOD_STATUS:
        pass
    elif status in BOUNDED_STATUS:
        severity = "P2" if args.mode == "bounded" else "P1"
        add_issue(
            issues,
            severity,
            "bounded",
            row,
            "bounded max-cycle row; completion gaps may be stop-condition artifacts",
            status,
        )
    else:
        add_issue(issues, "P0", "status", row, "row did not complete cleanly", status)

    if backend != "ramulator2":
        return

    total_req = total_requests(row)
    read_req = read_requests(row)

    stats_present = get(row, "ramulator_stats_present")
    if stats_present != "1":
        add_issue(
            issues,
            "P0",
            "ramulator-stats",
            row,
            "Ramulator stats are missing or were not parsed",
            stats_present or "<empty>",
        )

    if "ramulator_cmd_stats_present" in fields:
        if get(row, "ramulator_cmd_stats_present") != "1":
            add_issue(
                issues,
                "P0",
                "command-stats",
                row,
                "Ramulator command stats are missing",
                get(row, "ramulator_cmd_stats_present") or "<empty>",
            )
    else:
        add_issue(
            issues,
            "P1",
            "command-stats",
            row,
            "summary schema has no ramulator_cmd_stats_present column",
        )

    enabled = as_int(row, "backend_enabled_partitions")
    active = as_int(row, "backend_active_partitions")
    if args.expected_partitions is not None and enabled != args.expected_partitions:
        add_issue(
            issues,
            "P0",
            "partitions",
            row,
            "backend_enabled_partitions differs from expected",
            f"{enabled} != {args.expected_partitions}",
        )
    if enabled is None or enabled <= 0:
        add_issue(issues, "P0", "partitions", row, "no enabled backend partitions", enabled)
    elif active is not None and total_req >= args.min_requests:
        if active <= 0:
            add_issue(
                issues,
                "P0",
                "partitions",
                row,
                "backend accepted requests but no active partitions",
                active,
            )
        elif active < enabled:
            add_issue(
                issues,
                "P1",
                "partitions",
                row,
                "not all enabled partitions were active",
                f"{active}/{enabled}",
            )

    if total_req < args.min_requests and status in GOOD_STATUS | BOUNDED_STATUS:
        add_issue(
            issues,
            "P1",
            "zero-requests",
            row,
            "row produced no meaningful Ramulator/backend traffic",
            total_req,
        )

    read_gap = as_float(row, "analysis_backend_read_completion_gap")
    if read_gap is None:
        accepted_reads = as_float(row, "backend_total_accepted_reads")
        completed_reads = as_float(row, "backend_total_completed_reads")
        if accepted_reads is not None and completed_reads is not None:
            read_gap = accepted_reads - completed_reads
    if read_gap and read_gap > 0:
        severity = "P1" if bounded else "P0"
        add_issue(
            issues,
            severity,
            "read-gap",
            row,
            "accepted reads exceed completed reads",
            format_number(read_gap),
        )

    write_gap = as_float(row, "analysis_backend_write_completion_gap")
    if write_gap is None:
        accepted_writes = as_float(row, "backend_total_accepted_writes")
        completed_writes = as_float(row, "backend_global_completed_writes")
        if accepted_writes is not None and completed_writes is not None:
            write_gap = accepted_writes - completed_writes
    if write_gap and write_gap > 0:
        severity = "P2" if bounded else "P1"
        add_issue(
            issues,
            severity,
            "write-gap",
            row,
            "accepted writes exceed completed writes; check write drain semantics",
            format_number(write_gap),
        )

    if read_req >= args.min_cv_requests:
        cv_fields = (
            "analysis_backend_accepted_read_partition_cv",
            "analysis_ramulator_read_req_channel_cv",
            "analysis_ramulator_cmd_rd_channel_cv",
            "backend_partition_cv",
        )
        for field in cv_fields:
            cv = as_float(row, field)
            if cv is None:
                continue
            if cv >= args.cv_p0:
                add_issue(issues, "P0", "partition-cv", row, f"{field} is extreme", cv)
            elif cv >= args.cv_warn:
                add_issue(issues, "P2", "partition-cv", row, f"{field} is high", cv)

        max_share = as_float(row, "backend_max_partition_share")
        if max_share is not None and max_share >= args.max_share_warn:
            add_issue(
                issues,
                "P2",
                "partition-share",
                row,
                "one partition received a high share of accepted reads",
                max_share,
            )

    reject_ratio = as_float(row, "analysis_backend_reject_per_accept")
    if reject_ratio is not None and reject_ratio >= args.reject_ratio_warn:
        add_issue(
            issues,
            "P2",
            "queue-pressure",
            row,
            "backend rejected/accepted request ratio is high",
            reject_ratio,
        )


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6g}"


def print_file_report(path: Path, rows: list[dict[str, str]], issues: list[Issue], args: argparse.Namespace) -> None:
    status_counts = Counter(get(row, "status") or "<missing>" for row in rows)
    backend_counts = Counter(get(row, "backend") or "<missing>" for row in rows)
    severity_counts = Counter(issue.severity for issue in issues)
    bounded_rows = sum(1 for row in rows if is_bounded(row, args.mode))
    ramulator_rows = sum(1 for row in rows if get(row, "backend") == "ramulator2")

    print(f"Summary check: {path}")
    print(f"  rows: {len(rows)}  ramulator2_rows: {ramulator_rows}  bounded_rows: {bounded_rows}")
    print(f"  status: {format_counts(status_counts)}")
    print(f"  backend: {format_counts(backend_counts)}")
    if severity_counts:
        print(
            "  issues: "
            + " ".join(
                f"{severity}={severity_counts.get(severity, 0)}"
                for severity in ("P0", "P1", "P2")
                if severity_counts.get(severity, 0)
            )
        )
    else:
        print("  issues: none")

    grouped: dict[tuple[str, str], list[Issue]] = defaultdict(list)
    for issue in sorted(issues, key=lambda item: (SEVERITY_ORDER[item.severity], item.check, item.benchmark)):
        grouped[(issue.severity, issue.check)].append(issue)

    for severity in ("P0", "P1", "P2"):
        severity_groups = [
            (check, group)
            for (sev, check), group in grouped.items()
            if sev == severity
        ]
        if not severity_groups:
            continue
        print(f"  {severity}:")
        for check, group in sorted(severity_groups, key=lambda item: item[0]):
            print(f"    {check}: {len(group)}")
            for issue in group[: args.details]:
                value = f" [{issue.value}]" if issue.value else ""
                print(f"      - {issue.benchmark}: {issue.message}{value}")
            remaining = len(group) - args.details
            if remaining > 0:
                print(f"      - ... {remaining} more")
    print()


def format_counts(counter: Counter[str]) -> str:
    if not counter:
        return "<none>"
    return ", ".join(f"{key}={counter[key]}" for key in sorted(counter))


def should_fail(all_issues: list[Issue], fail_on: str) -> bool:
    if fail_on == "never":
        return False
    threshold = SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER[issue.severity] <= threshold for issue in all_issues)


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_summary_paths(args.paths)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    all_issues: list[Issue] = []
    for path in paths:
        rows, fields = read_rows(path)
        field_set = set(fields)
        issues: list[Issue] = []
        if not rows:
            issues.append(Issue("P0", "schema", "<file>", "summary.csv has no rows"))
        for row in rows:
            check_row(row, field_set, args, issues)
        print_file_report(path, rows, issues, args)
        all_issues.extend(issues)

    if should_fail(all_issues, args.fail_on):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

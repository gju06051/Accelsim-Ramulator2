#!/usr/bin/env python3
"""Generate and stage larger nvCOMP/cuDF Accel-Sim trace manifests."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = ROOT / "gpu_benchmark" / "benchmarks" / "prepare" / "results"
MAIN_TRACE_MANIFEST = ROOT / "gpu_benchmark" / "benchmarks" / "main" / "trace_manifest.tsv"
MEMORY_TRACE_MANIFEST = (
    ROOT / "gpu_benchmark" / "benchmarks" / "main" / "trace_manifest.memory_intensive.tsv"
)

NVCOMP_CODECS = ("lz4", "snappy", "gdeflate", "deflate", "zstd", "cascaded", "bitcomp", "ans")
CUDF_OPS = ("filter", "project", "groupby", "join", "sort")
CUDF_TPCH_QUERIES = ("q1", "q3", "q6", "q10")


def parse_size(text: str) -> int:
    import re

    match = re.fullmatch(r"\s*(\d+)\s*([kmgt]?i?b?)?\s*", text, re.IGNORECASE)
    if not match:
        raise argparse.ArgumentTypeError(f"invalid size: {text}")
    value = int(match.group(1))
    unit = (match.group(2) or "").lower()
    scale = {
        "": 1,
        "b": 1,
        "k": 1000,
        "kb": 1000,
        "ki": 1024,
        "kib": 1024,
        "m": 1000**2,
        "mb": 1000**2,
        "mi": 1024**2,
        "mib": 1024**2,
        "g": 1000**3,
        "gb": 1000**3,
        "gi": 1024**3,
        "gib": 1024**3,
    }[unit]
    return value * scale


def format_size(size: int) -> str:
    for suffix, scale in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if size % scale == 0:
            return f"{size // scale}{suffix}"
    return f"{size}B"


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def run(cmd: list[str], dry_run: bool) -> None:
    rendered = "+ " + " ".join(cmd)
    print(rendered, flush=True)
    if not dry_run:
        subprocess.run(cmd, check=True)


def read_manifest(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_manifest(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_trace_rows(
    rows: list[dict[str, str]],
    nvcomp_size_label: str,
    cudf_micro_size_label: str,
    cudf_tpch_size_label: str,
    out_root: Path,
) -> list[dict[str, str]]:
    nvcomp_dir = out_root / f"nvcomp_accelsim_traces_{nvcomp_size_label}"
    cudf_micro_dir = out_root / f"cudf_accelsim_traces_{cudf_micro_size_label}"
    cudf_tpch_dir = out_root / f"cudf_tpch_accelsim_traces_{cudf_tpch_size_label}"

    updated: list[dict[str, str]] = []
    for original in rows:
        row = dict(original)
        name = row.get("name", "")
        if name.startswith("nvcomp_"):
            codec = name.removeprefix("nvcomp_")
            row["trace_path"] = rel(
                nvcomp_dir / f"nvcomp_{codec}_{nvcomp_size_label}" / "traces" / "kernelslist.g"
            )
            row["trace_sm"] = row.get("trace_sm") or "86"
            row["source"] = f"nvCOMP memory-intensive {nvcomp_size_label} compression trace"
        elif name.startswith("cudf_tpch_"):
            query = name.removeprefix("cudf_tpch_")
            row["trace_path"] = rel(
                cudf_tpch_dir / f"cudf_tpch_{query}_{cudf_tpch_size_label}" / "traces" / "kernelslist.g"
            )
            row["trace_sm"] = row.get("trace_sm") or "80"
            row["source"] = f"cuDF TPC-H profiler-scoped {cudf_tpch_size_label} trace"
        elif name.startswith("cudf_"):
            op = name.removeprefix("cudf_")
            row["trace_path"] = rel(
                cudf_micro_dir / f"cudf_{op}_{cudf_micro_size_label}" / "traces" / "kernelslist.g"
            )
            row["trace_sm"] = row.get("trace_sm") or "80"
            row["source"] = f"cuDF profiler-scoped {cudf_micro_size_label} trace"
        updated.append(row)
    return updated


def missing_trace_paths(rows: list[dict[str, str]]) -> list[Path]:
    missing: list[Path] = []
    for row in rows:
        value = row.get("trace_path", "")
        if not value:
            continue
        path = Path(os.path.expandvars(value)).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            missing.append(path)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", type=Path, default=RESULTS_ROOT)
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-nvcomp", action="store_true")
    parser.add_argument("--skip-cudf-micro", action="store_true")
    parser.add_argument("--skip-cudf-tpch", action="store_true")
    parser.add_argument("--nvcomp-codecs", nargs="+", default=list(NVCOMP_CODECS))
    parser.add_argument("--nvcomp-size", type=parse_size, default=parse_size("64MiB"))
    parser.add_argument("--nvcomp-chunk-size", type=parse_size, default=parse_size("64KiB"))
    parser.add_argument("--nvcomp-kernel-range", default="3")
    parser.add_argument("--cudf-ops", nargs="+", default=list(CUDF_OPS))
    parser.add_argument("--cudf-micro-size", type=parse_size, default=parse_size("64MiB"))
    parser.add_argument("--cudf-tpch-queries", nargs="+", default=list(CUDF_TPCH_QUERIES))
    parser.add_argument("--cudf-tpch-size", type=parse_size, default=parse_size("128MiB"))
    parser.add_argument("--manifest-out", type=Path, default=MEMORY_TRACE_MANIFEST)
    parser.add_argument("--activate-main-manifest", action="store_true")
    args = parser.parse_args()

    out_root = args.out_root
    nvcomp_label = format_size(args.nvcomp_size)
    cudf_micro_label = format_size(args.cudf_micro_size)
    cudf_tpch_label = format_size(args.cudf_tpch_size)

    force_flag = ["--force"] if args.force else []
    if not args.skip_nvcomp:
        nvcomp_out = out_root / f"nvcomp_accelsim_traces_{nvcomp_label}"
        for codec in args.nvcomp_codecs:
            run(
                [
                    sys.executable,
                    str(ROOT / "gpu_benchmark" / "scripts" / "run_nvcomp_accelsim_trace.py"),
                    "--codec",
                    codec,
                    "--bytes",
                    str(args.nvcomp_size),
                    "--chunk-size",
                    str(args.nvcomp_chunk_size),
                    "--kernel-range",
                    str(args.nvcomp_kernel_range),
                    "--gpu",
                    args.gpu,
                    "--out-dir",
                    str(nvcomp_out),
                    *force_flag,
                ],
                args.dry_run,
            )

    if not args.skip_cudf_micro:
        cudf_out = out_root / f"cudf_accelsim_traces_{cudf_micro_label}"
        for op in args.cudf_ops:
            run(
                [
                    sys.executable,
                    str(ROOT / "gpu_benchmark" / "scripts" / "run_cudf_accelsim_trace.py"),
                    "--workload",
                    "micro",
                    "--op",
                    op,
                    "--size",
                    str(args.cudf_micro_size),
                    "--gpu",
                    args.gpu,
                    "--out-dir",
                    str(cudf_out),
                    *force_flag,
                ],
                args.dry_run,
            )

    if not args.skip_cudf_tpch:
        cudf_tpch_out = out_root / f"cudf_tpch_accelsim_traces_{cudf_tpch_label}"
        for query in args.cudf_tpch_queries:
            run(
                [
                    sys.executable,
                    str(ROOT / "gpu_benchmark" / "scripts" / "run_cudf_accelsim_trace.py"),
                    "--workload",
                    "tpch",
                    "--query",
                    query,
                    "--size",
                    str(args.cudf_tpch_size),
                    "--gpu",
                    args.gpu,
                    "--out-dir",
                    str(cudf_tpch_out),
                    *force_flag,
                ],
                args.dry_run,
            )

    fieldnames, rows = read_manifest(MAIN_TRACE_MANIFEST)
    updated = update_trace_rows(rows, nvcomp_label, cudf_micro_label, cudf_tpch_label, out_root)
    write_manifest(args.manifest_out, fieldnames, updated)
    print(f"memory_trace_manifest={args.manifest_out}")

    if args.activate_main_manifest:
        missing = missing_trace_paths(updated)
        if missing:
            print("not activating; missing trace files:", file=sys.stderr)
            for path in missing[:20]:
                print(f"  {path}", file=sys.stderr)
            if len(missing) > 20:
                print(f"  ... {len(missing) - 20} more", file=sys.stderr)
            return 2
        shutil.copyfile(args.manifest_out, MAIN_TRACE_MANIFEST)
        print(f"activated_main_trace_manifest={MAIN_TRACE_MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

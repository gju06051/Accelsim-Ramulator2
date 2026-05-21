#!/usr/bin/env python3
"""Run and summarize nvCOMP Nsight Compute input-size sweeps."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


DEFAULT_METRICS = [
    "gpu__time_duration.sum",
    "sm__inst_executed.sum",
    "sm__cycles_active.sum",
    "l1tex__t_sectors.sum",
    "l1tex__t_sectors_lookup_hit.sum",
    "l1tex__t_sectors_lookup_miss.sum",
    "lts__t_sectors.sum",
    "lts__t_sectors_lookup_hit.sum",
    "lts__t_sectors_lookup_miss.sum",
    "dram__bytes_read.sum",
    "dram__bytes_write.sum",
]

DEFAULT_CODECS = ["lz4", "snappy", "gdeflate", "deflate", "zstd", "cascaded", "bitcomp", "ans"]
DEFAULT_SIZES = ["1GiB", "2GiB", "4GiB"]

LOCAL_NCU_CANDIDATES = [
    Path("/home/gju06051/workspace/etc/target/linux-desktop-glibc_2_11_3-x64/ncu"),
    Path("/home/gju06051/workspace/nsight_deploy/target/linux-desktop-glibc_2_11_3-x64/ncu"),
]


def parse_size(text: str) -> int:
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
        "t": 1000**4,
        "tb": 1000**4,
        "ti": 1024**4,
        "tib": 1024**4,
    }[unit]
    return value * scale


def detect_nvcomp_root() -> Path | None:
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import pathlib, nvidia.libnvcomp; print(pathlib.Path(nvidia.libnvcomp.__file__).parent)",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None
    root = Path(proc.stdout.strip())
    return root if root.exists() else None


def detect_ncu() -> str:
    for path in LOCAL_NCU_CANDIDATES:
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return "ncu"


def run_command(cmd: list[str], env: dict[str, str], log_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(shlex.quote(part) for part in cmd), flush=True)
    proc = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if log_path is not None:
        log_path.write_text(proc.stdout)
    print(proc.stdout, end="", flush=True)
    return proc


def parse_native_metrics(output: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for token in output.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            if "." in value:
                result[key] = float(value)
            else:
                result[key] = int(value)
        except ValueError:
            pass
    return result


def iter_ncu_rows(csv_path: Path):
    lines = csv_path.read_text(errors="replace").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith('"ID"')), None)
    if header_index is None:
        return
    reader = csv.DictReader(lines[header_index:])
    for row in reader:
        if not row.get("ID"):
            continue
        yield row


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value in ("", "n/a", "N/A"):
        return 0.0
    return float(value.replace(",", ""))


def summarize_ncu(csv_path: Path) -> dict[str, float | int]:
    totals = {
        "kernel_count_all": 0,
        "kernel_count_nvcomp": 0,
        "kernel_time_ns": 0.0,
        "sm_inst": 0.0,
        "sm_cycles_active": 0.0,
        "l1_sectors": 0.0,
        "l1_hit": 0.0,
        "l1_miss": 0.0,
        "l2_sectors": 0.0,
        "l2_hit": 0.0,
        "l2_miss": 0.0,
        "dram_read_bytes": 0.0,
        "dram_write_bytes": 0.0,
    }
    for row in iter_ncu_rows(csv_path):
        totals["kernel_count_all"] += 1
        name = row.get("Kernel Name", "")
        if name.startswith("fill_compressible_bytes") or name.startswith("count_mismatches"):
            continue
        totals["kernel_count_nvcomp"] += 1
        totals["kernel_time_ns"] += as_float(row, "gpu__time_duration.sum")
        totals["sm_inst"] += as_float(row, "sm__inst_executed.sum")
        totals["sm_cycles_active"] += as_float(row, "sm__cycles_active.sum")
        totals["l1_sectors"] += as_float(row, "l1tex__t_sectors.sum")
        totals["l1_hit"] += as_float(row, "l1tex__t_sectors_lookup_hit.sum")
        totals["l1_miss"] += as_float(row, "l1tex__t_sectors_lookup_miss.sum")
        totals["l2_sectors"] += as_float(row, "lts__t_sectors.sum")
        totals["l2_hit"] += as_float(row, "lts__t_sectors_lookup_hit.sum")
        totals["l2_miss"] += as_float(row, "lts__t_sectors_lookup_miss.sum")
        totals["dram_read_bytes"] += as_float(row, "dram__bytes_read.sum")
        totals["dram_write_bytes"] += as_float(row, "dram__bytes_write.sum")
    l1_lookup = totals["l1_hit"] + totals["l1_miss"]
    l2_lookup = totals["l2_hit"] + totals["l2_miss"]
    totals["l1_hit_rate"] = totals["l1_hit"] / l1_lookup if l1_lookup else 0.0
    totals["l2_hit_rate"] = totals["l2_hit"] / l2_lookup if l2_lookup else 0.0
    totals["ipc_active_sm"] = (
        totals["sm_inst"] / totals["sm_cycles_active"] if totals["sm_cycles_active"] else 0.0
    )
    totals["dram_total_bytes"] = totals["dram_read_bytes"] + totals["dram_write_bytes"]
    totals["kernel_time_ms"] = totals["kernel_time_ns"] / 1.0e6
    return totals


def write_summary_csv(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_md(rows: list[dict[str, object]], path: Path) -> None:
    headers = [
        "codec",
        "GiB",
        "ratio",
        "native GiB/s",
        "dram/input",
        "L1 hit",
        "L2 hit",
        "IPC",
        "kernels",
    ]
    lines = [
        "# nvCOMP Nsight Compute Input-Size Ablation",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [
            str(row["codec"]),
            f"{float(row['size_gib']):.0f}",
            f"{float(row.get('ratio', 0.0)):.4f}",
            f"{float(row.get('native_gib_per_s', 0.0)):.2f}",
            f"{float(row.get('dram_bytes_per_input_byte', 0.0)):.2f}x",
            f"{100.0 * float(row.get('l1_hit_rate', 0.0)):.1f}%",
            f"{100.0 * float(row.get('l2_hit_rate', 0.0)):.1f}%",
            f"{float(row.get('ipc_active_sm', 0.0)):.3f}",
            str(row.get("kernel_count_nvcomp", "")),
        ]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(
        [
            "",
            "Notes:",
            "- Nsight Compute rows exclude the benchmark's input-fill and mismatch-check kernels.",
            "- IPC is `sm__inst_executed.sum / sm__cycles_active.sum`, i.e. warp instructions per active SM cycle.",
            "- DRAM/input is `(dram__bytes_read.sum + dram__bytes_write.sum) / input_bytes` for nvCOMP kernels only.",
            "- NCU was run with `--cache-control none` so the profiler does not force cache flushes between replay passes.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", default="gpu_benchmark/benchmarks/prepare/bin/nvcomp_codec_bench")
    parser.add_argument("--out-dir", default="results/nvcomp_ncu_20260521")
    parser.add_argument("--codecs", nargs="+", default=DEFAULT_CODECS)
    parser.add_argument("--sizes", nargs="+", default=DEFAULT_SIZES)
    parser.add_argument("--chunk-size", type=parse_size, default=parse_size("64KiB"))
    parser.add_argument("--iters", type=int, default=1)
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--ncu", default=detect_ncu())
    parser.add_argument("--replay-mode", choices=["kernel", "application"], default="kernel")
    parser.add_argument("--nvcomp-root", default=str(detect_nvcomp_root() or ""))
    parser.add_argument("--native-only", action="store_true")
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--summarize-existing", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    binary = Path(args.binary)
    if not binary.exists():
        raise SystemExit(f"missing binary: {binary}")

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = args.gpu
    if args.nvcomp_root:
        lib64 = str(Path(args.nvcomp_root) / "lib64")
        env["LD_LIBRARY_PATH"] = lib64 + ":" + env.get("LD_LIBRARY_PATH", "")

    rows: list[dict[str, object]] = []
    for codec in args.codecs:
        for size_text in args.sizes:
            size_bytes = parse_size(size_text)
            stem = f"{codec}_{size_bytes}"
            native_log = out_dir / f"{stem}.native.log"
            ncu_csv = out_dir / f"{stem}.ncu.csv"

            native_metrics: dict[str, float] = {}
            if not args.profile_only:
                if args.summarize_existing:
                    if not native_log.exists():
                        continue
                    native_metrics = parse_native_metrics(native_log.read_text(errors="replace"))
                elif args.skip_existing and native_log.exists():
                    native_metrics = parse_native_metrics(native_log.read_text(errors="replace"))
                else:
                    cmd = [
                        str(binary),
                        "--codec",
                        codec,
                        "--bytes",
                        str(size_bytes),
                        "--chunk-size",
                        str(args.chunk_size),
                        "--iters",
                        str(args.iters),
                    ]
                    proc = run_command(cmd, env, native_log)
                    if proc.returncode != 0:
                        print(f"native run failed for {codec} {size_text}", file=sys.stderr)
                        continue
                    native_metrics = parse_native_metrics(proc.stdout)

            ncu_metrics: dict[str, float | int] = {}
            if not args.native_only:
                if args.skip_existing and ncu_csv.exists():
                    ncu_metrics = summarize_ncu(ncu_csv)
                    if not ncu_metrics.get("kernel_count_all"):
                        ncu_metrics = {}
                if args.summarize_existing:
                    if not ncu_csv.exists():
                        continue
                    ncu_metrics = summarize_ncu(ncu_csv)
                    if not ncu_metrics.get("kernel_count_all"):
                        continue
                elif args.skip_existing and ncu_metrics:
                    pass
                else:
                    cmd = [
                        args.ncu,
                        "--target-processes",
                        "all",
                        "--replay-mode",
                        args.replay_mode,
                        "--cache-control",
                        "none",
                        "--csv",
                        "--page",
                        "raw",
                        "--print-units",
                        "base",
                        "--metrics",
                        ",".join(DEFAULT_METRICS),
                        "--log-file",
                        str(ncu_csv),
                        "--force-overwrite",
                        str(binary),
                        "--codec",
                        codec,
                        "--bytes",
                        str(size_bytes),
                        "--chunk-size",
                        str(args.chunk_size),
                        "--iters",
                        str(args.iters),
                    ]
                    proc = run_command(cmd, env)
                    if proc.returncode != 0:
                        print(f"ncu run failed for {codec} {size_text}", file=sys.stderr)
                        continue
                    ncu_metrics = summarize_ncu(ncu_csv)

            row: dict[str, object] = {
                "codec": codec,
                "size_bytes": size_bytes,
                "size_gib": size_bytes / float(1 << 30),
                "chunk_size": args.chunk_size,
                "iters": args.iters,
                "compressed": native_metrics.get("compressed", 0),
                "ratio": native_metrics.get("ratio", 0.0),
                "native_elapsed_ms": native_metrics.get("elapsed_ms", 0.0),
                "native_gib_per_s": native_metrics.get("gib_per_s", 0.0),
                "mismatches": native_metrics.get("mismatches", 0),
            }
            row.update(ncu_metrics)
            if row.get("dram_total_bytes"):
                row["dram_bytes_per_input_byte"] = float(row["dram_total_bytes"]) / float(size_bytes)
            else:
                row["dram_bytes_per_input_byte"] = 0.0
            rows.append(row)
            write_summary_csv(rows, out_dir / "summary.csv")
            write_summary_md(rows, out_dir / "summary.md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run and summarize cuDF Nsight Compute input-size sweeps."""

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

DEFAULT_OPS = ["filter", "project", "groupby", "join", "sort"]
DEFAULT_SIZES = ["2MiB", "4MiB", "8MiB", "16MiB", "32MiB", "64MiB", "128MiB", "256MiB", "512MiB"]
LOCAL_NCU_CANDIDATES = [
    Path("/home/gju06051/workspace/etc/target/linux-desktop-glibc_2_11_3-x64/ncu"),
    Path("/home/gju06051/workspace/nsight_deploy/target/linux-desktop-glibc_2_11_3-x64/ncu"),
]
LOCAL_RAPIDS_PYTHON_CANDIDATES = [
    Path("/home/gju06051/.venvs/rapids-cudf-cu12/bin/python"),
    Path("/home/gju06051/anaconda3/envs/rapids-cudf-cu12/bin/python"),
    Path("/home/gju06051/anaconda3/envs/rapids/bin/python"),
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
    }[unit]
    return value * scale


def detect_ncu() -> str:
    for path in LOCAL_NCU_CANDIDATES:
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return "ncu"


def python_has_cudf(path: str | Path) -> bool:
    try:
        proc = subprocess.run(
            [str(path), "-c", "import cudf"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def detect_rapids_python() -> str:
    env_python = os.environ.get("RAPIDS_PYTHON")
    if env_python and python_has_cudf(env_python):
        return env_python
    if python_has_cudf(sys.executable):
        return sys.executable
    for path in LOCAL_RAPIDS_PYTHON_CANDIDATES:
        if path.exists() and os.access(path, os.X_OK) and python_has_cudf(path):
            return str(path)
    return sys.executable


def run_command(cmd: list[str], env: dict[str, str], log_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(shlex.quote(part) for part in cmd), flush=True)
    proc = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if log_path is not None:
        log_path.write_text(proc.stdout)
    print(proc.stdout, end="", flush=True)
    return proc


def parse_key_values(output: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for token in output.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            result[key] = float(value) if "." in value else int(value)
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
        if row.get("ID"):
            yield row


def value(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    if raw in ("", "n/a", "N/A"):
        return 0.0
    return float(raw.replace(",", ""))


def summarize_ncu(csv_path: Path) -> dict[str, float | int]:
    totals = {
        "kernel_count": 0,
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
        totals["kernel_count"] += 1
        totals["kernel_time_ns"] += value(row, "gpu__time_duration.sum")
        totals["sm_inst"] += value(row, "sm__inst_executed.sum")
        totals["sm_cycles_active"] += value(row, "sm__cycles_active.sum")
        totals["l1_sectors"] += value(row, "l1tex__t_sectors.sum")
        totals["l1_hit"] += value(row, "l1tex__t_sectors_lookup_hit.sum")
        totals["l1_miss"] += value(row, "l1tex__t_sectors_lookup_miss.sum")
        totals["l2_sectors"] += value(row, "lts__t_sectors.sum")
        totals["l2_hit"] += value(row, "lts__t_sectors_lookup_hit.sum")
        totals["l2_miss"] += value(row, "lts__t_sectors_lookup_miss.sum")
        totals["dram_read_bytes"] += value(row, "dram__bytes_read.sum")
        totals["dram_write_bytes"] += value(row, "dram__bytes_write.sum")
    l1_lookup = totals["l1_hit"] + totals["l1_miss"]
    l2_lookup = totals["l2_hit"] + totals["l2_miss"]
    totals["l1_hit_rate"] = totals["l1_hit"] / l1_lookup if l1_lookup else 0.0
    totals["l2_hit_rate"] = totals["l2_hit"] / l2_lookup if l2_lookup else 0.0
    totals["ipc_active_sm"] = totals["sm_inst"] / totals["sm_cycles_active"] if totals["sm_cycles_active"] else 0.0
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
    lines = [
        "# cuDF Nsight Compute Input-Size Ablation",
        "",
        "| op | input | rows | time ms | DRAM/input | read/input | write/input | L1 hit | L2 hit | IPC | kernels |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {op} | {input_mib:.0f}MiB | {rows} | {time:.3f} | {dram:.2f} | {read:.2f} | {write:.2f} | {l1:.1f}% | {l2:.1f}% | {ipc:.3f} | {kernels} |".format(
                op=row["op"],
                input_mib=float(row["target_bytes"]) / float(1 << 20),
                rows=int(float(row.get("rows", 0))),
                time=float(row.get("kernel_time_ms", 0.0)),
                dram=float(row.get("dram_total_per_input", 0.0)),
                read=float(row.get("dram_read_per_input", 0.0)),
                write=float(row.get("dram_write_per_input", 0.0)),
                l1=100.0 * float(row.get("l1_hit_rate", 0.0)),
                l2=100.0 * float(row.get("l2_hit_rate", 0.0)),
                ipc=float(row.get("ipc_active_sm", 0.0)),
                kernels=row.get("kernel_count", 0),
            )
        )
    lines.extend(
        [
            "",
            "Notes:",
            "- NCU is run with `--profile-from-start off`; the benchmark calls `cudaProfilerStart/Stop` around only the cuDF operation.",
            "- Input bytes are the benchmark's logical device-resident input columns, not temporary workspace.",
            "- DRAM/input is `(dram__bytes_read.sum + dram__bytes_write.sum) / input_bytes` for the profiled cuDF operation kernels.",
            "- NCU is run with `--cache-control none` so profiler replay does not force cache flushes.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", default="gpu_benchmark/benchmarks/prepare/cudf/cudf_microbench.py")
    parser.add_argument("--out-dir", default="results/cudf_ncu")
    parser.add_argument("--ops", nargs="+", default=DEFAULT_OPS)
    parser.add_argument("--sizes", nargs="+", default=DEFAULT_SIZES)
    parser.add_argument("--cardinality", type=int, default=65536)
    parser.add_argument("--iters", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--python", default=detect_rapids_python())
    parser.add_argument("--ncu", default=detect_ncu())
    parser.add_argument("--replay-mode", choices=["kernel", "application"], default="kernel")
    parser.add_argument("--native-only", action="store_true")
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--summarize-existing", action="store_true")
    args = parser.parse_args()

    bench = Path(args.bench)
    if not bench.exists():
        raise SystemExit(f"missing benchmark: {bench}")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = args.gpu

    rows: list[dict[str, object]] = []
    for op in args.ops:
        for size_text in args.sizes:
            target_bytes = parse_size(size_text)
            stem = f"{op}_{target_bytes}"
            native_log = out_dir / f"{stem}.native.log"
            ncu_csv = out_dir / f"{stem}.ncu.csv"

            native_metrics: dict[str, float] = {}
            if not args.profile_only:
                if args.summarize_existing or (args.skip_existing and native_log.exists()):
                    if not native_log.exists():
                        continue
                    native_metrics = parse_key_values(native_log.read_text(errors="replace"))
                else:
                    cmd = [
                        args.python,
                        str(bench),
                        "--op",
                        op,
                        "--target-bytes",
                        str(target_bytes),
                        "--cardinality",
                        str(args.cardinality),
                        "--iters",
                        str(args.iters),
                        "--warmup",
                        str(args.warmup),
                    ]
                    proc = run_command(cmd, env, native_log)
                    if proc.returncode != 0:
                        print(f"native run failed for {op} {size_text}", file=sys.stderr)
                        continue
                    native_metrics = parse_key_values(proc.stdout)

            ncu_metrics: dict[str, float | int] = {}
            if not args.native_only:
                if args.summarize_existing or (args.skip_existing and ncu_csv.exists()):
                    if not ncu_csv.exists():
                        continue
                    ncu_metrics = summarize_ncu(ncu_csv)
                    if not ncu_metrics.get("kernel_count"):
                        continue
                else:
                    cmd = [
                        args.ncu,
                        "--target-processes",
                        "all",
                        "--profile-from-start",
                        "off",
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
                        args.python,
                        str(bench),
                        "--op",
                        op,
                        "--target-bytes",
                        str(target_bytes),
                        "--cardinality",
                        str(args.cardinality),
                        "--iters",
                        str(args.iters),
                        "--warmup",
                        str(args.warmup),
                        "--profile-operation-only",
                    ]
                    proc = run_command(cmd, env)
                    if proc.returncode != 0:
                        print(f"ncu run failed for {op} {size_text}", file=sys.stderr)
                        continue
                    ncu_metrics = summarize_ncu(ncu_csv)

            input_bytes = int(native_metrics.get("input_bytes", target_bytes))
            row: dict[str, object] = {
                "op": op,
                "target_bytes": target_bytes,
                "input_bytes": input_bytes,
                "rows": native_metrics.get("rows", 0),
                "cardinality": native_metrics.get("cardinality", args.cardinality),
                "result_rows": native_metrics.get("result_rows", 0),
                "native_elapsed_ms": native_metrics.get("elapsed_ms", 0.0),
                "native_gib_per_s": native_metrics.get("gib_per_s", 0.0),
            }
            row.update(ncu_metrics)
            if row.get("dram_total_bytes") and input_bytes:
                row["dram_read_per_input"] = float(row["dram_read_bytes"]) / float(input_bytes)
                row["dram_write_per_input"] = float(row["dram_write_bytes"]) / float(input_bytes)
                row["dram_total_per_input"] = float(row["dram_total_bytes"]) / float(input_bytes)
            else:
                row["dram_read_per_input"] = 0.0
                row["dram_write_per_input"] = 0.0
                row["dram_total_per_input"] = 0.0
            rows.append(row)
            write_summary_csv(rows, out_dir / "summary.csv")
            write_summary_md(rows, out_dir / "summary.md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

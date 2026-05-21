#!/usr/bin/env python3
"""Run cuDF TPC-H traces through Accel-Sim + Ramulator2 and summarize logs."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ACCEL = Path("/tmp/accel-sim-framework-dev-ramulator/gpu-simulator/bin/release/accel-sim.out")
DEFAULT_BASE_CONFIG = ROOT / "simulator/gpgpu-sim_distribution/configs/tested-cfgs/SM80_A100/gpgpusim.config"
DEFAULT_TRACE_CONFIG = Path("/tmp/accel-sim-framework-dev-ramulator/gpu-simulator/configs/tested-cfgs/SM80_A100/trace.config")
DEFAULT_H100_1STACK = ROOT / "simulator/accelsim_ramulator/configs/accelsim/h100_sxm_hbm3_1stack_16ch.config"
DEFAULT_RAMULATOR = ROOT / "simulator/accelsim_ramulator/configs/ramulator/h100_sxm_hbm3_sid_16ch.yaml"
DEFAULT_BRIDGE = ROOT / "simulator/accelsim_ramulator/build/ramulator2_bridge/libsgram_ramulator2_bridge.so"
DEFAULT_TRACE_ROOT = ROOT / "results/cudf_tpch_accelsim_traces_64MiB_20260521"
DEFAULT_OUT = ROOT / "results/cudf_tpch_accelsim_sim_64MiB_h100_1stack_20260521"


def run(cmd: list[str], cwd: Path, env: dict[str, str], log: Path) -> int:
    print("+ " + " ".join(shlex.quote(part) for part in cmd), flush=True)
    with log.open("w") as file:
        proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=file, stderr=subprocess.STDOUT)
    return proc.returncode


def last_float(lines: list[str], pattern: str) -> float | None:
    value = None
    rx = re.compile(pattern)
    for line in lines:
        match = rx.search(line)
        if match:
            value = float(match.group(1))
    return value


def last_int(lines: list[str], pattern: str) -> int | None:
    value = last_float(lines, pattern)
    return int(value) if value is not None else None


def sum_last_per_index(lines: list[str], prefix: str) -> int:
    values: dict[int, int] = {}
    rx = re.compile(rf"\b{re.escape(prefix)}_(\d+):\s*([0-9]+)")
    for line in lines:
        match = rx.search(line)
        if match:
            values[int(match.group(1))] = int(match.group(2))
    return sum(values.values())


def summarize(log: Path) -> dict[str, object]:
    lines = log.read_text(errors="replace").splitlines()
    metrics: dict[str, object] = {
        "status": "pass" if any("GPGPU-Sim: *** simulation thread exiting ***" in line for line in lines) else "unknown",
        "exit_status": last_int(lines, r"Exit status:\s*([0-9]+)"),
        "elapsed": next((line.split(": ", 1)[1] for line in lines if "Elapsed (wall clock) time" in line), ""),
        "max_rss_kb": last_int(lines, r"Maximum resident set size \(kbytes\):\s*([0-9]+)"),
        "kernels_seen": sum(1 for line in lines if line.startswith("Processing kernel ")),
        "ramulator_backend_partitions": len(
            {
                int(match.group(1))
                for line in lines
                for match in [re.search(r"SGRAM Ramulator2 backend partition (\d+):", line)]
                if match
            }
        ),
        "gpu_tot_sim_cycle": last_int(lines, r"gpu_tot_sim_cycle =\s*([0-9]+)"),
        "gpu_tot_sim_insn": last_int(lines, r"gpu_tot_sim_insn =\s*([0-9]+)"),
        "l2_access": last_int(lines, r"L2_total_cache_accesses =\s*([0-9]+)"),
        "l2_miss": last_int(lines, r"L2_total_cache_misses =\s*([0-9]+)"),
        "l2_miss_rate": last_float(lines, r"L2_total_cache_miss_rate =\s*([0-9.]+)"),
    }

    l2_breakdown = {
        "l2_read_hit": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_R\]\[HIT\] =\s*([0-9]+)") or 0,
        "l2_read_miss": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_R\]\[MISS\] =\s*([0-9]+)") or 0,
        "l2_read_sector_miss": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_R\]\[SECTOR_MISS\] =\s*([0-9]+)") or 0,
        "l2_read_access": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_R\]\[TOTAL_ACCESS\] =\s*([0-9]+)") or 0,
        "l2_write_hit": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_W\]\[HIT\] =\s*([0-9]+)") or 0,
        "l2_write_miss": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_W\]\[MISS\] =\s*([0-9]+)") or 0,
        "l2_write_sector_miss": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_W\]\[SECTOR_MISS\] =\s*([0-9]+)") or 0,
        "l2_write_access": last_int(lines, r"L2_cache_stats_breakdown\[GLOBAL_ACC_W\]\[TOTAL_ACCESS\] =\s*([0-9]+)") or 0,
    }
    metrics.update(l2_breakdown)
    metrics["l2_read_hit_pct"] = 100.0 * l2_breakdown["l2_read_hit"] / l2_breakdown["l2_read_access"] if l2_breakdown["l2_read_access"] else 0.0
    metrics["l2_write_hit_pct"] = 100.0 * l2_breakdown["l2_write_hit"] / l2_breakdown["l2_write_access"] if l2_breakdown["l2_write_access"] else 0.0

    for prefix in [
        "num_read_reqs",
        "num_write_reqs",
        "read_row_hits",
        "write_row_hits",
        "read_row_misses",
        "write_row_misses",
        "read_row_conflicts",
        "write_row_conflicts",
    ]:
        metrics[prefix] = sum_last_per_index(lines, prefix)
    metrics["ram_total_req"] = int(metrics["num_read_reqs"]) + int(metrics["num_write_reqs"])
    metrics["est_dram_mib_32b"] = float(metrics["ram_total_req"]) * 32.0 / (1024.0 * 1024.0)
    row_hits = int(metrics["read_row_hits"]) + int(metrics["write_row_hits"])
    row_misses = int(metrics["read_row_misses"]) + int(metrics["write_row_misses"])
    row_conflicts = int(metrics["read_row_conflicts"]) + int(metrics["write_row_conflicts"])
    row_total = row_hits + row_misses + row_conflicts
    metrics["row_hit_pct"] = 100.0 * row_hits / row_total if row_total else 0.0
    return metrics


def write_summary(query: str, run_dir: Path, metrics: dict[str, object]) -> None:
    ordered = [
        "status",
        "exit_status",
        "elapsed",
        "max_rss_kb",
        "kernels_seen",
        "ramulator_backend_partitions",
        "gpu_tot_sim_cycle",
        "gpu_tot_sim_insn",
        "l2_access",
        "l2_miss",
        "l2_miss_rate",
        "l2_read_access",
        "l2_read_hit",
        "l2_read_hit_pct",
        "l2_write_access",
        "l2_write_hit",
        "l2_write_hit_pct",
        "num_read_reqs",
        "num_write_reqs",
        "ram_total_req",
        "est_dram_mib_32b",
        "row_hit_pct",
        "read_row_hits",
        "read_row_misses",
        "read_row_conflicts",
        "write_row_hits",
        "write_row_misses",
        "write_row_conflicts",
    ]
    with (run_dir / "summary.tsv").open("w") as file:
        file.write("metric\tvalue\n")
        for key in ordered:
            file.write(f"{key}\t{metrics.get(key, '')}\n")

    with (run_dir / "summary.md").open("w") as file:
        file.write(f"# cuDF {query} 64MiB Accel-Sim + Ramulator2 H100 1-stack summary\n\n")
        file.write("| metric | value |\n| --- | ---: |\n")
        for key in ordered:
            value = metrics.get(key, "")
            if isinstance(value, float):
                if key == "l2_miss_rate":
                    text = f"{value * 100.0:.2f}%"
                elif key.endswith("_pct"):
                    text = f"{value:.2f}%"
                else:
                    text = f"{value:.2f}"
            else:
                text = str(value)
            file.write(f"| {key} | {text} |\n")
        file.write("\nConfig: H100 1-stack / 1/5 H100, 26 SM, 16 HBM3 channels, 10 MiB L2.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", nargs="+", default=["q1", "q3", "q6", "q10"])
    parser.add_argument("--size", default="64MiB")
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--accel-sim", type=Path, default=DEFAULT_ACCEL)
    parser.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG)
    parser.add_argument("--h100-config", type=Path, default=DEFAULT_H100_1STACK)
    parser.add_argument("--trace-config", type=Path, default=DEFAULT_TRACE_CONFIG)
    parser.add_argument("--ramulator-config", type=Path, default=DEFAULT_RAMULATOR)
    parser.add_argument("--bridge-lib", type=Path, default=DEFAULT_BRIDGE)
    parser.add_argument("--timeout", default="21600s")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    base_ld = ":".join(
        [
            str(ROOT / "simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release"),
            str(ROOT / "simulator/accelsim_ramulator/build/ramulator2_bridge"),
            str(ROOT / "simulator/ramulator2"),
            os.environ.get("LD_LIBRARY_PATH", ""),
        ]
    )

    rows: list[dict[str, object]] = []
    for query in args.queries:
        trace = args.trace_root / f"cudf_tpch_{query}_{args.size}" / "traces/kernelslist.g"
        if not trace.exists():
            raise SystemExit(f"missing trace for {query}: {trace}")
        run_dir = args.out_dir / f"cudf_tpch_{query}_{args.size}_h100_1stack"
        run_dir.mkdir(parents=True, exist_ok=True)
        log = run_dir / "sim.log"
        if log.exists() and not args.force:
            print(f"skip existing {query}: {log}", flush=True)
        else:
            env = os.environ.copy()
            env.update(
                {
                    "LD_LIBRARY_PATH": base_ld,
                    "SGRAM_BACKEND": "ramulator2",
                    "SGRAM_QUEUE_LIMIT": "128",
                    "SGRAM_RAMULATOR_LIB": str(args.bridge_lib),
                    "SGRAM_RAMULATOR_CONFIG": str(args.ramulator_config),
                    "SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT": "1024",
                    "SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE": "auto",
                    "SGRAM_ACCELSIM_DRAM_FREQ_MHZ": "1309",
                }
            )
            (run_dir / "run_env.txt").write_text(
                "\n".join(
                    [
                        f"query={query}",
                        f"trace={trace}",
                        f"accel_sim={args.accel_sim}",
                        f"base_config={args.base_config}",
                        f"h100_config={args.h100_config}",
                        f"trace_config={args.trace_config}",
                        f"ramulator_config={args.ramulator_config}",
                    ]
                )
                + "\n"
            )
            cmd = [
                "/usr/bin/time",
                "-v",
                "timeout",
                args.timeout,
                str(args.accel_sim),
                "-trace",
                str(trace),
                "-config",
                str(args.base_config),
                "-config",
                str(args.h100_config),
                "-config",
                str(args.trace_config),
            ]
            rc = run(cmd, run_dir, env, log)
            print(f"{query}: rc={rc}", flush=True)
        metrics = summarize(log)
        write_summary(query, run_dir, metrics)
        row = {"query": query, "run_dir": str(run_dir)}
        row.update(metrics)
        rows.append(row)

    keys = [
        "query",
        "status",
        "exit_status",
        "elapsed",
        "kernels_seen",
        "gpu_tot_sim_cycle",
        "gpu_tot_sim_insn",
        "l2_access",
        "l2_miss",
        "l2_miss_rate",
        "num_read_reqs",
        "num_write_reqs",
        "ram_total_req",
        "est_dram_mib_32b",
        "row_hit_pct",
        "run_dir",
    ]
    with (args.out_dir / "summary.tsv").open("w") as file:
        file.write("\t".join(keys) + "\n")
        for row in rows:
            file.write("\t".join(str(row.get(key, "")) for key in keys) + "\n")
    with (args.out_dir / "summary.md").open("w") as file:
        file.write("# cuDF TPC-H 64MiB Accel-Sim + Ramulator2 H100 1-stack summary\n\n")
        file.write("| query | status | elapsed | kernels | cycles | insn | L2 miss rate | DRAM req | est DRAM MiB | row hit | run dir |\n")
        file.write("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n")
        for row in rows:
            file.write(
                "| {query} | {status} | {elapsed} | {kernels_seen} | {cycle} | {insn} | {l2:.2f}% | {req} | {dram:.2f} | {rowhit:.2f}% | {run_dir} |\n".format(
                    query=row["query"],
                    status=row["status"],
                    elapsed=row["elapsed"],
                    kernels_seen=row["kernels_seen"],
                    cycle=row["gpu_tot_sim_cycle"],
                    insn=row["gpu_tot_sim_insn"],
                    l2=float(row["l2_miss_rate"] or 0.0) * 100.0,
                    req=row["ram_total_req"],
                    dram=float(row["est_dram_mib_32b"]),
                    rowhit=float(row["row_hit_pct"]),
                    run_dir=row["run_dir"],
                )
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())

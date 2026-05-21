#!/usr/bin/env python3
"""Summarize nvCOMP NCU CSVs for the compression kernels used in simulation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


# Trace kernel numbers are 1-based. Nsight Compute's CSV "ID" column is 0-based.
COMPRESSION_TRACE_RANGES = {
    "lz4": (3, 3),
    "snappy": (3, 3),
    "cascaded": (3, 3),
    "bitcomp": (3, 3),
    "gdeflate": (3, 5),
    "deflate": (3, 7),
    "zstd": (3, 8),
    "ans": (3, 7),
}

CODECS = ["lz4", "snappy", "gdeflate", "deflate", "zstd", "cascaded", "bitcomp", "ans"]


def parse_size(text: str) -> int:
    units = {
        "b": 1,
        "kib": 1 << 10,
        "mib": 1 << 20,
        "gib": 1 << 30,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
    }
    raw = text.strip().lower()
    for suffix, scale in sorted(units.items(), key=lambda item: len(item[0]), reverse=True):
        if raw.endswith(suffix):
            return int(raw[: -len(suffix)]) * scale
    return int(raw)


def iter_ncu_rows(path: Path):
    lines = path.read_text(errors="replace").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith('"ID"')), None)
    if header_index is None:
        return
    for row in csv.DictReader(lines[header_index:]):
        if row.get("ID"):
            yield row


def parse_native(path: Path) -> dict[str, float]:
    result: dict[str, float] = {}
    if not path.exists():
        return result
    for token in path.read_text(errors="replace").split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            result[key] = float(value)
        except ValueError:
            pass
    return result


def value(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    if raw in ("", "n/a", "N/A"):
        return 0.0
    return float(raw.replace(",", ""))


def summarize_rows(rows: list[dict[str, str]], size: int) -> dict[str, object]:
    total = {
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
    for row in rows:
        total["kernel_time_ns"] += value(row, "gpu__time_duration.sum")
        total["sm_inst"] += value(row, "sm__inst_executed.sum")
        total["sm_cycles_active"] += value(row, "sm__cycles_active.sum")
        total["l1_sectors"] += value(row, "l1tex__t_sectors.sum")
        total["l1_hit"] += value(row, "l1tex__t_sectors_lookup_hit.sum")
        total["l1_miss"] += value(row, "l1tex__t_sectors_lookup_miss.sum")
        total["l2_sectors"] += value(row, "lts__t_sectors.sum")
        total["l2_hit"] += value(row, "lts__t_sectors_lookup_hit.sum")
        total["l2_miss"] += value(row, "lts__t_sectors_lookup_miss.sum")
        total["dram_read_bytes"] += value(row, "dram__bytes_read.sum")
        total["dram_write_bytes"] += value(row, "dram__bytes_write.sum")

    l1_lookup = total["l1_hit"] + total["l1_miss"]
    l2_lookup = total["l2_hit"] + total["l2_miss"]
    total["kernel_time_ms"] = total["kernel_time_ns"] / 1.0e6
    total["ipc_active_sm"] = total["sm_inst"] / total["sm_cycles_active"] if total["sm_cycles_active"] else 0.0
    total["l1_hit_rate"] = total["l1_hit"] / l1_lookup if l1_lookup else 0.0
    total["l2_hit_rate"] = total["l2_hit"] / l2_lookup if l2_lookup else 0.0
    total["dram_total_bytes"] = total["dram_read_bytes"] + total["dram_write_bytes"]
    total["dram_read_per_input"] = total["dram_read_bytes"] / size
    total["dram_write_per_input"] = total["dram_write_bytes"] / size
    total["dram_total_per_input"] = total["dram_total_bytes"] / size
    return total


def format_size(size: int) -> str:
    if size < (1 << 30):
        return f"{size // (1 << 20)} MiB"
    return f"{size / float(1 << 30):.0f} GiB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="results/nvcomp_ncu_20260521")
    parser.add_argument("--codecs", nargs="+", default=CODECS)
    parser.add_argument("--sizes", nargs="+", default=["1GiB", "2GiB", "4GiB"])
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    sizes = [parse_size(size) for size in args.sizes]

    summary_rows: list[dict[str, object]] = []
    per_kernel_rows: list[dict[str, object]] = []

    for codec in args.codecs:
        first, last = COMPRESSION_TRACE_RANGES[codec]
        for size in sizes:
            ncu_path = out_dir / f"{codec}_{size}.ncu.csv"
            if not ncu_path.exists():
                continue
            selected = []
            for row in iter_ncu_rows(ncu_path):
                trace_no = int(row["ID"]) + 1
                if first <= trace_no <= last:
                    selected.append(row)
                    per_kernel_rows.append(
                        {
                            "codec": codec,
                            "size_bytes": size,
                            "size_gib": size / float(1 << 30),
                            "trace_kernel": trace_no,
                            "ncu_id": row["ID"],
                            "kernel_name": row["Kernel Name"],
                            "kernel_time_ms": value(row, "gpu__time_duration.sum") / 1.0e6,
                            "sm_inst": value(row, "sm__inst_executed.sum"),
                            "sm_cycles_active": value(row, "sm__cycles_active.sum"),
                            "ipc_active_sm": (
                                value(row, "sm__inst_executed.sum") / value(row, "sm__cycles_active.sum")
                                if value(row, "sm__cycles_active.sum")
                                else 0.0
                            ),
                            "l1_hit_rate": (
                                value(row, "l1tex__t_sectors_lookup_hit.sum")
                                / (
                                    value(row, "l1tex__t_sectors_lookup_hit.sum")
                                    + value(row, "l1tex__t_sectors_lookup_miss.sum")
                                )
                                if (
                                    value(row, "l1tex__t_sectors_lookup_hit.sum")
                                    + value(row, "l1tex__t_sectors_lookup_miss.sum")
                                )
                                else 0.0
                            ),
                            "l2_hit_rate": (
                                value(row, "lts__t_sectors_lookup_hit.sum")
                                / (
                                    value(row, "lts__t_sectors_lookup_hit.sum")
                                    + value(row, "lts__t_sectors_lookup_miss.sum")
                                )
                                if (
                                    value(row, "lts__t_sectors_lookup_hit.sum")
                                    + value(row, "lts__t_sectors_lookup_miss.sum")
                                )
                                else 0.0
                            ),
                            "dram_read_bytes": value(row, "dram__bytes_read.sum"),
                            "dram_write_bytes": value(row, "dram__bytes_write.sum"),
                        }
                    )
            if not selected:
                continue
            native = parse_native(out_dir / f"{codec}_{size}.native.log")
            row = {
                "codec": codec,
                "size_bytes": size,
                "size_gib": size / float(1 << 30),
                "trace_range": f"{first}-{last}" if first != last else str(first),
                "ncu_id_range": f"{first - 1}-{last - 1}" if first != last else str(first - 1),
                "selected_kernel_count": len(selected),
                "ratio": native.get("ratio", 0.0),
                "native_total_gib_per_s": native.get("gib_per_s", 0.0),
                "kernel_names": " | ".join(row["Kernel Name"] for row in selected),
            }
            row.update(summarize_rows(selected, size))
            summary_rows.append(row)

    if not summary_rows:
        raise SystemExit(f"no matching NCU CSVs found in {out_dir}")

    summary_path = out_dir / "compression_phase_summary.csv"
    with summary_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    per_kernel_path = out_dir / "compression_phase_per_kernel.csv"
    with per_kernel_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(per_kernel_rows[0].keys()))
        writer.writeheader()
        writer.writerows(per_kernel_rows)

    lines = [
        "# nvCOMP Compression-Phase Nsight Compute Summary",
        "",
        "Trace kernel ranges are 1-based. NCU `ID` is 0-based, so trace kernel 3 maps to NCU ID 2.",
        "",
        "| codec | input | trace | kernels | time ms | DRAM/input | DRAM read/input | DRAM write/input | L1 hit | L2 hit | IPC |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| {codec} | {input_size} | {trace} | {kernels} | {time:.3f} | {dram:.2f}x | "
            "{read:.2f}x | {write:.2f}x | {l1:.1f}% | {l2:.1f}% | {ipc:.3f} |".format(
                codec=row["codec"],
                input_size=format_size(int(row["size_bytes"])),
                trace=row["trace_range"],
                kernels=row["selected_kernel_count"],
                time=float(row["kernel_time_ms"]),
                dram=float(row["dram_total_per_input"]),
                read=float(row["dram_read_per_input"]),
                write=float(row["dram_write_per_input"]),
                l1=100.0 * float(row["l1_hit_rate"]),
                l2=100.0 * float(row["l2_hit_rate"]),
                ipc=float(row["ipc_active_sm"]),
            )
        )
    lines.extend(
        [
            "",
            "Raw per-kernel rows are in `compression_phase_per_kernel.csv`.",
        ]
    )
    (out_dir / "compression_phase_summary.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

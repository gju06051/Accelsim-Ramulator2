#!/usr/bin/env python3
"""Replay a prepared Accel-Sim trace from the main benchmark manifest.

The normal AccelSim + Ramulator2 matrix runner creates `gpgpusim.config` in the
per-benchmark run directory and exports the SGRAM/Ramulator environment.  This
helper is used by manifest rows whose real workload must be trace-driven rather
than executed through the CUDA runtime interceptor.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACE_MANIFEST = Path(
    os.environ.get(
        "SGRAM_TRACE_MANIFEST",
        str(ROOT / "gpu_benchmark" / "benchmarks" / "main" / "trace_manifest.tsv"),
    )
)

ACCEL_SIM_CANDIDATES = (
    Path(os.environ.get("SGRAM_ACCELSIM_TRACE_BIN", "")),
    Path(os.environ.get("ACCELSIM_TRACE_BIN", "")),
    Path("/tmp/accel-sim-framework-dev-ramulator/gpu-simulator/bin/release/accel-sim.out"),
    Path("/tmp/accel-sim-framework-dev/gpu-simulator/bin/release/accel-sim.out"),
)
TRACE_CONFIG_CANDIDATES = (
    Path(os.environ.get("SGRAM_ACCELSIM_TRACE_CONFIG", "")),
    Path(os.environ.get("ACCELSIM_TRACE_CONFIG", "")),
    Path("/tmp/accel-sim-framework-dev-ramulator/gpu-simulator/configs/tested-cfgs/SM80_A100/trace.config"),
    Path("/tmp/accel-sim-framework-dev/gpu-simulator/configs/tested-cfgs/SM80_A100/trace.config"),
)


def first_existing(candidates: tuple[Path, ...], label: str) -> Path:
    for candidate in candidates:
        if str(candidate) and candidate.is_file():
            return candidate.resolve()
    raise SystemExit(f"missing {label}; set SGRAM_ACCELSIM_TRACE_BIN or SGRAM_ACCELSIM_TRACE_CONFIG")


def resolve_path(value: str, cwd: Path) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    if path.parts and path.parts[0] == "gpu_benchmark":
        return (ROOT / path).resolve(strict=False)
    candidates = (
        (cwd / path).resolve(strict=False),
        (ROOT / path).resolve(strict=False),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def load_trace_row(manifest: Path, benchmark: str) -> dict[str, str]:
    with manifest.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file, delimiter="\t"):
            if row.get("name") == benchmark:
                return row
    raise SystemExit(f"trace benchmark not found in {manifest}: {benchmark}")


def gpgpusim_option_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("-"):
        return None
    return stripped.split(maxsplit=1)[0]


def collapse_gpgpusim_config(lines: list[str]) -> list[str]:
    last: dict[str, int] = {}
    for index, line in enumerate(lines):
        key = gpgpusim_option_key(line)
        if key:
            last[key] = index
    return [
        line
        for index, line in enumerate(lines)
        if not ((key := gpgpusim_option_key(line)) and last[key] != index)
    ]


def prepare_trace_config(base_config: Path, trace_sm: str, write_file: bool = True) -> Path:
    if not trace_sm:
        return base_config

    normalized = trace_sm.strip().lower()
    if normalized in {"", "base", "native", "none"}:
        return base_config

    try:
        sm = int(normalized)
    except ValueError as exc:
        raise SystemExit(f"invalid trace_sm value: {trace_sm}") from exc

    text = base_config.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    if text and not text.endswith("\n"):
        lines.append("\n")
    lines.extend(
        [
            "\n# Trace ISA compatibility overrides\n",
            f"-gpgpu_ptx_force_max_capability {sm}\n",
            f"-gpgpu_occupancy_sm_number {sm}\n",
            f"-gpgpu_coalesce_arch {sm}\n",
        ]
    )
    trace_config = base_config.with_name("gpgpusim.trace.config")
    if write_file:
        trace_config.write_text("".join(collapse_gpgpusim_config(lines)), encoding="utf-8")
    return trace_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default="", help="Benchmark name in trace_manifest.tsv.")
    parser.add_argument("--trace", type=Path, default=None, help="Direct path to kernelslist.g.")
    parser.add_argument("--trace-sm", default="", help="Trace ISA SM override, e.g. 80 or 86.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_TRACE_MANIFEST)
    parser.add_argument("--gpgpusim-config", type=Path, default=Path("gpgpusim.config"))
    parser.add_argument("--trace-config", type=Path, default=None)
    parser.add_argument("--accel-sim", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cwd = Path.cwd()
    manifest = resolve_path(str(args.manifest), cwd)
    trace_sm = args.trace_sm
    trace_path: Path
    row: dict[str, str] = {}

    if args.benchmark:
        row = load_trace_row(manifest, args.benchmark)
        trace_path = resolve_path(row["trace_path"], cwd)
        trace_sm = trace_sm or row.get("trace_sm", "")
        if not args.trace_config and row.get("trace_config"):
            args.trace_config = resolve_path(row["trace_config"], cwd)
    elif args.trace:
        trace_path = resolve_path(str(args.trace), cwd)
    else:
        raise SystemExit("use --benchmark or --trace")

    accel_sim = args.accel_sim.resolve() if args.accel_sim else first_existing(ACCEL_SIM_CANDIDATES, "accel-sim.out")
    trace_config = args.trace_config.resolve() if args.trace_config else first_existing(TRACE_CONFIG_CANDIDATES, "trace.config")
    gpgpusim_config = resolve_path(str(args.gpgpusim_config), cwd)

    missing = [path for path in (trace_path, accel_sim, trace_config, gpgpusim_config) if not path.exists()]
    if missing:
        for path in missing:
            print(f"missing required trace replay file: {path}", file=sys.stderr)
        return 2

    effective_gpgpusim_config = prepare_trace_config(
        gpgpusim_config, trace_sm, write_file=not args.dry_run
    )
    cmd = [
        str(accel_sim),
        "-trace",
        str(trace_path),
        "-config",
        str(effective_gpgpusim_config),
        "-config",
        str(trace_config),
    ]

    print(f"trace_replay_benchmark={args.benchmark or trace_path.stem}", flush=True)
    print(f"trace_replay_trace={trace_path}", flush=True)
    print(f"trace_replay_sm={trace_sm or 'base'}", flush=True)
    print(f"trace_replay_config={effective_gpgpusim_config}", flush=True)
    if row.get("source"):
        print(f"trace_replay_source={row['source']}", flush=True)
    if args.dry_run:
        print("trace_replay_command=" + " ".join(cmd), flush=True)
        return 0
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

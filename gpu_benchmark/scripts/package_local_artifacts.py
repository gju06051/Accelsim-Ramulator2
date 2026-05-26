#!/usr/bin/env python3
"""Package local, git-ignored benchmark artifacts for another clone.

The benchmark manifests intentionally keep large graph inputs, prepared
Accel-Sim traces, reference PDFs, and run results out of Git.  This helper
creates a repo-relative tar bundle that can be extracted at the root of a fresh
clone without hand-picking scattered directories.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Artifact:
    path: str
    note: str


GRAPH_MAIN = (
    Artifact("gpu_benchmark/suites/graphBIG/dataset/LDBC_100k", "GraphBIG main input"),
    Artifact(
        "gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/"
        "lonestargpu-2.0/inputs/rmat16.sym.gr",
        "Lonestar main RMAT16 input",
    ),
)

TRACE_DEFAULT = (
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/accelsim_trace_runtime",
        "Trace replay accel-sim.out and trace.config runtime",
    ),
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/nvcomp_accelsim_ramulator_traces_comp",
        "Default nvCOMP Accel-Sim traces",
    ),
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/cudf_accelsim_traces_1MiB_20260521",
        "Default cuDF micro traces",
    ),
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/cudf_tpch_accelsim_traces_64MiB_20260521",
        "Default cuDF TPC-H-shaped traces",
    ),
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/tango_h100_1stack_validation_sm86_20260522",
        "Default Tango SM86 validation traces",
    ),
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/tango_large_h100_1stack_validation_sm86_20260522",
        "Default Tango AlexNet SM86 validation trace",
    ),
)

TRACE_MEMORY = (
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/nvcomp_accelsim_traces_4MiB",
        "Memory-intensive nvCOMP traces",
    ),
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/cudf_accelsim_traces_64MiB",
        "Memory-intensive cuDF micro traces",
    ),
    Artifact(
        "gpu_benchmark/benchmarks/prepare/results/cudf_tpch_accelsim_traces_128MiB",
        "Memory-intensive cuDF TPC-H-shaped traces",
    ),
)

LARGE_GRAPHS = (
    Artifact("gpu_benchmark/suites/graphBIG/dataset/LDBC_1000k", "Large GraphBIG input"),
    Artifact(
        "gpu_benchmark/common/gpu-app-collection-harness/data_dirs/cuda/"
        "lonestargpu-2.0/inputs/rmat20.sym.gr",
        "Large Lonestar RMAT20 input",
    ),
)

GROUPS: dict[str, tuple[Artifact, ...]] = {
    "main-minimal": GRAPH_MAIN + TRACE_DEFAULT,
    "graphs-main": GRAPH_MAIN,
    "trace-default": TRACE_DEFAULT,
    "trace-memory": TRACE_MEMORY,
    "large-graphs": LARGE_GRAPHS,
    "docs": (Artifact("docs", "Local reference PDFs"),),
    "prepare-bin": (Artifact("gpu_benchmark/benchmarks/prepare/bin", "Optional prepared binaries"),),
    "run-results": (Artifact("simulator/accelsim_ramulator/results", "Local simulation results"),),
}

ALIASES: dict[str, tuple[str, ...]] = {
    "all-inputs": ("main-minimal", "trace-memory", "large-graphs"),
    "all-local": ("main-minimal", "trace-memory", "large-graphs", "docs", "prepare-bin"),
}


def run(cmd: list[str], dry_run: bool = False) -> None:
    print("+ " + " ".join(cmd), flush=True)
    if not dry_run:
        subprocess.run(cmd, check=True)


def split_group_arg(values: list[str]) -> list[str]:
    groups: list[str] = []
    for value in values:
        groups.extend(part.strip() for part in value.split(",") if part.strip())
    return groups


def expand_groups(group_args: list[str]) -> list[str]:
    expanded: list[str] = []
    for group in group_args:
        if group in ALIASES:
            expanded.extend(ALIASES[group])
        else:
            expanded.append(group)

    unknown = sorted({group for group in expanded if group not in GROUPS})
    if unknown:
        valid = sorted(set(GROUPS) | set(ALIASES))
        raise SystemExit(f"unknown group(s): {', '.join(unknown)}; valid: {', '.join(valid)}")
    return expanded


def collect_artifacts(groups: list[str]) -> list[Artifact]:
    seen: set[str] = set()
    artifacts: list[Artifact] = []
    for group in groups:
        for artifact in GROUPS[group]:
            if artifact.path in seen:
                continue
            seen.add(artifact.path)
            artifacts.append(artifact)
    return artifacts


def artifact_status(artifact: Artifact, root: Path) -> tuple[Path, bool]:
    path = root / artifact.path
    return path, path.exists()


def du(path: Path) -> str:
    try:
        completed = subprocess.run(
            ["du", "-sh", str(path)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return "?"
    return completed.stdout.split(maxsplit=1)[0]


def print_artifacts(artifacts: list[Artifact], root: Path) -> list[Artifact]:
    missing: list[Artifact] = []
    for artifact in artifacts:
        path, exists = artifact_status(artifact, root)
        state = "ok" if exists else "missing"
        size = du(path) if exists else "-"
        print(f"{state:7} {size:>8}  {artifact.path}  # {artifact.note}")
        if not exists:
            missing.append(artifact)
    return missing


def ensure_parent(path: Path, dry_run: bool) -> None:
    print(f"+ mkdir -p {path.parent}")
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)


def command_pack(args: argparse.Namespace) -> int:
    groups = expand_groups(split_group_arg(args.group or ["main-minimal"]))
    artifacts = collect_artifacts(groups)
    missing = print_artifacts(artifacts, args.root)
    if missing and not args.allow_missing:
        raise SystemExit("missing artifact(s); use --allow-missing to package the available subset")

    selected = [artifact.path for artifact in artifacts if (args.root / artifact.path).exists()]
    if not selected:
        raise SystemExit("no artifacts to package")

    output = args.output.resolve()
    ensure_parent(output, args.dry_run)
    tar_cmd = ["tar", "-cf", str(output), "-C", str(args.root), *selected]
    run(tar_cmd, args.dry_run)
    return 0


def command_unpack(args: argparse.Namespace) -> int:
    destination = args.destination.resolve()
    if not args.archive.is_file():
        raise SystemExit(f"archive not found: {args.archive}")
    run(["tar", "-xf", str(args.archive.resolve()), "-C", str(destination)], args.dry_run)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    groups = expand_groups(split_group_arg(args.group or ["main-minimal"]))
    missing = print_artifacts(collect_artifacts(groups), args.root)
    return 1 if missing else 0


def command_list(_: argparse.Namespace) -> int:
    print("Groups:")
    for name in sorted(GROUPS):
        print(f"  {name}")
        for artifact in GROUPS[name]:
            print(f"    {artifact.path}  # {artifact.note}")
    print("\nAliases:")
    for name in sorted(ALIASES):
        print(f"  {name}: {', '.join(ALIASES[name])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    pack = subparsers.add_parser("pack", help="Create a tar archive from selected artifact groups.")
    pack.add_argument(
        "--group",
        action="append",
        default=[],
        help="Artifact group or comma-separated groups. Default: main-minimal.",
    )
    pack.add_argument("--output", type=Path, required=True, help="Output tar path.")
    pack.add_argument("--allow-missing", action="store_true", help="Skip missing paths.")
    pack.add_argument("--dry-run", action="store_true", help="Print commands without running tar.")
    pack.set_defaults(func=command_pack)

    unpack = subparsers.add_parser("unpack", help="Extract a previously created bundle.")
    unpack.add_argument("archive", type=Path)
    unpack.add_argument(
        "--destination",
        "-C",
        type=Path,
        default=ROOT,
        help="Destination clone root. Default: current repository root.",
    )
    unpack.add_argument("--dry-run", action="store_true")
    unpack.set_defaults(func=command_unpack)

    verify = subparsers.add_parser("verify", help="Check whether selected artifacts exist.")
    verify.add_argument(
        "--group",
        action="append",
        default=[],
        help="Artifact group or comma-separated groups. Default: main-minimal.",
    )
    verify.set_defaults(func=command_verify)

    list_cmd = subparsers.add_parser("list", help="List artifact groups.")
    list_cmd.set_defaults(func=command_list)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.root = args.root.resolve()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

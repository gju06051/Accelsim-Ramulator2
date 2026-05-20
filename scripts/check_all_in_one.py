#!/usr/bin/env python3
"""Validate the StackGanged all-in-one artifact layout."""

from __future__ import annotations

import csv
import os
import shlex
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "simulator" / "accelsim_ramulator" / "benchmarks" / "operational_manifest.tsv"
GPU_APP_BIN = ROOT / "gpu_benchmark" / "common" / "gpu-app-collection-harness" / "bin" / "12.3" / "release"


def resolve_workspace_path(path_arg: Path) -> Path:
    if path_arg.is_absolute():
        return path_arg
    if path_arg.parts and path_arg.parts[0] == "gpu_benchmark":
        return ROOT / path_arg
    return ROOT / path_arg


def resolve_executable(command0: str, workdir: str) -> Path:
    path = Path(command0)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "gpu_benchmark":
        return resolve_workspace_path(path)
    if path.parent != Path("."):
        if workdir and workdir != ".":
            path = Path(workdir) / path
        return resolve_workspace_path(path)
    return GPU_APP_BIN / path


def main() -> int:
    if not MANIFEST.exists():
        print(f"missing manifest: {MANIFEST}", file=sys.stderr)
        return 2

    missing: list[tuple[str, str, Path]] = []
    rows = list(csv.DictReader(MANIFEST.open("r", encoding="utf-8"), delimiter="\t"))
    for row in rows:
        tokens = shlex.split(row["command"])
        exe = resolve_executable(tokens[0], row.get("workdir", "."))
        if not exe.exists():
            missing.append((row["name"], "exe", exe))
        for token in tokens[1:]:
            for item in token.split(","):
                if not item.startswith("gpu_benchmark/"):
                    continue
                path = ROOT / item
                if not path.exists():
                    missing.append((row["name"], "arg", path))

    print(f"root={ROOT}")
    print(f"manifest={MANIFEST}")
    print(f"benchmarks={len(rows)}")
    print(f"class_counts={dict(Counter(row['expected_class'] for row in rows))}")
    print(f"suite_counts={dict(Counter(row['suite'] for row in rows))}")
    print(f"workspace_env=SGRAM_WORKSPACE_ROOT={ROOT}")

    if missing:
        print("missing referenced files:", file=sys.stderr)
        for bench, kind, path in missing[:100]:
            print(f"  {bench} {kind}: {path}", file=sys.stderr)
        return 1

    print("referenced_files=OK")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())

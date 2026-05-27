#!/usr/bin/env python3
"""Generate Accel-Sim NVBit traces for official-derived memory proxy rows."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "gpu_benchmark" / "benchmarks" / "prepare" / "official_memory_manifest.tsv"
DEFAULT_BINARY = ROOT / "gpu_benchmark" / "benchmarks" / "prepare" / "bin" / "official_memory_proxy"
DEFAULT_OUT_DIR = (
    ROOT / "gpu_benchmark" / "benchmarks" / "prepare" / "results" / "official_memory_accelsim_traces"
)
DEFAULT_TRACE_MANIFEST_OUT = (
    ROOT / "gpu_benchmark" / "benchmarks" / "main" / "trace_manifest.official_memory.tsv"
)
TRACER_ROOT_CANDIDATES = (
    Path("/tmp/accel-sim-framework-dev/util/tracer_nvbit/tracer_tool"),
    Path("/tmp/accel-sim-framework-dev-ramulator/util/tracer_nvbit/tracer_tool"),
    Path("/tmp/accel-sim-framework/util/tracer_nvbit/tracer_tool"),
)


def repo_path(path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path
    return ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT))
    except ValueError:
        return str(path.resolve(strict=False))


def detect_tracer_tool() -> Path:
    env_tool = os.environ.get("ACCELSIM_TRACER_TOOL")
    if env_tool:
        path = Path(env_tool).expanduser()
        if path.exists():
            return path
    for root in TRACER_ROOT_CANDIDATES:
        path = root / "tracer_tool.so"
        if path.exists():
            return path
    return TRACER_ROOT_CANDIDATES[0] / "tracer_tool.so"


def postprocess_binary_for(tracer_tool: Path) -> Path:
    env_post = os.environ.get("ACCELSIM_TRACE_POSTPROCESS")
    if env_post:
        return Path(env_post).expanduser()
    return tracer_tool.parent / "traces-processing" / "post-traces-processing"


def load_rows(manifest: Path) -> list[dict[str, str]]:
    with manifest.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def select_rows(rows: list[dict[str, str]], names: list[str]) -> list[dict[str, str]]:
    if not names:
        return rows
    by_name = {row["name"]: row for row in rows}
    missing = [name for name in names if name not in by_name]
    if missing:
        raise SystemExit(f"benchmark(s) not found: {', '.join(missing)}")
    return [by_name[name] for name in names]


def run_command(cmd: list[str], env: dict[str, str], log_path: Path) -> subprocess.CompletedProcess[str]:
    rendered = "+ " + " ".join(shlex.quote(part) for part in cmd)
    print(rendered, flush=True)
    proc = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log_path.write_text(rendered + "\n" + proc.stdout)
    print(proc.stdout, end="", flush=True)
    return proc


def find_single(pattern: str, root: Path) -> Path:
    matches = sorted(root.glob(pattern))
    if not matches:
        raise SystemExit(f"missing expected trace file matching {root / pattern}")
    return matches[0]


def command_for_row(binary: Path, row: dict[str, str]) -> list[str]:
    parts = shlex.split(row["command"])
    if not parts:
        raise SystemExit(f"empty command for benchmark: {row['name']}")
    return [str(binary), *parts[1:]]


def write_trace_manifest(rows: list[dict[str, str]], out_dir: Path, manifest_out: Path) -> None:
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    with manifest_out.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter="\t", lineterminator="\n")
        writer.writerow(["name", "trace_path", "trace_sm", "trace_config", "source"])
        for row in rows:
            trace_path = out_dir / row["name"] / "traces" / "kernelslist.g"
            writer.writerow(
                [
                    row["name"],
                    repo_relative(trace_path),
                    "80",
                    "",
                    "Official-derived DLRM/GNN/CORAL2 proxy trace",
                ]
            )
    print(f"trace_manifest={manifest_out}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--benchmark",
        action="append",
        default=[],
        help="Benchmark name to trace. Repeat to trace a subset. Default: all rows.",
    )
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--tracer-tool", type=Path, default=detect_tracer_tool())
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_TRACE_MANIFEST_OUT)
    parser.add_argument("--skip-manifest-out", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-postprocess", action="store_true")
    parser.add_argument(
        "--kernel-range",
        default="1",
        help=(
            "Dynamic Accel-Sim tracer kernel range. The proxy initializes inputs "
            "on the host, so launch 1 is the benchmark kernel for the promoted rows."
        ),
    )
    args = parser.parse_args()

    manifest = repo_path(args.manifest)
    binary = repo_path(args.binary)
    out_dir = repo_path(args.out_dir)
    tracer_tool = args.tracer_tool.expanduser()
    manifest_out = repo_path(args.manifest_out)

    if not manifest.is_file():
        raise SystemExit(f"missing manifest: {manifest}")
    if not binary.is_file():
        raise SystemExit(f"missing official memory proxy binary: {binary}")
    if not tracer_tool.is_file():
        raise SystemExit(f"missing Accel-Sim tracer tool: {tracer_tool}")
    postprocess = postprocess_binary_for(tracer_tool)
    if not args.no_postprocess and not postprocess.is_file():
        raise SystemExit(f"missing post-traces-processing binary: {postprocess}")

    selected = select_rows(load_rows(manifest), args.benchmark)
    out_dir.mkdir(parents=True, exist_ok=True)

    for row in selected:
        name = row["name"]
        case_dir = out_dir / name
        if case_dir.exists() and any(case_dir.iterdir()):
            if not args.force:
                raise SystemExit(f"trace directory already exists, use --force: {case_dir}")
            shutil.rmtree(case_dir)
        case_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.pop("LD_PRELOAD", None)
        env["CUDA_INJECTION64_PATH"] = str(tracer_tool)
        env["ACK_CTX_INIT_LIMITATION"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = args.gpu
        env["USER_DEFINED_FOLDERS"] = "1"
        env["TRACES_FOLDER"] = str(case_dir)
        env["TOOL_COMPRESS"] = "1"
        env["TRACE_FILE_COMPRESS"] = "1"
        env["ACTIVE_FROM_START"] = "1"
        env["DYNAMIC_KERNEL_RANGE"] = str(args.kernel_range)
        env.setdefault("NOBANNER", "1")

        cmd = command_for_row(binary, row)
        proc = run_command(cmd, env, case_dir / "run.log")
        if proc.returncode != 0:
            return proc.returncode

        traces_dir = case_dir / "traces"
        kernelslist = find_single("kernelslist_ctx_*", traces_dir)
        stats = find_single("stats_ctx_*", traces_dir)
        kernelslist_g = None
        if not args.no_postprocess:
            post_proc = run_command([str(postprocess), str(kernelslist)], env, case_dir / "postprocess.log")
            if post_proc.returncode != 0:
                return post_proc.returncode
            kernelslist_g = traces_dir / "kernelslist.g"

        metadata = {
            "name": name,
            "suite": row.get("suite", ""),
            "expected_class": row.get("expected_class", ""),
            "source_command": row["command"],
            "trace_command": cmd,
            "main_reason": row.get("main_reason", ""),
            "gpu": args.gpu,
            "tracer_tool": str(tracer_tool),
            "postprocess": str(postprocess),
            "kernel_range": str(args.kernel_range),
            "case_dir": str(case_dir),
            "kernelslist": str(kernelslist),
            "stats": str(stats),
            "kernelslist_g": str(kernelslist_g) if kernelslist_g else "",
        }
        (case_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

        print(f"trace_dir={case_dir}")
        print(f"kernelslist={kernelslist}")
        if kernelslist_g:
            print(f"kernelslist_g={kernelslist_g}")
        print(f"stats={stats}")

    if not args.skip_manifest_out:
        write_trace_manifest(selected, out_dir, manifest_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

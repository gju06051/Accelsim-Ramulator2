#!/usr/bin/env python3
"""Generate Accel-Sim NVBit traces for profiler-scoped cuDF workloads."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


OPS = ("filter", "project", "groupby", "join", "sort")
TPCH_QUERIES = ("q1", "q3", "q6", "q10")
LOCAL_RAPIDS_PYTHON_CANDIDATES = [
    Path("/home/gju06051/.venvs/rapids-cudf-cu12/bin/python"),
    Path("/home/gju06051/anaconda3/envs/rapids-cudf-cu12/bin/python"),
    Path("/home/gju06051/anaconda3/envs/rapids/bin/python"),
]
TRACER_ROOT_CANDIDATES = [
    Path("/tmp/accel-sim-framework-dev/util/tracer_nvbit/tracer_tool"),
    Path("/tmp/accel-sim-framework-dev-ramulator/util/tracer_nvbit/tracer_tool"),
    Path("/tmp/accel-sim-framework/util/tracer_nvbit/tracer_tool"),
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


def format_size(size: int) -> str:
    for suffix, scale in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if size % scale == 0:
            return f"{size // scale}{suffix}"
    return f"{size}B"


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


def detect_tracer_tool() -> Path:
    env_tool = os.environ.get("ACCELSIM_TRACER_TOOL")
    if env_tool:
        path = Path(env_tool)
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
        return Path(env_post)
    return tracer_tool.parent / "traces-processing" / "post-traces-processing"


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", choices=("micro", "tpch"), default="micro")
    parser.add_argument("--bench")
    parser.add_argument("--out-dir", default="results/cudf_accelsim_traces")
    parser.add_argument("--op", choices=OPS)
    parser.add_argument("--query", choices=TPCH_QUERIES)
    parser.add_argument("--size", type=parse_size, default=parse_size("1MiB"))
    parser.add_argument("--cardinality", type=int, default=65536)
    parser.add_argument("--iters", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--python", default=detect_rapids_python())
    parser.add_argument("--tracer-tool", type=Path, default=detect_tracer_tool())
    parser.add_argument("--name")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-postprocess", action="store_true")
    parser.add_argument(
        "--kernel-range",
        help=(
            "Fallback dynamic kernel range. If set, tracing starts from process start "
            "and the benchmark does not call cudaProfilerStart/Stop."
        ),
    )
    args = parser.parse_args()

    if args.workload == "micro":
        if args.op is None:
            raise SystemExit("--op is required for --workload micro")
        bench = Path(args.bench or "gpu_benchmark/benchmarks/prepare/cudf/cudf_microbench.py")
    else:
        if args.query is None:
            raise SystemExit("--query is required for --workload tpch")
        bench = Path(args.bench or "gpu_benchmark/benchmarks/prepare/cudf/cudf_tpch_bench.py")

    if not bench.exists():
        raise SystemExit(f"missing benchmark: {bench}")
    tracer_tool = args.tracer_tool
    if not tracer_tool.exists():
        raise SystemExit(f"missing Accel-Sim tracer tool: {tracer_tool}")
    postprocess = postprocess_binary_for(tracer_tool)
    if not args.no_postprocess and not postprocess.exists():
        raise SystemExit(f"missing post-traces-processing binary: {postprocess}")

    size_label = format_size(args.size)
    workload_name = args.op if args.workload == "micro" else f"tpch_{args.query}"
    name = args.name or f"cudf_{workload_name}_{size_label}"
    case_dir = Path(args.out_dir) / name
    if case_dir.exists() and any(case_dir.iterdir()):
        if not args.force:
            raise SystemExit(f"trace directory already exists, use --force: {case_dir}")
        subprocess.run(["rm", "-rf", str(case_dir)], check=True)
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
    env.setdefault("NOBANNER", "1")

    cmd = [args.python, str(bench)]
    if args.workload == "micro":
        cmd.extend(
            [
                "--op",
                str(args.op),
                "--target-bytes",
                str(args.size),
                "--cardinality",
                str(args.cardinality),
                "--iters",
                str(args.iters),
                "--warmup",
                str(args.warmup),
            ]
        )
        profile_flag = "--profile-operation-only"
    else:
        cmd.extend(
            [
                "--query",
                str(args.query),
                "--target-bytes",
                str(args.size),
                "--iters",
                str(args.iters),
                "--warmup",
                str(args.warmup),
            ]
        )
        profile_flag = "--profile-query-only"
    if args.kernel_range:
        env["ACTIVE_FROM_START"] = "1"
        env["DYNAMIC_KERNEL_RANGE"] = args.kernel_range
    else:
        env["ACTIVE_FROM_START"] = "0"
        cmd.append(profile_flag)

    proc = run_command(cmd, env, case_dir / "run.log")
    if proc.returncode != 0:
        return proc.returncode

    traces_dir = case_dir / "traces"
    kernelslist = find_single("kernelslist_ctx_*", traces_dir)
    stats = find_single("stats_ctx_*", traces_dir)
    kernelslist_g = None
    if not args.no_postprocess:
        post_cmd = [str(postprocess), str(kernelslist)]
        post_proc = run_command(post_cmd, env, case_dir / "postprocess.log")
        if post_proc.returncode != 0:
            return post_proc.returncode
        kernelslist_g = traces_dir / "kernelslist.g"

    metadata = {
        "name": name,
        "workload": args.workload,
        "op": args.op or "",
        "query": args.query or "",
        "size_bytes": args.size,
        "size": size_label,
        "cardinality": args.cardinality,
        "iters": args.iters,
        "warmup": args.warmup,
        "gpu": args.gpu,
        "python": args.python,
        "tracer_tool": str(tracer_tool),
        "postprocess": str(postprocess),
        "profile_scoped": not bool(args.kernel_range),
        "kernel_range": args.kernel_range or "",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

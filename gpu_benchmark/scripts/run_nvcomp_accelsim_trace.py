#!/usr/bin/env python3
"""Generate Accel-Sim NVBit traces for nvCOMP codec workloads."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


CODECS = ("lz4", "snappy", "gdeflate", "deflate", "zstd", "cascaded", "bitcomp", "ans")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINARY = ROOT / "gpu_benchmark" / "benchmarks" / "prepare" / "bin" / "nvcomp_codec_bench"
DEFAULT_OUT_DIR = ROOT / "gpu_benchmark" / "benchmarks" / "prepare" / "results" / "nvcomp_accelsim_traces"
LOCAL_TRACER_ROOT_CANDIDATES = [
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
        "t": 1000**4,
        "tb": 1000**4,
        "ti": 1024**4,
        "tib": 1024**4,
    }[unit]
    return value * scale


def format_size(size: int) -> str:
    for suffix, scale in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if size % scale == 0:
            return f"{size // scale}{suffix}"
    return f"{size}B"


def detect_nvcomp_root() -> Path | None:
    env_root = os.environ.get("NVCOMP_ROOT")
    if env_root:
        path = Path(env_root).expanduser()
        if path.exists():
            return path
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


def detect_tracer_tool() -> Path:
    env_tool = os.environ.get("ACCELSIM_TRACER_TOOL")
    if env_tool:
        path = Path(env_tool)
        if path.exists():
            return path
    for root in LOCAL_TRACER_ROOT_CANDIDATES:
        path = root / "tracer_tool.so"
        if path.exists():
            return path
    return LOCAL_TRACER_ROOT_CANDIDATES[0] / "tracer_tool.so"


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
    parser.add_argument("--binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--codec", choices=CODECS, required=True)
    parser.add_argument("--bytes", type=parse_size, default=parse_size("64MiB"))
    parser.add_argument("--chunk-size", type=parse_size, default=parse_size("64KiB"))
    parser.add_argument("--iters", type=int, default=1)
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--nvcomp-root", type=Path, default=detect_nvcomp_root())
    parser.add_argument("--tracer-tool", type=Path, default=detect_tracer_tool())
    parser.add_argument("--name")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-postprocess", action="store_true")
    parser.add_argument(
        "--kernel-range",
        default="3",
        help=(
            "Dynamic Accel-Sim tracer kernel range. The local nvCOMP wrapper's "
            "compression kernel is launch 3 for the validated LZ4 flow."
        ),
    )
    args = parser.parse_args()

    binary = args.binary
    if not binary.exists():
        raise SystemExit(f"missing nvCOMP benchmark binary: {binary}")
    tracer_tool = args.tracer_tool
    if not tracer_tool.exists():
        raise SystemExit(f"missing Accel-Sim tracer tool: {tracer_tool}")
    postprocess = postprocess_binary_for(tracer_tool)
    if not args.no_postprocess and not postprocess.exists():
        raise SystemExit(f"missing post-traces-processing binary: {postprocess}")
    if args.iters <= 0:
        raise SystemExit("--iters must be positive")
    if args.bytes <= 0 or args.chunk_size <= 0:
        raise SystemExit("--bytes and --chunk-size must be positive")

    size_label = format_size(args.bytes)
    name = args.name or f"nvcomp_{args.codec}_{size_label}"
    case_dir = args.out_dir / name
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
    env["ACTIVE_FROM_START"] = "1"
    env["DYNAMIC_KERNEL_RANGE"] = str(args.kernel_range)
    env.setdefault("NOBANNER", "1")
    if args.nvcomp_root:
        env["NVCOMP_ROOT"] = str(args.nvcomp_root)
        lib64 = args.nvcomp_root / "lib64"
        env["LD_LIBRARY_PATH"] = str(lib64) + ":" + env.get("LD_LIBRARY_PATH", "")

    cmd = [
        str(binary),
        "--codec",
        args.codec,
        "--bytes",
        str(args.bytes),
        "--chunk-size",
        str(args.chunk_size),
        "--iters",
        str(args.iters),
    ]
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
        "codec": args.codec,
        "size_bytes": args.bytes,
        "size": size_label,
        "chunk_size": args.chunk_size,
        "chunk_size_label": format_size(args.chunk_size),
        "iters": args.iters,
        "gpu": args.gpu,
        "binary": str(binary),
        "nvcomp_root": str(args.nvcomp_root) if args.nvcomp_root else "",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

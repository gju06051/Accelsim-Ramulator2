#!/usr/bin/env python3
"""Small RAPIDS cuDF operation benchmark with profiler-scoped GPU work."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import math
import os
import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np


ROW_BYTES = 16
DEFAULT_CARDINALITY = 65536
OPS = ("filter", "project", "groupby", "join", "sort")


def cuda_runtime_library_candidates() -> list[str]:
    site_root = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    return [
        str(path)
        for path in site_root.glob("nvidia/cuda_runtime/lib/libcudart.so*")
        if path.is_file()
    ]


def parse_size(text: str) -> int:
    match = re.fullmatch(r"\s*(\d+)\s*([kmgt]?i?b?)?\s*", text, re.IGNORECASE)
    if not match:
        raise argparse.ArgumentTypeError(f"invalid size: {text}")
    value = int(match.group(1))
    unit = (match.group(2) or "").lower()
    scales = {
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
    }
    return value * scales[unit]


def load_library(names: list[str]) -> ctypes.CDLL | None:
    for name in names:
        if not name:
            continue
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    return None


class CudaRuntime:
    def __init__(self) -> None:
        candidates = [
            *cuda_runtime_library_candidates(),
            ctypes.util.find_library("cudart"),
            os.environ.get("CUDART_LIBRARY", ""),
            "/usr/local/cuda/lib64/libcudart.so",
            "/usr/local/cuda-12.3/lib64/libcudart.so",
            "/usr/local/cuda-12.4/lib64/libcudart.so",
        ]
        self.lib = load_library(candidates)
        if self.lib is None:
            raise RuntimeError("could not load libcudart; set CUDART_LIBRARY or LD_LIBRARY_PATH")
        for name in ("cudaDeviceSynchronize", "cudaProfilerStart", "cudaProfilerStop"):
            getattr(self.lib, name).restype = ctypes.c_int

    def check(self, code: int, api: str) -> None:
        if code != 0:
            raise RuntimeError(f"{api} failed with CUDA error {code}")

    def synchronize(self) -> None:
        self.check(self.lib.cudaDeviceSynchronize(), "cudaDeviceSynchronize")

    def profiler_start(self) -> None:
        self.check(self.lib.cudaProfilerStart(), "cudaProfilerStart")

    def profiler_stop(self) -> None:
        self.check(self.lib.cudaProfilerStop(), "cudaProfilerStop")


class Nvtx:
    def __init__(self) -> None:
        candidates = [
            ctypes.util.find_library("nvToolsExt"),
            os.environ.get("NVTOOLSEXT_LIBRARY", ""),
            "/usr/local/cuda/lib64/libnvToolsExt.so",
            "/usr/local/cuda-12.3/lib64/libnvToolsExt.so",
            "/usr/local/cuda-12.4/lib64/libnvToolsExt.so",
        ]
        self.lib = load_library(candidates)
        if self.lib is not None:
            self.lib.nvtxRangePushA.argtypes = [ctypes.c_char_p]
            self.lib.nvtxRangePushA.restype = ctypes.c_int
            self.lib.nvtxRangePop.restype = ctypes.c_int

    @contextmanager
    def range(self, name: str):
        if self.lib is not None:
            self.lib.nvtxRangePushA(name.encode("utf-8"))
        try:
            yield
        finally:
            if self.lib is not None:
                self.lib.nvtxRangePop()


def make_arrays(rows: int, cardinality: int) -> dict[str, np.ndarray]:
    index = np.arange(rows, dtype=np.int64)
    keys = ((index * 1103515245 + 12345) % cardinality).astype(np.int32)
    values = ((index % 10007).astype(np.float32) * np.float32(0.25))
    payload = (index ^ (index >> 3)).astype(np.int64)
    return {"key": keys, "val": values, "payload": payload}


def input_bytes_for(op: str, rows: int, cardinality: int) -> int:
    left = rows * ROW_BYTES
    if op == "join":
        return left + cardinality * 8
    return left


def build_context(cudf: Any, op: str, rows: int, cardinality: int) -> dict[str, Any]:
    data = make_arrays(rows, cardinality)
    df = cudf.DataFrame(data)
    ctx: dict[str, Any] = {
        "df": df,
        "rows": rows,
        "cardinality": cardinality,
        "threshold": cardinality // 2,
    }
    if op == "join":
        right_key = np.arange(cardinality, dtype=np.int32)
        right_dim = ((right_key.astype(np.int64) * 17) & 0x7FFFFFFF).astype(np.int32)
        ctx["right"] = cudf.DataFrame({"key": right_key, "dim": right_dim})
    return ctx


def run_operation(op: str, ctx: dict[str, Any]) -> Any:
    df = ctx["df"]
    if op == "filter":
        return df[df["key"] < ctx["threshold"]]
    if op == "project":
        return df["val"] * np.float32(1.25) + df["payload"].astype("float32") * np.float32(0.001)
    if op == "groupby":
        return df.groupby("key", sort=False).agg({"val": "sum", "payload": "count"})
    if op == "join":
        return df.merge(ctx["right"], on="key", how="inner")
    if op == "sort":
        return df.sort_values("key")
    raise ValueError(f"unknown op: {op}")


def result_rows(result: Any) -> int:
    try:
        return int(len(result))
    except TypeError:
        return 0


def rows_from_args(args: argparse.Namespace) -> int:
    if args.rows is not None:
        return args.rows
    if args.target_bytes is None:
        return parse_size("64MiB") // ROW_BYTES
    return max(1, args.target_bytes // ROW_BYTES)


def import_cudf() -> Any:
    try:
        import cudf  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "RAPIDS cuDF is not installed in this Python environment. "
            "Run this script from a cuDF/RAPIDS environment."
        ) from exc
    return cudf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--op", choices=OPS, required=True)
    parser.add_argument("--rows", type=int)
    parser.add_argument("--target-bytes", type=parse_size)
    parser.add_argument("--cardinality", type=int, default=DEFAULT_CARDINALITY)
    parser.add_argument("--iters", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--profile-operation-only", action="store_true")
    args = parser.parse_args()

    if args.iters <= 0 or args.warmup < 0:
        raise SystemExit("--iters must be positive and --warmup must be non-negative")

    rows = rows_from_args(args)
    if args.cardinality <= 0:
        raise SystemExit("--cardinality must be positive")
    cardinality = min(args.cardinality, max(1, rows))

    cudf = import_cudf()
    cuda = CudaRuntime()
    nvtx = Nvtx()
    ctx = build_context(cudf, args.op, rows, cardinality)
    cuda.synchronize()

    last_result = None
    for _ in range(args.warmup):
        last_result = run_operation(args.op, ctx)
        cuda.synchronize()

    input_bytes = input_bytes_for(args.op, rows, cardinality)
    cuda.synchronize()
    if args.profile_operation_only:
        cuda.profiler_start()
    start = time.perf_counter()
    try:
        for _ in range(args.iters):
            with nvtx.range(f"cudf:{args.op}"):
                last_result = run_operation(args.op, ctx)
                cuda.synchronize()
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if args.profile_operation_only:
            cuda.profiler_stop()
        cuda.synchronize()

    gib = (input_bytes * args.iters) / float(1 << 30)
    gib_per_s = gib / (elapsed_ms / 1000.0) if elapsed_ms > 0 else math.inf
    print(
        "cudf_microbench "
        f"op={args.op} rows={rows} cardinality={cardinality} "
        f"input_bytes={input_bytes} iters={args.iters} warmup={args.warmup} "
        f"result_rows={result_rows(last_result)} elapsed_ms={elapsed_ms:.3f} "
        f"gib_per_s={gib_per_s:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

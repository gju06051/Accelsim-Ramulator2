#!/usr/bin/env python3
"""Thin TPC-H-style cuDF query benchmark with profiler-scoped GPU work."""

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


QUERIES = ("q1", "q3", "q6", "q10")
LINEITEM_ROW_BYTES = 25


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


def import_cudf() -> Any:
    try:
        import cudf  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "RAPIDS cuDF is not installed in this Python environment. "
            "Run this script from a cuDF/RAPIDS environment."
        ) from exc
    return cudf


def nbytes_of_columns(columns: dict[str, np.ndarray]) -> int:
    return sum(int(column.nbytes) for column in columns.values())


def choose_row_counts(target_bytes: int, rows: int | None) -> dict[str, int]:
    lineitem_rows = rows if rows is not None else max(1024, target_bytes // LINEITEM_ROW_BYTES)
    orders_rows = max(256, lineitem_rows // 4)
    customer_rows = max(128, orders_rows // 10)
    return {
        "lineitem": int(lineitem_rows),
        "orders": int(orders_rows),
        "customer": int(customer_rows),
        "nation": 25,
    }


def lineitem_columns(rows: int, orders_rows: int) -> dict[str, np.ndarray]:
    idx = np.arange(rows, dtype=np.int64)
    return {
        "l_orderkey": (idx % orders_rows).astype(np.int32),
        "l_extendedprice": ((idx % 100000).astype(np.float32) + np.float32(100.0)),
        "l_discount": ((idx % 11).astype(np.float32) * np.float32(0.01)),
        "l_tax": ((idx % 9).astype(np.float32) * np.float32(0.01)),
        "l_quantity": ((idx % 50).astype(np.float32) + np.float32(1.0)),
        "l_returnflag": (idx % 3).astype(np.int8),
        "l_linestatus": ((idx // 3) % 2).astype(np.int8),
        "l_shipdate": (idx % 2525).astype(np.int32),
    }


def orders_columns(rows: int, customer_rows: int) -> dict[str, np.ndarray]:
    idx = np.arange(rows, dtype=np.int64)
    return {
        "o_orderkey": idx.astype(np.int32),
        "o_custkey": (idx % customer_rows).astype(np.int32),
        "o_orderdate": ((idx * 7) % 2525).astype(np.int32),
        "o_shippriority": (idx % 5).astype(np.int8),
    }


def customer_columns(rows: int) -> dict[str, np.ndarray]:
    idx = np.arange(rows, dtype=np.int64)
    return {
        "c_custkey": idx.astype(np.int32),
        "c_nationkey": (idx % 25).astype(np.int32),
        "c_mktsegment": (idx % 5).astype(np.int8),
        "c_acctbal": ((idx % 50000).astype(np.float32) * np.float32(0.1)),
    }


def nation_columns(rows: int) -> dict[str, np.ndarray]:
    idx = np.arange(rows, dtype=np.int64)
    return {
        "n_nationkey": idx.astype(np.int32),
        "n_regionkey": (idx % 5).astype(np.int8),
    }


def build_context(cudf: Any, target_bytes: int, rows: int | None) -> dict[str, Any]:
    counts = choose_row_counts(target_bytes, rows)
    lineitem = lineitem_columns(counts["lineitem"], counts["orders"])
    orders = orders_columns(counts["orders"], counts["customer"])
    customer = customer_columns(counts["customer"])
    nation = nation_columns(counts["nation"])
    table_bytes = {
        "lineitem": nbytes_of_columns(lineitem),
        "orders": nbytes_of_columns(orders),
        "customer": nbytes_of_columns(customer),
        "nation": nbytes_of_columns(nation),
    }
    return {
        "lineitem": cudf.DataFrame(lineitem),
        "orders": cudf.DataFrame(orders),
        "customer": cudf.DataFrame(customer),
        "nation": cudf.DataFrame(nation),
        "counts": counts,
        "table_bytes": table_bytes,
    }


def input_bytes_for_query(query: str, ctx: dict[str, Any]) -> int:
    table_bytes = ctx["table_bytes"]
    if query in ("q1", "q6"):
        return int(table_bytes["lineitem"])
    if query == "q3":
        return int(table_bytes["lineitem"] + table_bytes["orders"] + table_bytes["customer"])
    if query == "q10":
        return int(table_bytes["lineitem"] + table_bytes["orders"] + table_bytes["customer"] + table_bytes["nation"])
    raise ValueError(f"unknown query: {query}")


def run_q1(ctx: dict[str, Any]) -> Any:
    lineitem = ctx["lineitem"]
    filtered = lineitem[lineitem["l_shipdate"] <= 2400].copy()
    filtered["disc_price"] = filtered["l_extendedprice"] * (np.float32(1.0) - filtered["l_discount"])
    filtered["charge"] = filtered["disc_price"] * (np.float32(1.0) + filtered["l_tax"])
    result = (
        filtered.groupby(["l_returnflag", "l_linestatus"], as_index=False)
        .agg(
            {
                "l_quantity": ["sum", "mean"],
                "l_extendedprice": ["sum", "mean"],
                "disc_price": "sum",
                "charge": "sum",
                "l_discount": "mean",
                "l_orderkey": "count",
            }
        )
        .sort_values(["l_returnflag", "l_linestatus"])
    )
    return result


def run_q3(ctx: dict[str, Any]) -> Any:
    customer = ctx["customer"]
    orders = ctx["orders"]
    lineitem = ctx["lineitem"]
    customers = customer[customer["c_mktsegment"] == 2]
    orders_filtered = orders[orders["o_orderdate"] < 1100]
    lineitem_filtered = lineitem[lineitem["l_shipdate"] > 1100]
    joined = customers.merge(orders_filtered, left_on="c_custkey", right_on="o_custkey", how="inner")
    joined = joined.merge(lineitem_filtered, left_on="o_orderkey", right_on="l_orderkey", how="inner")
    joined["revenue"] = joined["l_extendedprice"] * (np.float32(1.0) - joined["l_discount"])
    result = (
        joined.groupby(["l_orderkey", "o_orderdate", "o_shippriority"], as_index=False)
        .agg({"revenue": "sum"})
        .sort_values("revenue", ascending=False)
        .head(10)
    )
    return result


def run_q6(ctx: dict[str, Any]) -> Any:
    lineitem = ctx["lineitem"]
    mask = (
        (lineitem["l_shipdate"] >= 730)
        & (lineitem["l_shipdate"] < 1095)
        & (lineitem["l_discount"] >= np.float32(0.05))
        & (lineitem["l_discount"] <= np.float32(0.07))
        & (lineitem["l_quantity"] < np.float32(24.0))
    )
    filtered = lineitem[mask]
    return (filtered["l_extendedprice"] * filtered["l_discount"]).sum()


def run_q10(ctx: dict[str, Any]) -> Any:
    customer = ctx["customer"]
    orders = ctx["orders"]
    lineitem = ctx["lineitem"]
    nation = ctx["nation"]
    orders_filtered = orders[(orders["o_orderdate"] >= 365) & (orders["o_orderdate"] < 455)]
    lineitem_filtered = lineitem[lineitem["l_returnflag"] == 1]
    joined = orders_filtered.merge(lineitem_filtered, left_on="o_orderkey", right_on="l_orderkey", how="inner")
    joined = joined.merge(customer, left_on="o_custkey", right_on="c_custkey", how="inner")
    joined = joined.merge(nation, left_on="c_nationkey", right_on="n_nationkey", how="inner")
    joined["revenue"] = joined["l_extendedprice"] * (np.float32(1.0) - joined["l_discount"])
    result = (
        joined.groupby(["c_custkey", "c_nationkey", "n_regionkey"], as_index=False)
        .agg({"revenue": "sum", "c_acctbal": "max"})
        .sort_values("revenue", ascending=False)
        .head(20)
    )
    return result


def run_query(query: str, ctx: dict[str, Any]) -> Any:
    if query == "q1":
        return run_q1(ctx)
    if query == "q3":
        return run_q3(ctx)
    if query == "q6":
        return run_q6(ctx)
    if query == "q10":
        return run_q10(ctx)
    raise ValueError(f"unknown query: {query}")


def result_rows(result: Any) -> int:
    try:
        return int(len(result))
    except TypeError:
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", choices=QUERIES, required=True)
    parser.add_argument("--rows", type=int)
    parser.add_argument("--target-bytes", type=parse_size, default=parse_size("64MiB"))
    parser.add_argument("--iters", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--profile-query-only", action="store_true")
    args = parser.parse_args()

    if args.iters <= 0 or args.warmup < 0:
        raise SystemExit("--iters must be positive and --warmup must be non-negative")

    cudf = import_cudf()
    cuda = CudaRuntime()
    nvtx = Nvtx()
    ctx = build_context(cudf, args.target_bytes, args.rows)
    cuda.synchronize()

    last_result = None
    for _ in range(args.warmup):
        last_result = run_query(args.query, ctx)
        cuda.synchronize()

    cuda.synchronize()
    if args.profile_query_only:
        cuda.profiler_start()
    start = time.perf_counter()
    try:
        for _ in range(args.iters):
            with nvtx.range(f"cudf:tpch:{args.query}"):
                last_result = run_query(args.query, ctx)
                cuda.synchronize()
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if args.profile_query_only:
            cuda.profiler_stop()
        cuda.synchronize()

    input_bytes = input_bytes_for_query(args.query, ctx)
    gib = (input_bytes * args.iters) / float(1 << 30)
    gib_per_s = gib / (elapsed_ms / 1000.0) if elapsed_ms > 0 else math.inf
    counts = ctx["counts"]
    print(
        "cudf_tpch_bench "
        f"query={args.query} "
        f"lineitem_rows={counts['lineitem']} orders_rows={counts['orders']} "
        f"customer_rows={counts['customer']} input_bytes={input_bytes} "
        f"iters={args.iters} warmup={args.warmup} "
        f"result_rows={result_rows(last_result)} elapsed_ms={elapsed_ms:.3f} "
        f"gib_per_s={gib_per_s:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate Galois/Lonestar binary .gr RMAT inputs.

The LonestarGPU 2.x BFS/SSSP binaries used in this repository read the Galois
binary graph layout:

  uint64 version (=1)
  uint64 edge_data_size (=4 for uint32 weights)
  uint64 num_nodes
  uint64 num_edges
  uint64 out_index[num_nodes]  # cumulative end offsets
  uint32 destinations[num_edges]
  uint32 edge_data[num_edges]

Generated graphs are symmetrized so the resulting file name convention matches
the existing rmat12.sym.gr input.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def generate_rmat_edges(scale: int, edge_factor: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    num_nodes = 1 << scale
    num_base_edges = (num_nodes * edge_factor) // 2
    rng = np.random.default_rng(seed)

    src = np.zeros(num_base_edges, dtype=np.uint32)
    dst = np.zeros(num_base_edges, dtype=np.uint32)

    # Graph500-like initiator probabilities, with light noise to avoid a few
    # overly dominant vertices.
    a, b, c = 0.57, 0.19, 0.19
    for bit in range(scale - 1, -1, -1):
        noise = rng.uniform(0.95, 1.05, size=3)
        aa, bb, cc = np.array([a, b, c]) * noise
        total = aa + bb + cc + 0.05
        aa, bb, cc = aa / total, bb / total, cc / total

        r = rng.random(num_base_edges)
        src |= ((r >= aa) & (r < aa + bb)).astype(np.uint32) << bit
        dst |= (r >= aa + bb).astype(np.uint32) << bit

    mask = src != dst
    src = src[mask]
    dst = dst[mask]

    sym_src = np.concatenate([src, dst])
    sym_dst = np.concatenate([dst, src])
    return sym_src, sym_dst


def write_galois_gr(output: Path, num_nodes: int, src: np.ndarray, dst: np.ndarray) -> None:
    order = np.lexsort((dst, src))
    src = src[order]
    dst = dst[order]
    counts = np.bincount(src, minlength=num_nodes).astype(np.uint64)
    out_index = np.cumsum(counts, dtype=np.uint64)
    weights = np.ones(dst.size, dtype=np.uint32)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as file:
        np.array([1, 4, num_nodes, dst.size], dtype=np.uint64).tofile(file)
        out_index.tofile(file)
        dst.astype(np.uint32, copy=False).tofile(file)
        weights.tofile(file)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, required=True, help="Number of vertices as 2^scale.")
    parser.add_argument("--edge-factor", type=int, default=16, help="Directed average degree target.")
    parser.add_argument("--seed", type=int, default=20260524)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.scale < 2:
        raise SystemExit("--scale must be at least 2")
    if args.edge_factor < 1:
        raise SystemExit("--edge-factor must be positive")

    num_nodes = 1 << args.scale
    src, dst = generate_rmat_edges(args.scale, args.edge_factor, args.seed)
    write_galois_gr(args.output, num_nodes, src, dst)
    print(
        f"wrote {args.output} nodes={num_nodes} directed_edges={dst.size} "
        f"avg_degree={dst.size / num_nodes:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

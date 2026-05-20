#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BFS_DIR="${ROOT}/suites/graphBIG/gpu_bench/gpu_BFS"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

make -C "${BFS_DIR}" clean
make -C "${BFS_DIR}" bfs_topo_frontier
"${BFS_DIR}/bfs_topo_frontier" --dataset "${ROOT}/suites/graphBIG/dataset/small" --root 31

#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  run_cudf_bench.sh micro --op <filter|project|groupby|join|sort> [args...]
  run_cudf_bench.sh tpch --query <q1|q3|q6|q10> [args...]

Set RAPIDS_PYTHON to force a specific Python with RAPIDS cuDF installed.
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

workload="$1"
shift

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../../.." && pwd)"

python_candidates=()
if [[ -n "${RAPIDS_PYTHON:-}" ]]; then
  python_candidates+=("$RAPIDS_PYTHON")
fi
python_candidates+=(
  "$repo_root/.venvs/rapids-cudf-cu12/bin/python"
  "$HOME/.venvs/rapids-cudf-cu12/bin/python"
  "$HOME/anaconda3/envs/rapids-cudf-cu12/bin/python"
  "$HOME/anaconda3/envs/rapids/bin/python"
  "python3"
)

rapids_python=""
for candidate in "${python_candidates[@]}"; do
  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]] || continue
    resolved="$candidate"
  else
    resolved="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$resolved" ]] || continue
  fi
  if "$resolved" -c 'import cudf' >/dev/null 2>&1; then
    rapids_python="$resolved"
    break
  fi
done

if [[ -z "$rapids_python" ]]; then
  echo "error: could not find a Python environment with RAPIDS cuDF; set RAPIDS_PYTHON" >&2
  exit 127
fi

case "$workload" in
  micro)
    exec "$rapids_python" "$repo_root/gpu_benchmark/benchmarks/prepare/cudf/cudf_microbench.py" "$@"
    ;;
  tpch)
    exec "$rapids_python" "$repo_root/gpu_benchmark/benchmarks/prepare/cudf/cudf_tpch_bench.py" "$@"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac

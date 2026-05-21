#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${script_dir}"

while [ "${repo_root}" != "/" ]; do
  if [ -x "${repo_root}/gpu_benchmark/benchmarks/prepare/bin/nvcomp_codec_bench" ]; then
    break
  fi
  repo_root="$(dirname -- "${repo_root}")"
done

binary="${repo_root}/gpu_benchmark/benchmarks/prepare/bin/nvcomp_codec_bench"
if [ ! -x "${binary}" ]; then
  echo "nvcomp_codec_bench not found. Build it with: make -C gpu_benchmark/benchmarks/prepare nvcomp" >&2
  exit 1
fi

nvcomp_root="${NVCOMP_ROOT:-}"
if [ -z "${nvcomp_root}" ]; then
  nvcomp_root="$(
    python3 - <<'PY' 2>/dev/null || true
import pathlib
try:
    import nvidia.libnvcomp
except Exception:
    raise SystemExit(0)
print(pathlib.Path(nvidia.libnvcomp.__file__).parent)
PY
  )"
fi

if [ -n "${nvcomp_root}" ] && [ -d "${nvcomp_root}/lib64" ]; then
  export LD_LIBRARY_PATH="${nvcomp_root}/lib64:${LD_LIBRARY_PATH:-}"
fi

exec "${binary}" "$@"

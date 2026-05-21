#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${script_dir}"

while [ "${repo_root}" != "/" ]; do
  if [ -x "${repo_root}/gpu_benchmark/benchmarks/prepare/tango/run_tango.sh" ]; then
    break
  fi
  repo_root="$(dirname -- "${repo_root}")"
done

runner="${repo_root}/gpu_benchmark/benchmarks/prepare/tango/run_tango.sh"
if [ ! -x "${runner}" ]; then
  echo "Tango runner not found. Build it with: make -C gpu_benchmark/benchmarks/prepare tango" >&2
  exit 1
fi

exec "${runner}" "$@"

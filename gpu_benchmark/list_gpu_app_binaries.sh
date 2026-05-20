#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${ROOT}/setup_gpu_app_collection_env.sh" >/dev/null

find "${BINDIR}/${BINSUBDIR}" -maxdepth 1 -type f -perm /111 -printf '%f\n' | sort

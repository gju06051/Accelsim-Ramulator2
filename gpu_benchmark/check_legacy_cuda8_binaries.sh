#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Checking gpu-app-collection built binary runtime dependencies"
find "${ROOT}/gpu-app-collection/bin" \
  -type f -perm /111 \
  -print0 |
while IFS= read -r -d '' exe; do
  if file "${exe}" | grep -q 'ELF'; then
    missing="$(ldd "${exe}" 2>/dev/null | awk '/not found/{print $1}' | paste -sd ',' -)"
    if [[ -n "${missing}" ]]; then
      echo "MISSING ${missing} :: ${exe}"
    else
      echo "OK :: ${exe}"
    fi
  fi
done

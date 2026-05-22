#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

url="${TANGO_URL:-https://gitlab.com/Tango-DNNbench/Tango.git}"
commit="${TANGO_COMMIT:-59db69914bf5391b8f39b8b8463482794afe3956}"
dest="${TANGO_SRC_ROOT:-${script_dir}/upstream/Tango}"
models="${TANGO_MODELS:-CifarNet GRU LSTM AlexNet}"

mkdir -p "$(dirname -- "${dest}")"

if [ ! -d "${dest}/.git" ]; then
  git clone --filter=blob:none --no-checkout "${url}" "${dest}"
fi

git -C "${dest}" fetch --depth 1 origin "${commit}"
git -C "${dest}" sparse-checkout init --no-cone

patterns=("/README.md" "/LICENSE")
for model in ${models}; do
  patterns+=("/GPU/${model}/**")
done

printf "%s\n" "${patterns[@]}" | git -C "${dest}" sparse-checkout set --stdin --no-cone
git -C "${dest}" checkout --detach "${commit}"

echo "Fetched Tango ${commit} into ${dest}"
echo "Models: ${models}"

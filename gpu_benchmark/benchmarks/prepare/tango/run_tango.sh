#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <cifarnet|gru|lstm|alexnet|resnet|squeezenet> [model args...]" >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
src_root="${TANGO_SRC_ROOT:-${script_dir}/upstream/Tango}"
model="$1"
shift

case "${model}" in
  CifarNet|cifarnet)
    dir="${src_root}/GPU/CifarNet"
    exe="./CN"
    default_args=(1)
    ;;
  GRU|gru)
    dir="${src_root}/GPU/GRU"
    exe="./GRU"
    default_args=()
    ;;
  LSTM|lstm)
    dir="${src_root}/GPU/LSTM"
    exe="./LSTM"
    default_args=(1)
    ;;
  AlexNet|alexnet)
    dir="${src_root}/GPU/AlexNet"
    exe="./AN"
    default_args=(1)
    ;;
  ResNet|resnet)
    dir="${src_root}/GPU/ResNet"
    exe="./RN"
    default_args=(1)
    ;;
  SqueezeNet|squeezenet)
    dir="${src_root}/GPU/SqueezeNet"
    exe="./SN"
    default_args=(1)
    ;;
  *)
    echo "Unknown Tango model: ${model}" >&2
    exit 2
    ;;
esac

if [ ! -x "${dir}/${exe#./}" ]; then
  echo "Tango executable not found: ${dir}/${exe#./}. Run tango/build_tango.sh first." >&2
  exit 2
fi

if [ "$#" -eq 0 ]; then
  set -- "${default_args[@]}"
fi

(cd "${dir}" && exec "${exe}" "$@")

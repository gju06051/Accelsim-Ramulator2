#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
src_root="${TANGO_SRC_ROOT:-${script_dir}/upstream/Tango}"
models="${TANGO_MODELS:-CifarNet GRU LSTM AlexNet}"

nvcc_bin="${NVCC:-nvcc}"
cuda_host_cxx="${CUDAHOSTCXX:-/usr/bin/g++-11}"
cuda_arch="${CUDA_ARCH:-86}"
common_flags=(
  -O3
  -std=c++11
  -ccbin "${cuda_host_cxx}"
  -gencode "arch=compute_${cuda_arch},code=sm_${cuda_arch}"
  -gencode "arch=compute_${cuda_arch},code=compute_${cuda_arch}"
)

if [ ! -d "${src_root}/GPU" ]; then
  echo "Tango source not found at ${src_root}. Run tango/fetch_tango.sh first." >&2
  exit 2
fi

build_one() {
  local model="$1"
  local dir source output

  case "${model}" in
    CifarNet|cifarnet)
      dir="${src_root}/GPU/CifarNet"
      source="CN_cuda.cu"
      output="CN"
      ;;
    GRU|gru)
      dir="${src_root}/GPU/GRU"
      source="gru_host.cu"
      output="GRU"
      ;;
    LSTM|lstm)
      dir="${src_root}/GPU/LSTM"
      source="lstm.cu"
      output="LSTM"
      ;;
    AlexNet|alexnet)
      dir="${src_root}/GPU/AlexNet"
      source="alexnet_host.cu"
      output="AN"
      ;;
    ResNet|resnet)
      dir="${src_root}/GPU/ResNet"
      source="resnet_host.cu"
      output="RN"
      ;;
    SqueezeNet|squeezenet)
      dir="${src_root}/GPU/SqueezeNet"
      source="SN.cu"
      output="SN"
      ;;
    *)
      echo "Unknown Tango model: ${model}" >&2
      exit 2
      ;;
  esac

  if [ ! -f "${dir}/${source}" ]; then
    echo "Missing ${dir}/${source}. Re-run fetch_tango.sh with TANGO_MODELS including ${model}." >&2
    exit 2
  fi

  echo "Building Tango ${model}"
  (cd "${dir}" && "${nvcc_bin}" "${common_flags[@]}" "${source}" -o "${output}")
}

for model in ${models}; do
  build_one "${model}"
done

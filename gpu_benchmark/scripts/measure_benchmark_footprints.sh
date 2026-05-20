#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT}/traces/run_logs/footprint}"
TIMEOUT_DEFAULT="${BENCH_TIMEOUT:-180}"
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

mkdir -p "${OUT_DIR}"

# shellcheck source=/dev/null
source "${ROOT}/scripts/setup_gpu_app_collection_env.sh" >/dev/null

TRACER="${TRACER:-${ROOT}/footprint_tracer/build/libcuda_footprint_tracer.so}"
if [[ ! -f "${TRACER}" ]]; then
  TRACER="$("${ROOT}/scripts/build_cuda_footprint_tracer.sh")"
fi

BIN="${BINDIR}/${BINSUBDIR}"
GRAPHBIG="${ROOT}/suites/graphBIG"
GRAPHBIG_GPU="${GRAPHBIG}/gpu_bench"
GRAPHBIG_DATA="${GRAPHBIG}/dataset"
APPS_DATA="${GPUAPPS_ROOT}/data_dirs"
RODINIA_DATA="${APPS_DATA}/cuda/rodinia/3.1"
PANNOTIA_DATA="${APPS_DATA}/pannotia"
PARBOIL="${GPUAPPS_ROOT}/src/cuda/parboil"
LONESTAR_DATA="${APPS_DATA}/cuda/lonestargpu-2.0/inputs"
ISPASS_DATA="${APPS_DATA}/cuda/ispass-2009"

SUMMARY="${OUT_DIR}/summary.tsv"
printf "suite\tbenchmark\tdataset\tstatus\texit_code\tseconds\tpeak_bytes\tpeak_mib\tover_40mb\ttotal_allocated_bytes\tmax_single_allocation_bytes\talloc_count\tlog\tmetrics\tcommand\n" >"${SUMMARY}"

sanitize() {
  printf "%s" "$1" | tr -c 'A-Za-z0-9_.-' '_'
}

metric_field() {
  local file="$1"
  local idx="$2"
  awk -F'\t' -v idx="${idx}" '
    $1 != "pid" && $idx ~ /^[0-9]+([.][0-9]+)?$/ {
      if ($idx + 0 > max) max = $idx + 0
    }
    END { printf "%.0f", max + 0 }
  ' "${file}" 2>/dev/null || printf "0"
}

metric_mib() {
  local bytes="$1"
  awk -v b="${bytes}" 'BEGIN { printf "%.3f", b / 1024 / 1024 }'
}

record_case() {
  local suite="$1"
  local bench="$2"
  local dataset="$3"
  local timeout_s="$4"
  local cmd="$5"
  local safe metrics log start end seconds code status peak total max_single alloc_count peak_mib over_40mb

  safe="$(sanitize "${suite}_${bench}_${dataset}")"
  metrics="${OUT_DIR}/${safe}.metrics.tsv"
  log="${OUT_DIR}/${safe}.log"
  rm -f "${metrics}" "${log}"

  echo "== ${suite}/${bench}/${dataset} =="
  start="$(date +%s)"
  set +e
  CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES}" \
  CUDA_FOOTPRINT_LOG="${metrics}" \
  LD_PRELOAD="${TRACER}${LD_PRELOAD:+:${LD_PRELOAD}}" \
    timeout "${timeout_s}s" bash -lc "${cmd}" >"${log}" 2>&1
  code=$?
  set -e
  end="$(date +%s)"
  seconds=$((end - start))

  if [[ "${code}" -eq 0 ]]; then
    status="PASS"
  elif [[ "${code}" -eq 124 ]]; then
    status="TIMEOUT"
  else
    status="FAIL"
  fi

  peak="$(metric_field "${metrics}" 3)"
  total="$(metric_field "${metrics}" 5)"
  max_single="$(metric_field "${metrics}" 6)"
  alloc_count="$(metric_field "${metrics}" 7)"
  peak_mib="$(metric_mib "${peak}")"
  if (( peak > 40 * 1024 * 1024 )); then
    over_40mb="yes"
  else
    over_40mb="no"
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "${suite}" "${bench}" "${dataset}" "${status}" "${code}" "${seconds}" \
    "${peak}" "${peak_mib}" "${over_40mb}" "${total}" "${max_single}" \
    "${alloc_count}" "${log}" "${metrics}" "${cmd}" >>"${SUMMARY}"
}

run_graphbig() {
  local d
  d="${GRAPHBIG_DATA}/LDBC_100k"
  record_case graphBIG bfs_topo_frontier LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_BFS/bfs_topo_frontier' --dataset '${d}' --root 31"
  record_case graphBIG bfs_data_thread_centric LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_BFS/bfs_data_thread_centric' --dataset '${d}' --root 31"
  record_case graphBIG bfs_data_warp_centric LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_BFS/bfs_data_warp_centric' --dataset '${d}' --root 31"
  record_case graphBIG connected_comp LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_ConnectedComp/connected_comp' --dataset '${d}'"
  record_case graphBIG degree_centr LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_DegreeCentr/degree_centr' --dataset '${d}'"
  record_case graphBIG gc_topo_thread_centric LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_GraphColoring/gc_topo_thread_centric' --dataset '${d}'"
  record_case graphBIG sssp_data_thread_centric LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_SSSP/sssp_data_thread_centric' --dataset '${d}' --root 31"
  record_case graphBIG sssp_data_warp_centric LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_SSSP/sssp_data_warp_centric' --dataset '${d}' --root 31"
  record_case graphBIG triangle_count LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_TriangleCount/triangle_count' --dataset '${d}'"
  record_case graphBIG kcore LDBC_100k 120 "'${GRAPHBIG_GPU}/gpu_kCore/kcore' --dataset '${d}'"

  d="${GRAPHBIG_DATA}/LDBC_1000k"
  record_case graphBIG bfs_topo_frontier LDBC_1000k 180 "'${GRAPHBIG_GPU}/gpu_BFS/bfs_topo_frontier' --dataset '${d}' --root 31"
  record_case graphBIG sssp_data_thread_centric LDBC_1000k 180 "'${GRAPHBIG_GPU}/gpu_SSSP/sssp_data_thread_centric' --dataset '${d}' --root 31"
  record_case graphBIG connected_comp LDBC_1000k 180 "'${GRAPHBIG_GPU}/gpu_ConnectedComp/connected_comp' --dataset '${d}'"
}

run_polybench() {
  local b t
  for b in \
    polybench-2DConvolution polybench-3DConvolution polybench-3mm \
    polybench-atax polybench-bicg polybench-correlation \
    polybench-covariance polybench-fdtd2d polybench-gemm \
    polybench-gesummv polybench-mvt polybench-syr2k polybench-syrk
  do
    record_case polybench "${b}" default 120 "'${BIN}/${b}'"
  done
  for b in polybench-2mm polybench-gramschmidt; do
    t=360
    record_case polybench "${b}" default "${t}" "'${BIN}/${b}'"
  done
}

run_ispass() {
  record_case ispass-2009 BFS graph65536 120 "'${BIN}/ispass-2009-BFS' '${ISPASS_DATA}/ispass-2009-BFS/data/graph65536.txt'"
  record_case ispass-2009 NN 1000 120 "cd '${ISPASS_DATA}/ispass-2009-NN' && '${BIN}/ispass-2009-NN' 1000"
  record_case ispass-2009 LIB default 120 "'${BIN}/ispass-2009-LIB'"
  record_case ispass-2009 LPS default 120 "'${BIN}/ispass-2009-LPS'"
  record_case ispass-2009 NQU default 120 "'${BIN}/ispass-2009-NQU'"
  record_case ispass-2009 RAY 256x256 120 "'${BIN}/ispass-2009-RAY' 256 256"
  record_case ispass-2009 STO default 120 "'${BIN}/ispass-2009-STO'"
}

run_pannotia() {
  record_case pannotia bc 1k_128k 120 "'${BIN}/bc' '${PANNOTIA_DATA}/bc/data/1k_128k.gr'"
  record_case pannotia color_max G3_circuit 120 "'${BIN}/color_max' '${PANNOTIA_DATA}/color_max/data/G3_circuit.graph' 1"
  record_case pannotia color_maxmin G3_circuit 120 "'${BIN}/color_maxmin' '${PANNOTIA_DATA}/color_maxmin/data/G3_circuit.graph' 1"
  record_case pannotia fw 256_16384 120 "'${BIN}/fw' '${PANNOTIA_DATA}/fw/data/256_16384.gr'"
  record_case pannotia fw_block 256_16384 120 "'${BIN}/fw_block' '${PANNOTIA_DATA}/fw_block/data/256_16384.gr'"
  record_case pannotia mis G3_circuit 120 "'${BIN}/mis' '${PANNOTIA_DATA}/mis/data/G3_circuit.graph' 1"
  record_case pannotia pagerank coAuthorsDBLP 120 "'${BIN}/pagerank' '${PANNOTIA_DATA}/pagerank/data/coAuthorsDBLP.graph' 1"
  record_case pannotia pagerank_spmv coAuthorsDBLP 120 "'${BIN}/pagerank_spmv' '${PANNOTIA_DATA}/pagerank_spmv/data/coAuthorsDBLP.graph' 1"
  record_case pannotia sssp USA-road-d.NY 120 "'${BIN}/sssp' '${PANNOTIA_DATA}/sssp/data/USA-road-d.NY.gr' 0"
  record_case pannotia sssp_ell USA-road-d.NY 120 "'${BIN}/sssp_ell' '${PANNOTIA_DATA}/sssp_ell/data/USA-road-d.NY.gr' 0"
}

run_rodinia() {
  record_case rodinia backprop 65536 120 "'${BIN}/backprop-rodinia-3.1' 65536"
  record_case rodinia bfs graph65536 120 "'${BIN}/bfs-rodinia-3.1' '${RODINIA_DATA}/bfs-rodinia-3.1/data/graph65536.txt'"
  record_case rodinia cfd fvcorr_097K 120 "'${BIN}/cfd-rodinia-3.1' '${RODINIA_DATA}/cfd-rodinia-3.1/data/fvcorr.domn.097K'"
  record_case rodinia hotspot 64x2 120 "'${BIN}/hotspot-rodinia-3.1' 64 2 10 '${RODINIA_DATA}/hotspot-rodinia-3.1/data/temp_64' '${RODINIA_DATA}/hotspot-rodinia-3.1/data/power_64' '${OUT_DIR}/hotspot.out'"
  record_case rodinia hotspot3D 64x8 120 "'${BIN}/hotspot3D-rodinia-3.1' 64 8 10 '${RODINIA_DATA}/hotspot3D-rodinia-3.1/data/power_64x8' '${RODINIA_DATA}/hotspot3D-rodinia-3.1/data/temp_64x8' '${OUT_DIR}/hotspot3D.out'"
  record_case rodinia gaussian matrix208 120 "'${BIN}/gaussian-rodinia-3.1' -f '${RODINIA_DATA}/gaussian-rodinia-3.1/data/matrix208.txt' -q"
  record_case rodinia lud 256 120 "'${BIN}/lud-rodinia-3.1' -i '${RODINIA_DATA}/lud-rodinia-3.1/data/256.dat'"
  record_case rodinia nn filelist_4 120 "cd '${RODINIA_DATA}/nn-rodinia-3.1' && '${BIN}/nn-rodinia-3.1' data/filelist_4 -r 3 -lat 30 -lng 90"
  record_case rodinia nw 2048 120 "'${BIN}/nw-rodinia-3.1' 2048 10"
  record_case rodinia pathfinder 1000x100 120 "'${BIN}/pathfinder-rodinia-3.1' 1000 100 20"
  record_case rodinia particlefilter_float 128x128x10 120 "'${BIN}/particlefilter_float-rodinia-3.1' -x 128 -y 128 -z 10 -np 1000"
  record_case rodinia particlefilter_naive 128x128x10 120 "'${BIN}/particlefilter_naive-rodinia-3.1' -x 128 -y 128 -z 10 -np 1000"
  record_case rodinia srad_v1 502x458 120 "'${BIN}/srad_v1-rodinia-3.1' 10 0.5 502 458"
  record_case rodinia srad_v2 1024x1024 120 "'${BIN}/srad_v2-rodinia-3.1' 1024 1024 0 127 0 127 0.5 2"
  record_case rodinia lavaMD boxes10 120 "'${BIN}/lavaMD-rodinia-3.1' -boxes1d 10"
  record_case rodinia myocyte 100x10 120 "'${BIN}/myocyte-rodinia-3.1' 100 10 1"
  record_case rodinia streamcluster 65536 180 "'${BIN}/streamcluster-rodinia-3.1' 10 20 128 65536 65536 1000 none '${OUT_DIR}/streamcluster.out' 1"
  record_case rodinia heartwall test20 120 "'${BIN}/heartwall-rodinia-3.1' '${RODINIA_DATA}/heartwall-rodinia-3.1/data/test.avi' 20"
  record_case rodinia btree mil 120 "'${BIN}/b+tree-rodinia-3.1' file '${RODINIA_DATA}/b+tree-rodinia-3.1/data/mil.txt' command '${RODINIA_DATA}/b+tree-rodinia-3.1/data/command.txt'"
  record_case rodinia huffman test1024 120 "'${BIN}/huffman-rodinia-3.1' '${RODINIA_DATA}/huffman-rodinia-3.1/data/test1024_H2.206587175259.in'"
  record_case rodinia dwt2d 192x192 120 "'${BIN}/dwt2d-rodinia-3.1' -d 192x192 -f -5 '${RODINIA_DATA}/dwt2d-rodinia-3.1/data/rgb.bmp' '${OUT_DIR}/dwt2d.out'"
}

run_parboil() {
  record_case parboil cutcp small 180 "cd '${PARBOIL}' && ./parboil run cutcp cuda small -C"
  record_case parboil histo default 180 "cd '${PARBOIL}' && ./parboil run histo cuda default -C"
  record_case parboil mri-gridding small 180 "cd '${PARBOIL}' && ./parboil run mri-gridding cuda small -C"
  record_case parboil mri-q small 180 "cd '${PARBOIL}' && ./parboil run mri-q cuda small -C"
  record_case parboil stencil small 180 "cd '${PARBOIL}' && ./parboil run stencil cuda small -C"
  record_case parboil tpacf small 180 "cd '${PARBOIL}' && ./parboil run tpacf cuda small -C"
  record_case parboil sgemm small 180 "'${BIN}/parboil-sgemm' -i '${PARBOIL}/datasets/sgemm/small/input/matrix1.txt,${PARBOIL}/datasets/sgemm/small/input/matrix2.txt,${PARBOIL}/datasets/sgemm/small/input/matrix2t.txt' -o '${OUT_DIR}/parboil_sgemm.out'"
  record_case parboil lbm short 180 "'${BIN}/parboil-lbm' 100 -i '${PARBOIL}/datasets/lbm/short/input/120_120_150_ldc.of' -o '${OUT_DIR}/parboil_lbm.out'"
}

run_lonestar() {
  record_case lonestar bfs rmat12 120 "'${BIN}/lonestar-bfs' '${LONESTAR_DATA}/rmat12.sym.gr'"
  record_case lonestar bfs_atomic rmat12 120 "'${BIN}/lonestar-bfs-atomic' '${LONESTAR_DATA}/rmat12.sym.gr'"
  record_case lonestar bfs_wla rmat12 120 "'${BIN}/lonestar-bfs-wla' '${LONESTAR_DATA}/rmat12.sym.gr'"
  record_case lonestar bfs_wlw rmat12 120 "'${BIN}/lonestar-bfs-wlw' '${LONESTAR_DATA}/rmat12.sym.gr'"
  record_case lonestar sssp USA-road-d.NY 120 "'${BIN}/lonestar-sssp' '${LONESTAR_DATA}/USA-road-d.NY.gr'"
  record_case lonestar sssp_wln USA-road-d.NY 120 "'${BIN}/lonestar-sssp-wln' '${LONESTAR_DATA}/USA-road-d.NY.gr'"
  record_case lonestar mst rmat12 120 "'${BIN}/lonestar-mst' '${LONESTAR_DATA}/rmat12.sym.gr'"
  record_case lonestar dmr 25k_factor12 120 "'${BIN}/lonestar-dmr' '${LONESTAR_DATA}/25k' 12"
  record_case lonestar nsp random42 120 "'${BIN}/lonestar-nsp' '${LONESTAR_DATA}/random-42-10-3.cnf' 3"
  record_case lonestar pta pine_no_verify 180 "'${BIN}/lonestar-pta' '${LONESTAR_DATA}/pine_nodes.txt' '${LONESTAR_DATA}/pine_constraints_after_hcd.txt' '${LONESTAR_DATA}/pine_hcd.txt' '${LONESTAR_DATA}/pine_correct_soln_001.txt' 1 0"
}

run_proxy() {
  record_case proxy XSBench small 180 "'${BIN}/XSBench' 1 small 0 1000"
  record_case proxy lulesh dt0.001 180 "'${BIN}/lulesh' 0.001"
}

run_uvm() {
  record_case uvm 2dconv default 120 "'${BIN}/uvm_2dconv'"
  record_case uvm add_vectors default 120 "'${BIN}/uvm_add_vectors'"
  record_case uvm atax default 120 "'${BIN}/uvm_atax'"
  record_case uvm fdtd default 120 "'${BIN}/uvm_fdtd'"
  record_case uvm ra default 120 "'${BIN}/uvm_ra'"
  record_case uvm sssp default 120 "'${BIN}/uvm_sssp'"
  record_case uvm stream_triad default 120 "'${BIN}/uvm_stream_triad'"
  record_case uvm backprop 65536 120 "'${BIN}/uvm_backprop' 65536"
  record_case uvm needle 64 120 "'${BIN}/uvm_needle' 64 10"
  record_case uvm pathfinder 100x100 120 "'${BIN}/uvm_pathfinder' 100 100 20"
  record_case uvm srad 128x128 120 "'${BIN}/uvm_srad' 128 128 0 31 0 31 0.5 2"
}

BENCH_GROUPS="${BENCH_GROUPS:-graphbig,polybench,ispass,pannotia,rodinia,parboil,lonestar,proxy}"
IFS=',' read -r -a selected_groups <<<"${BENCH_GROUPS}"
for group in "${selected_groups[@]}"; do
  case "${group}" in
    graphbig) run_graphbig ;;
    polybench) run_polybench ;;
    ispass) run_ispass ;;
    pannotia) run_pannotia ;;
    rodinia) run_rodinia ;;
    parboil) run_parboil ;;
    lonestar) run_lonestar ;;
    proxy) run_proxy ;;
    uvm) run_uvm ;;
    *) echo "Unknown group: ${group}" >&2; exit 1 ;;
  esac
done

echo "summary=${SUMMARY}"

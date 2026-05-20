#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_BENCH="${ROOT}/gpu_benchmark"

FOOTPRINT_SUMMARY="${FOOTPRINT_SUMMARY:-${GPU_BENCH}/traces/run_logs/footprint/summary.tsv}"
OUT_DIR="${OUT_DIR:-${GPU_BENCH}/traces/sim/a100_sector_profile}"
MIN_FOOTPRINT_MIB="${MIN_FOOTPRINT_MIB:-40}"
SIM_TIMEOUT="${SIM_TIMEOUT:-0}"
MAX_CASES="${MAX_CASES:-0}"
CASE_REGEX="${CASE_REGEX:-}"
EXCLUDE_SUITES="${EXCLUDE_SUITES:-uvm}"
FORCE="${FORCE:-0}"
SORT_ORDER="${SORT_ORDER:-desc}"
JOBS="${JOBS:-32}"
GPGPUSIM_ENV="${GPGPUSIM_ENV:-${ROOT}/gpgpu-sim_a100_env.sh}"
SECTOR_GPGPUSIM_CONFIG="${SECTOR_GPGPUSIM_CONFIG:-}"
SECTOR_EXTRA_GPGPUSIM_CONFIG="${SECTOR_EXTRA_GPGPUSIM_CONFIG:-}"

GPUAPPS_ROOT="${GPUAPPS_ROOT:-${GPU_BENCH}/gpu-app-collection}"
PARBOIL="${GPUAPPS_ROOT}/src/cuda/parboil"

mkdir -p "${OUT_DIR}"
mkdir -p "${OUT_DIR}/locks"
GLOBAL_LAUNCH_LOCK_DIR="${GLOBAL_LAUNCH_LOCK_DIR:-${GPU_BENCH}/traces/sim/launch_locks}"
mkdir -p "${GLOBAL_LAUNCH_LOCK_DIR}"

SELECTED="${OUT_DIR}/selected_cases.tsv"
SUMMARY="${OUT_DIR}/summary.tsv"
COMBINED_CSV="${OUT_DIR}/sector_access_profile.csv"
CROSS_BANK_CSV="${OUT_DIR}/sector_access_cross_bank_profile.csv"

sanitize() {
  printf "%s" "$1" | tr -c 'A-Za-z0-9_.-' '_'
}

profile_value() {
  local file="$1"
  local key="$2"
  if [[ ! -f "${file}" ]]; then
    printf "NA\n"
    return 0
  fi
  awk -F' = ' -v key="${key}" '
    $1 == key {
      print $2
      found = 1
      exit
    }
    END {
      if (!found) print "NA"
    }
  ' "${file}" 2>/dev/null || printf "NA\n"
}

profile_has_zero_traffic() {
  local file="$1"
  if [[ ! -f "${file}" ]]; then
    return 1
  fi

  awk -F' = ' '
    $1 == "sector_access_records" {
      records = $2 + 0
      have_records = 1
    }
    $1 == "sector_access_total_dram_bytes" {
      bytes = $2 + 0
      have_bytes = 1
    }
    END {
      exit !(have_records && have_bytes && records == 0 && bytes == 0)
    }
  ' "${file}" 2>/dev/null
}

profile_reuse_status() {
  local profile_file="$1"
  if profile_has_zero_traffic "${profile_file}"; then
    printf "NO_ELIGIBLE_READ_TRAFFIC\n"
  else
    printf "DONE\n"
  fi
}

write_complete_marker() {
  local complete_file="$1"
  local status="$2"
  local exit_code="$3"
  local seconds="$4"
  local profile_file="$5"

  {
    printf "status=%s\n" "${status}"
    printf "exit_code=%s\n" "${exit_code}"
    printf "seconds=%s\n" "${seconds}"
    printf "records=%s\n" "$(profile_value "${profile_file}" sector_access_records)"
    printf "total_dram_bytes=%s\n" "$(profile_value "${profile_file}" sector_access_total_dram_bytes)"
    printf "completed_at=%s\n" "$(date -Is)"
  } >"${complete_file}"
}

normalize_command() {
  local suite="$1"
  local bench="$2"
  local dataset="$3"
  local run_dir="$4"
  local cmd="$5"

  case "${suite}/${bench}/${dataset}" in
    parboil/histo/default)
      printf "'%s/benchmarks/histo/build/cuda_default/histo' -i '%s/datasets/histo/default/input/img.bin' -o '%s/histo.bmp' -- 20 4\n" \
        "${PARBOIL}" "${PARBOIL}" "${run_dir}"
      ;;
    parboil/mri-gridding/small)
      printf "'%s/benchmarks/mri-gridding/build/cuda_default/mri-gridding' -i '%s/datasets/mri-gridding/small/input/small.uks' -o '%s/mri-gridding.out' -- 32 0\n" \
        "${PARBOIL}" "${PARBOIL}" "${run_dir}"
      ;;
    *)
      printf "%s\n" "${cmd}"
      ;;
  esac
}

detect_launch_dir() {
  local cmd="$1"
  local cd_dir
  cd_dir="$(printf "%s\n" "${cmd}" | sed -n "s/^cd '\([^']*\)' && .*/\1/p")"
  if [[ -n "${cd_dir}" ]]; then
    printf "%s\n" "${cd_dir}"
  else
    printf "%s\n" "$2"
  fi
}

write_config() {
  local run_dir="$1"
  local profile_file="$2"

  cp "${SECTOR_GPGPUSIM_CONFIG}" "${run_dir}/gpgpusim.config"
  {
    printf "\n# generated_by_sector_access_batch\n"
    printf -- "-gpgpu_perf_sim_memcpy 0\n"
    printf -- "-sector_access_profile 1\n"
    printf -- "-sector_access_profile_file %s\n" "${profile_file}"
    if [[ -n "${SECTOR_EXTRA_GPGPUSIM_CONFIG}" ]]; then
      printf "%s\n" "${SECTOR_EXTRA_GPGPUSIM_CONFIG}"
    fi
  } >>"${run_dir}/gpgpusim.config"
}

install_launch_config() {
  local run_dir="$1"
  local launch_dir="$2"
  local target="${launch_dir}/gpgpusim.config"
  local backup="${run_dir}/launch_gpgpusim.config.backup"

  if [[ "${launch_dir}" == "${run_dir}" ]]; then
    printf "NONE\n"
    return
  fi

  if [[ -e "${target}" || -L "${target}" ]]; then
    if grep -q '^# generated_by_sector_access_batch$' "${target}" 2>/dev/null; then
      rm -f "${target}"
    else
      mv "${target}" "${backup}"
    fi
  fi

  cp "${run_dir}/gpgpusim.config" "${target}"
  printf "%s\n" "${backup}"
}

restore_launch_config() {
  local launch_dir="$1"
  local backup="$2"
  local target="${launch_dir}/gpgpusim.config"

  if [[ "${backup}" == "NONE" ]]; then
    return
  fi

  rm -f "${target}"
  if [[ -e "${backup}" || -L "${backup}" ]]; then
    mv "${backup}" "${target}"
  fi
}

make_selected_cases() {
  local min_bytes tmp
  min_bytes="$(awk -v mib="${MIN_FOOTPRINT_MIB}" 'BEGIN { printf "%.0f", mib * 1024 * 1024 }')"
  tmp="${SELECTED}.tmp"

  {
    printf "rank\tsuite\tbenchmark\tdataset\tfootprint_mib\tfootprint_bytes\tcommand\n"
    awk -F'\t' -v min="${min_bytes}" -v exclude="${EXCLUDE_SUITES}" '
      BEGIN {
        n = split(exclude, suites, ",")
        for (i = 1; i <= n; i++) {
          if (suites[i] != "") skip_suite[suites[i]] = 1
        }
      }
      NR > 1 && $4 == "PASS" && ($7 + 0) >= min && !($1 in skip_suite) {
        OFS = "\t"
        print $1, $2, $3, $8, $7, $15
      }
    ' "${FOOTPRINT_SUMMARY}" |
      if [[ "${SORT_ORDER}" == "asc" ]]; then
        sort -t$'\t' -k4,4n
      else
        sort -t$'\t' -k4,4nr
      fi |
      awk -F'\t' 'BEGIN { OFS = "\t" } { print NR, $0 }'
  } >"${tmp}"

  if [[ -n "${CASE_REGEX}" ]]; then
    awk -F'\t' -v re="${CASE_REGEX}" '
      NR == 1 || ($2 "/" $3 "/" $4) ~ re
    ' "${tmp}" >"${SELECTED}"
  else
    mv "${tmp}" "${SELECTED}"
  fi

  if [[ "${MAX_CASES}" != "0" ]]; then
    tmp="${SELECTED}.tmp"
    awk -F'\t' -v max="${MAX_CASES}" '
      NR == 1 || NR <= max + 1
    ' "${SELECTED}" >"${tmp}"
    mv "${tmp}" "${SELECTED}"
  fi
}

record_summary() {
  local rank="$1"
  local suite="$2"
  local bench="$3"
  local dataset="$4"
  local footprint_mib="$5"
  local footprint_bytes="$6"
  local status="$7"
  local exit_code="$8"
  local seconds="$9"
  local run_dir="${10}"
  local profile_file="${11}"
  local log="${12}"
  local cmd="${13}"

  local records total_dram eligible dyn8 dyn16 dyn32 lifetime spatial extra slot8 slot16
  local chop8_supply chop8_ready chop8_full chop8_ideal chop8_half chop8_loss
  local chop8_recovered chop8_no_candidate chop8_timing chop8_bank
  local chop8_full_gain chop8_half_gain
  local chop16_supply chop16_ready chop16_full chop16_ideal chop16_half chop16_loss
  local chop16_recovered chop16_no_candidate chop16_timing chop16_bank
  local chop16_full_gain chop16_half_gain
  local rowhit_candidates rowhit_ready avg_candidates avg_ready
  local cand8 cand16 cand32 avg_age
  records="$(profile_value "${profile_file}" sector_access_records)"
  total_dram="$(profile_value "${profile_file}" sector_access_total_dram_bytes)"
  eligible="$(profile_value "${profile_file}" sector_access_eligible_traffic_fraction)"
  dyn8="$(profile_value "${profile_file}" sector_access_dynamic_8B_ratio)"
  dyn16="$(profile_value "${profile_file}" sector_access_dynamic_16B_ratio)"
  dyn32="$(profile_value "${profile_file}" sector_access_dynamic_32B_ratio)"
  lifetime="$(profile_value "${profile_file}" sector_access_lifetime_usefulness_32B)"
  spatial="$(profile_value "${profile_file}" sector_access_spatial_prefetch_benefit_per_record)"
  extra="$(profile_value "${profile_file}" sector_access_dynamic_extra_fetch_rate)"
  slot8="$(profile_value "${profile_file}" sector_access_same_row_slot_fill_rate_8B)"
  slot16="$(profile_value "${profile_file}" sector_access_same_row_slot_fill_rate_16B)"
  chop8_supply="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_supply_bytes)"
  chop8_ready="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_fill_rate)"
  chop8_full="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_full_tccd_fill_rate)"
  chop8_ideal="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_no_timing_fill_rate)"
  chop8_half="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_tccd_half_fill_rate)"
  chop8_loss="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_timing_limited_loss_rate)"
  chop8_recovered="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_tccd_half_recovered_rate)"
  chop8_no_candidate="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_no_candidate_rate)"
  chop8_timing="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_timing_blocked_rate)"
  chop8_bank="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_bank_conflict_rate)"
  chop8_full_gain="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_full_tccd_extra_bw_gain)"
  chop8_half_gain="$(profile_value "${profile_file}" sector_access_cross_bank_chop8_tccd_half_extra_bw_gain)"
  chop16_supply="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_supply_bytes)"
  chop16_ready="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_fill_rate)"
  chop16_full="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_full_tccd_fill_rate)"
  chop16_ideal="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_no_timing_fill_rate)"
  chop16_half="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_tccd_half_fill_rate)"
  chop16_loss="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_timing_limited_loss_rate)"
  chop16_recovered="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_tccd_half_recovered_rate)"
  chop16_no_candidate="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_no_candidate_rate)"
  chop16_timing="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_timing_blocked_rate)"
  chop16_bank="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_bank_conflict_rate)"
  chop16_full_gain="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_full_tccd_extra_bw_gain)"
  chop16_half_gain="$(profile_value "${profile_file}" sector_access_cross_bank_chop16_tccd_half_extra_bw_gain)"
  rowhit_candidates="$(profile_value "${profile_file}" sector_access_cross_bank_rowhit_candidate_count)"
  rowhit_ready="$(profile_value "${profile_file}" sector_access_cross_bank_rowhit_timing_ready_count)"
  avg_candidates="$(profile_value "${profile_file}" sector_access_cross_bank_avg_rowhit_candidates_per_chop8)"
  avg_ready="$(profile_value "${profile_file}" sector_access_cross_bank_avg_timing_ready_candidates_per_chop8)"
  cand8="$(profile_value "${profile_file}" sector_access_cross_bank_candidate_8B_ratio)"
  cand16="$(profile_value "${profile_file}" sector_access_cross_bank_candidate_16B_ratio)"
  cand32="$(profile_value "${profile_file}" sector_access_cross_bank_candidate_32B_ratio)"
  avg_age="$(profile_value "${profile_file}" sector_access_cross_bank_avg_candidate_age)"

  (
    flock 200
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "${rank}" "${suite}" "${bench}" "${dataset}" "${footprint_mib}" \
      "${footprint_bytes}" "${status}" "${exit_code}" "${seconds}" \
      "${records}" "${total_dram}" "${dyn8}" "${dyn16}" "${dyn32}" \
      "${lifetime}" "${spatial}" "${extra}" "${slot8}" "${slot16}" \
      "${eligible}" "${chop8_supply}" "${chop8_ready}" "${chop8_full}" \
      "${chop8_ideal}" "${chop8_half}" "${chop8_loss}" "${chop8_recovered}" \
      "${chop8_no_candidate}" "${chop8_timing}" "${chop8_bank}" \
      "${chop8_full_gain}" "${chop8_half_gain}" "${chop16_supply}" \
      "${chop16_ready}" "${chop16_full}" "${chop16_ideal}" "${chop16_half}" \
      "${chop16_loss}" "${chop16_recovered}" "${chop16_no_candidate}" \
      "${chop16_timing}" "${chop16_bank}" "${chop16_full_gain}" \
      "${chop16_half_gain}" "${rowhit_candidates}" "${rowhit_ready}" \
      "${avg_candidates}" "${avg_ready}" "${cand8}" "${cand16}" \
      "${cand32}" "${avg_age}" "${run_dir}" "${log}" >>"${SUMMARY}"
  ) 200>"${SUMMARY}.lock"
}

append_combined_csv() {
  local profile_file="$1"
  local suite="$2"
  local bench="$3"
  local dataset="$4"
  local footprint_mib="$5"
  local status="$6"

  local csv
  csv="$(awk -F' = ' '$1 == "sector_access_profile_csv" { print $2; exit }' "${profile_file}" 2>/dev/null || true)"
  if [[ -z "${csv}" ]]; then
    return
  fi

  (
    flock 201
    printf "%s,%s,%s,%s,%s,%s\n" \
      "${suite}" "${bench}" "${dataset}" "${footprint_mib}" "${status}" "${csv}" \
      >>"${COMBINED_CSV}"
  ) 201>"${COMBINED_CSV}.lock"

  csv="$(awk -F' = ' '$1 == "sector_access_cross_bank_profile_csv" { print $2; exit }' "${profile_file}" 2>/dev/null || true)"
  if [[ -z "${csv}" ]]; then
    return
  fi

  (
    flock 202
    printf "%s,%s,%s,%s,%s,%s\n" \
      "${suite}" "${bench}" "${dataset}" "${footprint_mib}" "${status}" "${csv}" \
      >>"${CROSS_BANK_CSV}"
  ) 202>"${CROSS_BANK_CSV}.lock"
}

run_payload() {
  local launch_dir="$1"
  local cmd="$2"

  (
    # shellcheck source=/dev/null
    source "${GPGPUSIM_ENV}"
    export SECTOR_GPGPUSIM_CONFIG="${SECTOR_GPGPUSIM_CONFIG:-${GPGPUSIM_A100_CONFIG}}"
    export MAKE_ARGS="${MAKE_ARGS:-}"
    cd "${launch_dir}"
    if [[ "${SIM_TIMEOUT}" == "0" || "${SIM_TIMEOUT}" == "none" ]]; then
      bash -c "${cmd}"
    else
      timeout "${SIM_TIMEOUT}s" bash -c "${cmd}"
    fi
  )
}

run_one_case() {
  local rank="$1"
  local suite="$2"
  local bench="$3"
  local dataset="$4"
  local footprint_mib="$5"
  local footprint_bytes="$6"
  local cmd="$7"

  local safe run_dir profile_file complete_file log launch_dir launch_backup start end seconds code status
  local lock_name lock_file
  safe="$(sanitize "$(printf "%03d_%s_%s_%s" "${rank}" "${suite}" "${bench}" "${dataset}")")"
  run_dir="${OUT_DIR}/${safe}"
  profile_file="${run_dir}/sector_access_profile.out"
  complete_file="${run_dir}/sector_access_profile.complete"
  log="${run_dir}/run.log"

  mkdir -p "${run_dir}"

  cmd="$(normalize_command "${suite}" "${bench}" "${dataset}" "${run_dir}" "${cmd}")"
  cmd="${cmd//$(dirname "${FOOTPRINT_SUMMARY}")/${run_dir}}"

  if [[ "${FORCE}" != "1" && -s "${profile_file}" && -s "${complete_file}" ]]; then
    status="$(profile_reuse_status "${profile_file}")"
    echo "== ${rank}: ${suite}/${bench}/${dataset} already done (${status}) =="
    record_summary "${rank}" "${suite}" "${bench}" "${dataset}" "${footprint_mib}" \
      "${footprint_bytes}" "${status}" "0" "0" "${run_dir}" "${profile_file}" \
      "${log}" "${cmd}"
    append_combined_csv "${profile_file}" "${suite}" "${bench}" "${dataset}" \
      "${footprint_mib}" "${status}"
    return
  elif [[ "${FORCE}" != "1" && -s "${profile_file}" ]]; then
    echo "== ${rank}: ${suite}/${bench}/${dataset} stale profile found; rerunning =="
  fi

  rm -f "${profile_file}" "${complete_file}" "${log}"
  write_config "${run_dir}" "${profile_file}"
  launch_dir="$(detect_launch_dir "${cmd}" "${run_dir}")"

  echo "== ${rank}: ${suite}/${bench}/${dataset} footprint=${footprint_mib}MiB =="
  echo "run_dir=${run_dir}"
  echo "launch_dir=${launch_dir}"

  start="$(date +%s)"
  set +e
  if [[ "${launch_dir}" == "${run_dir}" ]]; then
    launch_backup="$(install_launch_config "${run_dir}" "${launch_dir}")"
    run_payload "${launch_dir}" "${cmd}" >"${log}" 2>&1
    code=$?
    restore_launch_config "${launch_dir}" "${launch_backup}"
  else
    lock_name="$(sanitize "${launch_dir}")"
    lock_file="${GLOBAL_LAUNCH_LOCK_DIR}/${lock_name}.lock"
    (
      flock 202
      launch_backup="$(install_launch_config "${run_dir}" "${launch_dir}")"
      run_payload "${launch_dir}" "${cmd}" >"${log}" 2>&1
      code=$?
      restore_launch_config "${launch_dir}" "${launch_backup}"
      exit "${code}"
    ) 202>"${lock_file}"
    code=$?
  fi
  set -e
  end="$(date +%s)"
  seconds=$((end - start))

  if [[ "${code}" -eq 124 ]]; then
    status="TIMEOUT"
  elif [[ "${code}" -eq 0 && -s "${profile_file}" ]]; then
    if profile_has_zero_traffic "${profile_file}"; then
      status="NO_ELIGIBLE_READ_TRAFFIC"
    else
      status="PASS"
    fi
    write_complete_marker "${complete_file}" "${status}" "${code}" "${seconds}" "${profile_file}"
  elif [[ "${code}" -eq 0 ]]; then
    status="NO_PROFILE"
  else
    status="FAIL"
  fi

  record_summary "${rank}" "${suite}" "${bench}" "${dataset}" "${footprint_mib}" \
    "${footprint_bytes}" "${status}" "${code}" "${seconds}" "${run_dir}" \
    "${profile_file}" "${log}" "${cmd}"
  append_combined_csv "${profile_file}" "${suite}" "${bench}" "${dataset}" \
    "${footprint_mib}" "${status}"
}

run_selected_cases() {
  local active=0
  local rank suite bench dataset footprint_mib footprint_bytes cmd

  while IFS=$'\t' read -r rank suite bench dataset footprint_mib footprint_bytes cmd; do
    if [[ "${rank}" == "rank" ]]; then
      continue
    fi

    run_one_case "${rank}" "${suite}" "${bench}" "${dataset}" \
      "${footprint_mib}" "${footprint_bytes}" "${cmd}" &
    active=$((active + 1))

    if (( active >= JOBS )); then
      wait -n || true
      active=$((active - 1))
    fi
  done <"${SELECTED}"

  while (( active > 0 )); do
    wait -n || true
    active=$((active - 1))
  done
}

if [[ ! -f "${FOOTPRINT_SUMMARY}" ]]; then
  echo "Missing footprint summary: ${FOOTPRINT_SUMMARY}" >&2
  exit 2
fi

# shellcheck source=/dev/null
source "${GPGPUSIM_ENV}" >/dev/null
export SECTOR_GPGPUSIM_CONFIG="${SECTOR_GPGPUSIM_CONFIG:-${GPGPUSIM_A100_CONFIG}}"

make_selected_cases

printf "rank\tsuite\tbenchmark\tdataset\tfootprint_mib\tfootprint_bytes\tstatus\texit_code\tseconds\tsector_access_records\tsector_access_total_dram_bytes\tdynamic_8B_ratio\tdynamic_16B_ratio\tdynamic_32B_ratio\tlifetime_usefulness_32B\tspatial_prefetch_benefit_per_record\tdynamic_extra_fetch_rate\tsame_row_slot_fill_rate_8B\tsame_row_slot_fill_rate_16B\teligible_traffic_fraction\tchop8_supply_bytes\tchop8_otherwise_ready_fill_rate\tchop8_full_tccd_fill_rate\tchop8_no_timing_fill_rate\tchop8_tccd_half_fill_rate\tchop8_timing_limited_loss_rate\tchop8_tccd_half_recovered_rate\tchop8_no_candidate_rate\tchop8_timing_blocked_rate\tchop8_bank_conflict_rate\tchop8_full_tccd_extra_bw_gain\tchop8_tccd_half_extra_bw_gain\tchop16_supply_bytes\tchop16_otherwise_ready_fill_rate\tchop16_full_tccd_fill_rate\tchop16_no_timing_fill_rate\tchop16_tccd_half_fill_rate\tchop16_timing_limited_loss_rate\tchop16_tccd_half_recovered_rate\tchop16_no_candidate_rate\tchop16_timing_blocked_rate\tchop16_bank_conflict_rate\tchop16_full_tccd_extra_bw_gain\tchop16_tccd_half_extra_bw_gain\trowhit_candidate_count\trowhit_timing_ready_count\tavg_rowhit_candidates_per_chop8\tavg_timing_ready_candidates_per_chop8\tcandidate_8B_ratio\tcandidate_16B_ratio\tcandidate_32B_ratio\tavg_candidate_age\trun_dir\tlog\n" >"${SUMMARY}"
printf "suite,benchmark,dataset,footprint_mib,status,Benchmark,dynamic_8B_ratio,dynamic_16B_ratio,dynamic_32B_ratio,lifetime_usefulness_32B,spatial_prefetch_benefit_per_record,dynamic_extra_fetch_rate,same_row_slot_fill_rate_8B,same_row_slot_fill_rate_16B,eligible_traffic_fraction\n" >"${COMBINED_CSV}"
printf "suite,benchmark,dataset,footprint_mib,status,Benchmark,chop8_supply_bytes,chop8_otherwise_ready_fill_rate,chop8_full_tccd_fill_rate,chop8_no_timing_fill_rate,chop8_tccd_half_fill_rate,chop8_timing_limited_loss_rate,chop8_tccd_half_recovered_rate,chop8_full_tccd_unfilled_rate,chop8_no_candidate_rate,chop8_timing_blocked_rate,chop8_bank_conflict_rate,chop8_full_tccd_extra_bw_gain,chop8_tccd_half_extra_bw_gain,chop16_supply_bytes,chop16_otherwise_ready_fill_rate,chop16_full_tccd_fill_rate,chop16_no_timing_fill_rate,chop16_tccd_half_fill_rate,chop16_timing_limited_loss_rate,chop16_tccd_half_recovered_rate,chop16_full_tccd_unfilled_rate,chop16_no_candidate_rate,chop16_timing_blocked_rate,chop16_bank_conflict_rate,chop16_full_tccd_extra_bw_gain,chop16_tccd_half_extra_bw_gain,avg_rowhit_candidates_per_chop8,avg_timing_ready_candidates_per_chop8,avg_candidate_age\n" >"${CROSS_BANK_CSV}"

run_selected_cases

echo "selected=${SELECTED}"
echo "summary=${SUMMARY}"
echo "csv=${COMBINED_CSV}"

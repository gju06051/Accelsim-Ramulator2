#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="${MANIFEST:-${ROOT}/gpu_benchmark/benchmarks/inventory/sg_hbm_benchmark_manifest.tsv}"
OUT_DIR="${OUT_DIR:-${ROOT}/gpu_benchmark/sg_hbm_trace_classification}"
MAX_CASES="${MAX_CASES:-0}"
CASE_REGEX="${CASE_REGEX:-}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
RUN_BUDGET_SECONDS="${RUN_BUDGET_SECONDS:-0}"
MAX_RECORDS="${MAX_RECORDS:-5000000}"
MEMTRACE_MAX_RECORDS="${MEMTRACE_MAX_RECORDS:-200000}"
FORCE="${FORCE:-0}"

RUN_TRACE="${ROOT}/gpu_benchmark/scripts/run_with_nvbit_mem_trace.sh"
PARSER="${ROOT}/tools/nvbit_memtrace_to_trace.py"
CLASSIFIER="${ROOT}/tools/sg_hbm_classify_trace.py"
SUMMARY="${OUT_DIR}/summary.csv"
STATUS="${OUT_DIR}/status.tsv"

mkdir -p "${OUT_DIR}"

if [[ ! -f "${MANIFEST}" ]]; then
  echo "manifest not found: ${MANIFEST}" >&2
  exit 2
fi

printf "name\tsuite\texpected_class\tstatus\texit_code\ttrace_records\tpredicted_class\tseq_ratio\trow_temporal_hit_1KB\tsector_temporal_hit_256B\trow_util_1KB\tsector_reuse_256B\trun_dir\n" >"${STATUS}"
tmp_summary="${SUMMARY}.tmp"
rm -f "${tmp_summary}"

ran=0
start_seconds=${SECONDS}
{
  read -r _header
  while IFS=$'\t' read -r name suite expected_class workdir command main_reason; do
    [[ -z "${name}" ]] && continue
    if [[ -n "${CASE_REGEX}" && ! "${name}/${suite}/${expected_class}" =~ ${CASE_REGEX} ]]; then
      continue
    fi
    if [[ "${MAX_CASES}" != "0" && "${ran}" -ge "${MAX_CASES}" ]]; then
      break
    fi
    if [[ "${RUN_BUDGET_SECONDS}" != "0" && "$((SECONDS - start_seconds))" -ge "${RUN_BUDGET_SECONDS}" ]]; then
      echo "[SG-HBM] run budget exhausted after $((SECONDS - start_seconds))s; stopping before ${name}" >&2
      break
    fi

    run_dir="${OUT_DIR}/${name}"
    mkdir -p "${run_dir}"
    raw_log="${run_dir}/${name}.nvbit.raw.log"
    trace="${run_dir}/${name}.mem.trace"
    class_out="${run_dir}/${name}.classify.out"
    class_csv="${run_dir}/${name}.classify.csv"
    complete="${run_dir}/complete"
    partial="${run_dir}/partial"

    if [[ "${FORCE}" != "1" && -f "${complete}" ]]; then
      if [[ -f "${partial}" ]]; then
        status="PARTIAL_SKIP"
      else
        status="SKIP"
      fi
      exit_code=0
    else
      rm -f "${complete}" "${partial}"
      echo "[SG-HBM] tracing ${name} (${suite}, expected=${expected_class})"
      read -r -a cmd_argv <<<"${command}"
      set +e
      RUN_WORKDIR="${ROOT}/${workdir}" MEMTRACE_MAX_RECORDS="${MEMTRACE_MAX_RECORDS}" \
        timeout "${TIMEOUT_SECONDS}" \
        "${RUN_TRACE}" "${name}" "${run_dir}" -- \
        "${cmd_argv[@]}"
      exit_code=$?
      set -e
      if [[ "${exit_code}" == "0" && -s "${trace}" ]]; then
        status="TRACE_OK"
        touch "${complete}"
      else
        if [[ -s "${raw_log}" ]]; then
          set +e
          "${PARSER}" "${raw_log}" -o "${trace}" >&2
          parse_exit=$?
          set -e
        else
          parse_exit=1
        fi

        if [[ "${parse_exit}" == "0" && -s "${trace}" ]]; then
          status="TRACE_PARTIAL"
          touch "${complete}" "${partial}"
        else
          status="TRACE_FAIL"
        fi
      fi
    fi

    predicted="NA"
    records="NA"
    seq_ratio="NA"
    row_temporal="NA"
    sector_temporal="NA"
    row_util="NA"
    sector_reuse="NA"

    if [[ "${status}" == "TRACE_OK" || "${status}" == "TRACE_PARTIAL" || "${status}" == "SKIP" || "${status}" == "PARTIAL_SKIP" ]]; then
      set +e
      "${CLASSIFIER}" "${trace}" \
        --name "${name}" \
        --suite "${suite}" \
        --expected-class "${expected_class}" \
        --max-records "${MAX_RECORDS}" \
        --csv "${class_csv}" >"${class_out}" 2>&1
      class_exit=$?
      set -e
      if [[ "${class_exit}" == "0" && -s "${class_csv}" ]]; then
        predicted="$(awk -F= '$1=="predicted_class"{print $2}' "${class_out}")"
        records="$(awk -F= '$1=="records"{print $2}' "${class_out}")"
        seq_ratio="$(awk -F= '$1=="seq_ratio"{print $2}' "${class_out}")"
        row_temporal="$(awk -F= '$1=="row_temporal_hit_1KB"{print $2}' "${class_out}")"
        sector_temporal="$(awk -F= '$1=="sector_temporal_hit_256B"{print $2}' "${class_out}")"
        row_util="$(awk -F= '$1=="row_util_1KB"{print $2}' "${class_out}")"
        sector_reuse="$(awk -F= '$1=="sector_reuse_256B"{print $2}' "${class_out}")"
        if [[ ! -f "${tmp_summary}" ]]; then
          cat "${class_csv}" >"${tmp_summary}"
        else
          tail -n +2 "${class_csv}" >>"${tmp_summary}"
        fi
      else
        status="CLASSIFY_FAIL"
      fi
    fi

    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "${name}" "${suite}" "${expected_class}" "${status}" "${exit_code}" \
      "${records}" "${predicted}" "${seq_ratio}" "${row_temporal}" \
      "${sector_temporal}" "${row_util}" "${sector_reuse}" \
      "${run_dir}" >>"${STATUS}"
    ran=$((ran + 1))
  done
} <"${MANIFEST}"

if [[ -f "${tmp_summary}" ]]; then
  mv "${tmp_summary}" "${SUMMARY}"
else
  printf "benchmark,suite,expected_class,predicted_class,main_reason,records,reads,writes,write_ratio,bytes_requested,avg_request_size_B,atom_touches,seq_ratio,row_temporal_hit_1KB,sector_temporal_hit_256B,row_util_1KB,sector_reuse_256B,rows_touched,sectors_256B_touched,trace_truncated\n" >"${SUMMARY}"
fi

echo "status=${STATUS}"
echo "summary=${SUMMARY}"

#!/usr/bin/env python3
"""Run a bounded Accel-Sim backend benchmark matrix.

The runs are intentionally capped with -gpgpu_max_cycle.  For this integration
smoke test, reaching the cap after the requested backend is constructed and
kernels launch is treated as a healthy bounded run, not as a benchmark failure.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from shlex import quote, split


INTEGRATION_ROOT = Path(__file__).resolve().parents[1]


def env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


DEFAULT_WORKSPACE_ROOT = (
    INTEGRATION_ROOT.parents[1]
    if INTEGRATION_ROOT.parent.name == "simulator"
    else INTEGRATION_ROOT.parent
)
WORKSPACE_ROOT = env_path("SGRAM_WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT)


def default_simulator_root(name: str) -> Path:
    direct = WORKSPACE_ROOT / name
    nested = WORKSPACE_ROOT / "simulator" / name
    return direct if direct.exists() else nested


GPGPU_ROOT = env_path("SGRAM_GPGPU_ROOT", default_simulator_root("gpgpu-sim_distribution"))
RAMULATOR2_ROOT = env_path("SGRAM_RAMULATOR2_ROOT", default_simulator_root("ramulator2"))
GPU_BENCHMARK_ROOT = env_path("SGRAM_GPU_BENCHMARK_ROOT", WORKSPACE_ROOT / "gpu_benchmark")
GPGPU_BUILD = env_path("SGRAM_GPGPU_BUILD", GPGPU_ROOT / "build" / "sgram_fixed")
GPGPU_SETUP = GPGPU_ROOT / "setup"
GPGPU_CONFIG = env_path(
    "SGRAM_GPGPU_CONFIG",
    GPGPU_ROOT / "configs" / "tested-cfgs" / "SM80_A100" / "gpgpusim.config",
)
GPU_APP_BIN = (
    GPU_BENCHMARK_ROOT
    / "common"
    / "gpu-app-collection-harness"
    / "bin"
    / "12.3"
    / "release"
)
GRAPHBIG_GPU = GPU_BENCHMARK_ROOT / "suites" / "graphBIG" / "gpu_bench"
GRAPHBIG_DATA = GPU_BENCHMARK_ROOT / "suites" / "graphBIG" / "dataset" / "small"
PARBOIL_DATA = GPU_BENCHMARK_ROOT / "common" / "gpu-app-collection-harness" / "data_dirs" / "parboil" / "datasets"
LOCAL_BENCHMARK_DIR = INTEGRATION_ROOT / "benchmarks"
GPU_BENCHMARK_MAIN_DIR = GPU_BENCHMARK_ROOT / "benchmarks" / "main"
GPU_BENCHMARK_INVENTORY_DIR = GPU_BENCHMARK_ROOT / "benchmarks" / "inventory"
MANIFEST_MAIN = GPU_BENCHMARK_MAIN_DIR / "manifest.tsv"
MANIFEST_OPERATIONAL = LOCAL_BENCHMARK_DIR / "operational_manifest.tsv"
MANIFEST_FINAL = LOCAL_BENCHMARK_DIR / "final_manifest.tsv"
MANIFEST_BROAD = GPU_BENCHMARK_INVENTORY_DIR / "sg_hbm_benchmark_manifest_broad.tsv"
MANIFEST_EXTRA_BUILT = GPU_BENCHMARK_INVENTORY_DIR / "sg_hbm_benchmark_manifest_extra_built.tsv"
MANIFEST_EXTRA_VALIDATED = GPU_BENCHMARK_INVENTORY_DIR / "sg_hbm_benchmark_manifest_extra_validated.tsv"
MANIFEST_MORE_SUITES_BUILT = GPU_BENCHMARK_INVENTORY_DIR / "sg_hbm_benchmark_manifest_more_suites_built.tsv"
MANIFEST_MORE_SUITES_VALIDATED = GPU_BENCHMARK_INVENTORY_DIR / "sg_hbm_benchmark_manifest_more_suites_validated.tsv"
DEFAULT_RAMULATOR_CONFIG = env_path(
    "SGRAM_RAMULATOR_CONFIG",
    INTEGRATION_ROOT / "configs" / "ramulator" / "hbm4.yaml",
)
RAMULATOR_GENERIC_BUFFER_ENTRIES_PER_CHANNEL = 32
RAMULATOR_READ_SIDE_BUFFERS_PER_CHANNEL = 2
A100_L2_8MB_CONFIG = "S:32:128:13,L:B:m:L:X,A:192:4,32:0,32"
A100_HBM_ADDR_MAPPING = (
    "-gpgpu_mem_addr_mapping "
    "dramid@8;00000000.00000000.00000000.00000000."
    "0000RRRR.RRRRRRRR.RBBBCCCC.BCCSSSSS"
)
A100_1STACK_OVERRIDES: tuple[str, ...] = (
    "-gpgpu_n_clusters 22",
    "-gpgpu_n_mem 8",
)
A100_5STACK_OVERRIDES: tuple[str, ...] = (
    "-gpgpu_n_clusters 108",
    "-gpgpu_n_mem 40",
    "-gpgpu_n_sub_partition_per_mchannel 4",
    "-gpgpu_memory_partition_indexing 2",
    "-gpgpu_mem_address_mask 1",
    A100_HBM_ADDR_MAPPING,
)
H100_HBM_ADDR_MAPPING = A100_HBM_ADDR_MAPPING
H100_1STACK_OVERRIDES: tuple[str, ...] = (
    "-gpgpu_n_clusters 26",
    "-gpgpu_clock_domains 1980:1980:1980:1309",
    "-ptx_opcode_initiation_fp 1,1,1,1,2",
    "-gpgpu_shmem_option 0,8,16,32,64,100,132,164,196,228",
    "-gpgpu_unified_l1d_size 256",
    "-gpgpu_shmem_size 233472",
    "-gpgpu_shmem_sizeDefault 233472",
    "-gpgpu_n_mem 16",
    "-gpgpu_n_sub_partition_per_mchannel 2",
    "-gpgpu_cache:dl2 S:128:128:20,L:B:m:L:X,A:192:4,32:0,32",
    "-gpgpu_memory_partition_indexing 2",
    "-gpgpu_mem_address_mask 1",
    H100_HBM_ADDR_MAPPING,
)
H100_FULL_OVERRIDES: tuple[str, ...] = (
    "-gpgpu_n_clusters 132",
    "-gpgpu_clock_domains 1980:1980:1980:1309",
    "-ptx_opcode_initiation_fp 1,1,1,1,2",
    "-gpgpu_shmem_option 0,8,16,32,64,100,132,164,196,228",
    "-gpgpu_unified_l1d_size 256",
    "-gpgpu_shmem_size 233472",
    "-gpgpu_shmem_sizeDefault 233472",
    "-gpgpu_n_mem 80",
    "-gpgpu_n_sub_partition_per_mchannel 2",
    "-gpgpu_cache:dl2 S:128:128:20,L:B:m:L:X,A:192:4,32:0,32",
    "-gpgpu_memory_partition_indexing 2",
    "-gpgpu_mem_address_mask 1",
    H100_HBM_ADDR_MAPPING,
)
CONFIG_VARIANTS: dict[str, tuple[str, ...]] = {
    "a100_full": (),
    "a100_1stack": A100_1STACK_OVERRIDES,
    "a100_5stack": A100_5STACK_OVERRIDES,
    "h100_1stack": H100_1STACK_OVERRIDES,
    "h100_full": H100_FULL_OVERRIDES,
}


@dataclass(frozen=True)
class Benchmark:
    name: str
    suite: str
    command: tuple[str, ...]
    workdir: str = "."
    expected_class: str = ""
    main_reason: str = ""


CORE_BENCHMARKS: tuple[Benchmark, ...] = (
    Benchmark("polybench_2dconv", "polybench", ("polybench-2DConvolution",)),
    Benchmark("polybench_2mm", "polybench", ("polybench-2mm",)),
    Benchmark("polybench_3dconv", "polybench", ("polybench-3DConvolution",)),
    Benchmark("polybench_3mm", "polybench", ("polybench-3mm",)),
    Benchmark("polybench_atax", "polybench", ("polybench-atax",)),
    Benchmark("polybench_bicg", "polybench", ("polybench-bicg",)),
    Benchmark("polybench_correlation", "polybench", ("polybench-correlation",)),
    Benchmark("polybench_covariance", "polybench", ("polybench-covariance",)),
    Benchmark("polybench_fdtd2d", "polybench", ("polybench-fdtd2d",)),
    Benchmark("polybench_gemm", "polybench", ("polybench-gemm",)),
    Benchmark("polybench_gesummv", "polybench", ("polybench-gesummv",)),
    Benchmark("polybench_gramschmidt", "polybench", ("polybench-gramschmidt",)),
    Benchmark("polybench_mvt", "polybench", ("polybench-mvt",)),
    Benchmark("polybench_syr2k", "polybench", ("polybench-syr2k",)),
    Benchmark("polybench_syrk", "polybench", ("polybench-syrk",)),
    Benchmark("micro_mem_lat", "microbench", ("mem_lat",)),
    Benchmark("ispass_lib", "ispass-2009", ("ispass-2009-LIB",)),
    Benchmark("ispass_lps", "ispass-2009", ("ispass-2009-LPS",)),
    Benchmark("micro_mem_bw", "microbench", ("mem_bw",)),
    Benchmark("ispass_nqu", "ispass-2009", ("ispass-2009-NQU",)),
    Benchmark("ispass_ray", "ispass-2009", ("ispass-2009-RAY", "256", "256")),
    Benchmark("ispass_sto", "ispass-2009", ("ispass-2009-STO",)),
)

GRAPHBIG_BENCHMARKS: tuple[Benchmark, ...] = (
    Benchmark(
        "graphbig_bfs_data_thread",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BFS" / "bfs_data_thread_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_bfs_data_warp",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BFS" / "bfs_data_warp_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_bfs_topo_atomic",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BFS" / "bfs_topo_atomic"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_bfs_topo_frontier",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BFS" / "bfs_topo_frontier"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_bfs_topo_thread",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BFS" / "bfs_topo_thread_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_bfs_topo_unroll",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BFS" / "bfs_topo_unroll"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_bfs_topo_warp",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BFS" / "bfs_topo_warp_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_betweenness",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_BetweennessCentr" / "betweenness"), "--dataset", str(GRAPHBIG_DATA)),
    ),
    Benchmark(
        "graphbig_connected_comp",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_ConnectedComp" / "connected_comp"), "--dataset", str(GRAPHBIG_DATA)),
    ),
    Benchmark(
        "graphbig_degree_centr",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_DegreeCentr" / "degree_centr"), "--dataset", str(GRAPHBIG_DATA)),
    ),
    Benchmark(
        "graphbig_gc_topo_thread",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_GraphColoring" / "gc_topo_thread_centric"), "--dataset", str(GRAPHBIG_DATA)),
    ),
    Benchmark(
        "graphbig_kcore",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_kCore" / "kcore"), "--dataset", str(GRAPHBIG_DATA)),
    ),
    Benchmark(
        "graphbig_sssp_data_thread",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_SSSP" / "sssp_data_thread_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_sssp_data_warp",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_SSSP" / "sssp_data_warp_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_sssp_topo_thread",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_SSSP" / "sssp_topo_thread_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_sssp_topo_warp",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_SSSP" / "sssp_topo_warp_centric"), "--dataset", str(GRAPHBIG_DATA), "--root", "31"),
    ),
    Benchmark(
        "graphbig_triangle_count",
        "graphBIG",
        (str(GRAPHBIG_GPU / "gpu_TriangleCount" / "triangle_count"), "--dataset", str(GRAPHBIG_DATA)),
    ),
)

def load_manifest_benchmarks(path: Path) -> tuple[Benchmark, ...]:
    if not path.exists():
        return ()
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = csv.DictReader(f, delimiter="\t")
        return tuple(
            Benchmark(
                name=row["name"],
                suite=row["suite"],
                command=tuple(split(row["command"])),
                workdir=row.get("workdir", ".") or ".",
                expected_class=row.get("expected_class", ""),
                main_reason=row.get("main_reason", ""),
            )
            for row in rows
            if row.get("name") and row.get("command")
        )


MANIFEST_MAIN_BENCHMARKS = load_manifest_benchmarks(MANIFEST_MAIN)
MANIFEST_OPERATIONAL_BENCHMARKS = load_manifest_benchmarks(MANIFEST_OPERATIONAL)
MANIFEST_FINAL_BENCHMARKS = load_manifest_benchmarks(MANIFEST_FINAL)
MANIFEST_BROAD_BENCHMARKS = load_manifest_benchmarks(MANIFEST_BROAD)
MANIFEST_EXTRA_BUILT_BENCHMARKS = load_manifest_benchmarks(MANIFEST_EXTRA_BUILT)
MANIFEST_EXTRA_VALIDATED_BENCHMARKS = load_manifest_benchmarks(MANIFEST_EXTRA_VALIDATED)
MANIFEST_MORE_SUITES_BUILT_BENCHMARKS = load_manifest_benchmarks(MANIFEST_MORE_SUITES_BUILT)
MANIFEST_MORE_SUITES_VALIDATED_BENCHMARKS = load_manifest_benchmarks(MANIFEST_MORE_SUITES_VALIDATED)


BENCHMARK_PRESETS: dict[str, tuple[Benchmark, ...]] = {
    "core": CORE_BENCHMARKS,
    "graphbig": GRAPHBIG_BENCHMARKS,
    "accelsim_ramulator_main": MANIFEST_MAIN_BENCHMARKS or MANIFEST_FINAL_BENCHMARKS,
    "accelsim_ramulator_operational": MANIFEST_OPERATIONAL_BENCHMARKS,
    "accelsim_ramulator_final": MANIFEST_FINAL_BENCHMARKS,
    "stackganged": CORE_BENCHMARKS + GRAPHBIG_BENCHMARKS,
    "stackganged_operational": MANIFEST_OPERATIONAL_BENCHMARKS,
    "stackganged_broad": MANIFEST_BROAD_BENCHMARKS or (CORE_BENCHMARKS + GRAPHBIG_BENCHMARKS),
    "stackganged_extra_built": MANIFEST_EXTRA_BUILT_BENCHMARKS,
    "stackganged_extra_validated": MANIFEST_EXTRA_VALIDATED_BENCHMARKS,
    "stackganged_more_suites_built": MANIFEST_MORE_SUITES_BUILT_BENCHMARKS,
    "stackganged_more_suites_validated": MANIFEST_MORE_SUITES_VALIDATED_BENCHMARKS,
    "stackganged_all_built": (MANIFEST_BROAD_BENCHMARKS or (CORE_BENCHMARKS + GRAPHBIG_BENCHMARKS))
    + MANIFEST_EXTRA_BUILT_BENCHMARKS
    + MANIFEST_MORE_SUITES_BUILT_BENCHMARKS,
    "stackganged_all_validated": MANIFEST_OPERATIONAL_BENCHMARKS
    or (MANIFEST_BROAD_BENCHMARKS or (CORE_BENCHMARKS + GRAPHBIG_BENCHMARKS))
    + MANIFEST_EXTRA_VALIDATED_BENCHMARKS
    + MANIFEST_MORE_SUITES_VALIDATED_BENCHMARKS,
}
BENCHMARKS: tuple[Benchmark, ...] = BENCHMARK_PRESETS["core"]


# GPGPU-Sim may interleave md5/PTX extraction output with backend init lines;
# keep the partition/queue tail form so a split "backend enabled" line still counts.
ENABLED_RE = re.compile(
    r"(?:SGRAM (?:fixed-latency|Ramulator2) backend enabled: )?"
    r"(?:partition|tion|ion)=(\d+) queue_limit=\d+"
)
BACKEND_PRINT_RE = re.compile(r"SGRAM (?:fixed|Ramulator2) backend partition (\d+):")
BACKEND_PARTITION_STAT_RE = re.compile(
    r"SGRAM Ramulator2 backend partition (\d+): .*?"
    r"accepted_reads=(\d+) completed_reads=(\d+) "
    r"accepted_writes=(\d+) rejected=(\d+)"
    r"(?: rejected_inflight=(\d+) rejected_ramulator=(\d+) "
    r"backend_full=(\d+) global_inflight_reads=(\d+) inflight_limit=(\d+))?"
)
BACKEND_RAMULATOR_STAT_RE = re.compile(
    r"SGRAM Ramulator2 backend partition (?P<partition>\d+): .*?"
    r"bridge_ticks=(?P<ticks>\d+) .*?"
    r"accepted_reads=(?P<reads>\d+) completed_reads=(?P<completed_reads>\d+) "
    r"accepted_writes=(?P<writes>\d+)"
)
RAMULATOR_BRIDGE_CREATED_RE = re.compile(
    r"SGRAM Ramulator2 bridge created: .*?"
    r"tCK=(?P<tck>[0-9.]+) ns .*?"
    r"accelsim_dram_freq_mhz=(?P<accel_dram>[0-9.-]+) "
    r"ramulator_mhz=(?P<ramulator_mhz>[0-9.-]+) .*?"
    r"ticks_per_dram_cycle=(?P<ticks>[0-9.]+) source=(?P<source>[A-Za-z0-9_]+)"
)
LAUNCH_RE = re.compile(r"GPGPU-Sim PTX: cudaLaunch")
STAT_RE = re.compile(r"^([A-Za-z0-9_]+)\s*=\s*([0-9.]+)")
RAMULATOR_YAML_STAT_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_]*):\s*"
    r"([+-]?(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|\.nan|nan|inf|\.inf))\s*$",
    re.IGNORECASE,
)
HOST_TIMING_STAGES = (
    "clock",
    "core_icnt",
    "mem_to_icnt",
    "dram",
    "l2",
    "icnt_transfer",
    "core_pipeline",
    "power_model",
    "core_bookkeeping",
    "runtime_stats",
    "total",
)


def parse_csv_ints(text: str) -> list[int]:
    values: list[int] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item, 0))
    return values


def shell_join(items: tuple[str, ...] | list[str]) -> str:
    return " ".join(quote(str(item)) for item in items)


def expand_manifest_arg(arg: str) -> list[str]:
    if arg == "@parboil_tpacf_small_inputs":
        input_dir = PARBOIL_DATA / "tpacf" / "small" / "input"
        inputs = [input_dir / "Datapnts.1"] + [input_dir / f"Randompnts.{idx}" for idx in range(1, 101)]
        return [",".join(str(path) for path in inputs)]
    return [arg]


def resolve_workspace_path(path_arg: Path) -> Path:
    if path_arg.is_absolute():
        return path_arg.resolve(strict=False)
    if path_arg.parts and path_arg.parts[0] == "gpu_benchmark":
        return GPU_BENCHMARK_ROOT.joinpath(*path_arg.parts[1:]).resolve(strict=False)
    return (WORKSPACE_ROOT / path_arg).resolve(strict=False)


def resolve_input_path(path_arg: Path) -> Path:
    if path_arg.is_absolute():
        return path_arg.resolve(strict=False)
    candidates = [
        (Path.cwd() / path_arg).resolve(strict=False),
        (INTEGRATION_ROOT / path_arg).resolve(strict=False),
        (WORKSPACE_ROOT / path_arg).resolve(strict=False),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_manifest_executable(command0: Path, workdir: str) -> Path:
    if command0.is_absolute():
        return command0
    if command0.parts and command0.parts[0] == "gpu_benchmark":
        return resolve_workspace_path(command0)
    if command0.parent != Path("."):
        base = Path(workdir)
        if workdir != "." and not base.is_absolute():
            command0 = base / command0
        return resolve_workspace_path(command0)
    return GPU_APP_BIN / command0


def absolutize_repo_path_arg(arg: str) -> str:
    parts = arg.split(",")
    resolved_parts: list[str] = []
    for part in parts:
        path_arg = Path(part)
        if not path_arg.is_absolute() and path_arg.parts and path_arg.parts[0] == "gpu_benchmark":
            resolved_parts.append(str(resolve_workspace_path(path_arg)))
        else:
            resolved_parts.append(part)
    return ",".join(resolved_parts)


def benchmark_command(bench: Benchmark) -> list[str]:
    command0 = Path(bench.command[0])
    exe = resolve_manifest_executable(command0, bench.workdir)

    args: list[str] = []
    for arg in bench.command[1:]:
        for expanded_arg in expand_manifest_arg(arg):
            args.append(absolutize_repo_path_arg(expanded_arg))
    return [str(exe), *args]


def gpgpusim_option_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or not stripped.startswith("-"):
        return None
    return stripped.split(maxsplit=1)[0]


def collapse_gpgpusim_config(lines: list[str]) -> list[str]:
    last_option_line: dict[str, int] = {}
    for index, line in enumerate(lines):
        key = gpgpusim_option_key(line)
        if key:
            last_option_line[key] = index

    return [
        line
        for index, line in enumerate(lines)
        if not (
            (key := gpgpusim_option_key(line))
            and last_option_line[key] != index
        )
    ]


def write_config(
    run_dir: Path,
    source_config: Path,
    max_cycle: int,
    l2_cache_config: str,
    config_overrides: tuple[str, ...],
    override_files: tuple[Path, ...],
    gpgpusim_host_timing: str,
) -> None:
    generated_lines = [
        "# Generated by run_fixed_backend_matrix.py\n",
        "# Duplicate GPGPU-Sim options are collapsed after applying all overrides.\n",
        f"# base_config: {source_config}\n",
        "\n",
    ]
    source_text = source_config.read_text(encoding="utf-8")
    generated_lines.extend(source_text.splitlines(keepends=True))
    if source_text and not source_text.endswith("\n"):
        generated_lines.append("\n")

    generated_lines.append("\n# AccelSim + Ramulator2 effective overrides\n")
    if l2_cache_config:
        generated_lines.append(f"-gpgpu_cache:dl2 {l2_cache_config}\n")
    if config_overrides:
        generated_lines.append("# inline/variant overrides\n")
        generated_lines.extend(f"{override}\n" for override in config_overrides)
    for override_file in override_files:
        generated_lines.append(f"# override_file: {override_file}\n")
        text = override_file.read_text(encoding="utf-8")
        generated_lines.extend(text.splitlines(keepends=True))
        if text and not text.endswith("\n"):
            generated_lines.append("\n")
    generated_lines.extend(
        (
            f"-gpgpu_max_cycle {max_cycle}\n",
            "-gpgpu_kernel_launch_latency 0\n",
            "-gpgpu_runtime_stat 1000000000\n",
            f"-gpgpu_host_timing {1 if gpgpusim_host_timing == 'on' else 0}\n",
            "-liveness_message_freq 1000000\n",
        )
    )

    effective_lines = collapse_gpgpusim_config(generated_lines)
    (run_dir / "gpgpusim.config").write_text("".join(effective_lines), encoding="utf-8")


def prepare_ramulator_config(run_dir: Path, source_config: Path) -> Path:
    copied_config = run_dir / "ramulator2.yaml"
    shutil.copyfile(source_config, copied_config)
    return copied_config.resolve()


def infer_ramulator_channels(ramulator_config: Path) -> int:
    text = ramulator_config.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"(?m)^\s*channel\s*:\s*(\d+)\s*(?:#.*)?$", text)
    if not matches:
        raise ValueError(f"could not infer DRAM channel count from {ramulator_config}")
    return int(matches[-1])


def resolve_ramulator_inflight_read_limit(value: str, ramulator_config: Path) -> int:
    normalized = str(value).strip().lower()
    if normalized == "auto":
        channels = infer_ramulator_channels(ramulator_config)
        return (
            channels
            * RAMULATOR_GENERIC_BUFFER_ENTRIES_PER_CHANNEL
            * RAMULATOR_READ_SIDE_BUFFERS_PER_CHANNEL
        )
    try:
        parsed = int(str(value), 0)
    except ValueError as exc:
        raise ValueError(
            "--ramulator-inflight-read-limit must be an integer or 'auto'"
        ) from exc
    if parsed < 0:
        raise ValueError("--ramulator-inflight-read-limit must be non-negative")
    return parsed


def prepare_benchmark_inputs(bench: Benchmark, run_dir: Path) -> None:
    if bench.name == "ispass_bfs":
        (run_dir / "SampleGraph.txt").write_text(
            "\n".join(
                [
                    "4",
                    "0 2",
                    "2 1",
                    "3 1",
                    "4 0",
                    "0",
                    "4",
                    "1 1",
                    "2 1",
                    "3 1",
                    "3 1",
                    "",
                ]
            ),
            encoding="ascii",
        )
    elif bench.name == "ispass_nn":
        data_dir = run_dir / "data"
        data_dir.mkdir(exist_ok=True)
        for filename, count in (
            ("lw1.wei", 156),
            ("lw2.wei", 7800),
            ("lw3.wei", 125100),
            ("lw4.wei", 1010),
        ):
            (data_dir / filename).write_bytes(struct.pack("<f", 0.01) * count)

        num_images = 28
        if len(bench.command) > 1:
            try:
                num_images = max(num_images, int(bench.command[1]))
            except ValueError:
                pass
        with (data_dir / "t10k-images-idx3-ubyte").open("wb") as f:
            f.write((2051).to_bytes(4, "big"))
            f.write(num_images.to_bytes(4, "big"))
            f.write((28).to_bytes(4, "big"))
            f.write((28).to_bytes(4, "big"))
            f.write(bytes([0x40]) * 28 * 28 * num_images)
    elif bench.name == "rodinia_myocyte":
        data_dir = run_dir.parent.parent / "data" / "myocyte"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "y.txt").write_text("\n".join(["1.0"] * 91) + "\n", encoding="ascii")
        (data_dir / "params.txt").write_text("\n".join(["1.0"] * 18) + "\n", encoding="ascii")
    elif bench.name == "rodinia_nn":
        src = GPU_BENCHMARK_ROOT / "common" / "gpu-app-collection-harness" / "src" / "cuda" / "rodinia" / "3.1"
        data_src = src / "data" / "nn"
        data_dir = run_dir / "data"
        data_dir.mkdir(exist_ok=True)
        for item in data_src.glob("cane4_*.db"):
            link = data_dir / item.name
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(item)
        (run_dir / "filelist_4").write_text(
            "\n".join(f"data/cane4_{idx}.db" for idx in range(4)) + "\n",
            encoding="ascii",
        )


def classify_status(exit_code: int, timed_out: bool, stdout: str, stderr: str, require_backend: bool) -> str:
    enabled = bool(ENABLED_RE.search(stdout))
    launched = bool(LAUNCH_RE.search(stdout))
    max_cycle = "break due to reaching the maximum cycles" in stdout
    dumped = "dumped core" in stderr.lower()
    crash_code = exit_code in (134, 139, -6, -11)
    ready = launched and (enabled or not require_backend)

    if timed_out:
        if ready:
            return "TIMEBOX_OK"
        return "TIMEOUT"
    if dumped or crash_code:
        return "CRASH"
    if ready and max_cycle:
        return "MAX_CYCLE_OK"
    if exit_code == 0 and ready:
        return "OK"
    if exit_code == 0 and enabled and require_backend:
        return "BACKEND_STARTED_NO_KERNEL"
    if exit_code == 0 and not require_backend:
        return "OK"
    if enabled:
        return "BACKEND_STARTED_ERROR"
    return "NO_BACKEND"


def extract_last_numeric(stdout: str, key: str) -> str:
    value = ""
    prefix = f"{key} ="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            value = line.split("=", 1)[1].strip().split()[0]
    return value


def extract_clock_domains(config_path: Path) -> tuple[str, str, str, str]:
    domains = ""
    for line in config_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("-gpgpu_clock_domains "):
            domains = stripped.split(None, 1)[1].split("#", 1)[0].strip()
    parts = domains.split(":")
    if len(parts) != 4:
        return ("", "", "", "")
    return tuple(parts)  # type: ignore[return-value]


def extract_ramulator_clock_stats(stdout: str) -> dict[str, str]:
    match = None
    for match in RAMULATOR_BRIDGE_CREATED_RE.finditer(stdout):
        pass
    if not match:
        return {
            "ramulator_tck_ns": "",
            "ramulator_mhz": "",
            "ramulator_effective_ticks_per_dram_cycle": "",
            "ramulator_tick_source": "",
        }
    return {
        "ramulator_tck_ns": match.group("tck"),
        "ramulator_mhz": match.group("ramulator_mhz"),
        "ramulator_effective_ticks_per_dram_cycle": match.group("ticks"),
        "ramulator_tick_source": match.group("source"),
    }


def extract_host_timing_stats(stdout: str) -> dict[str, str]:
    stats = {
        "gpgpusim_host_timing_enabled": extract_last_numeric(
            stdout, "gpgpusim_host_timing_enabled"
        )
    }
    for stage in HOST_TIMING_STAGES:
        for suffix in ("us", "calls", "pct"):
            key = f"gpgpusim_host_timing_{stage}_{suffix}"
            stats[key] = extract_last_numeric(stdout, key)
    return stats


def compute_ratio(numer: str, denom: str) -> str:
    try:
        n = float(numer)
        d = float(denom)
    except ValueError:
        return ""
    if d == 0:
        return ""
    return f"{n / d:.6f}"


def format_int_list(values: list[int]) -> str:
    return ",".join(str(value) for value in values)


def compute_cv(values: list[int]) -> str:
    if not values:
        return ""
    mean = sum(values) / len(values)
    if mean == 0:
        return ""
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return f"{(variance ** 0.5) / mean:.6f}"


def parse_ramulator_scalar(value: str) -> float | int | None:
    value = value.strip()
    lower = value.lower()
    if lower in {".nan", "nan", "+nan", "-nan", ".inf", "inf", "+inf", "-inf"}:
        return None
    try:
        if any(ch in value for ch in ".eE"):
            return float(value)
        return int(value, 0)
    except ValueError:
        return None


def format_float(value: float) -> str:
    return f"{value:.6f}"


def format_numeric(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return format_float(value)


def empty_ramulator_stats() -> dict[str, str | int]:
    return {
        "ramulator_stats_present": 0,
        "ramulator_stats_source": "",
        "ramulator_memory_system_cycles": "",
        "ramulator_total_num_read_requests": "",
        "ramulator_total_num_write_requests": "",
        "ramulator_num_read_reqs": "",
        "ramulator_num_write_reqs": "",
        "ramulator_row_hits": "",
        "ramulator_row_misses": "",
        "ramulator_row_conflicts": "",
        "ramulator_read_row_hits": "",
        "ramulator_read_row_misses": "",
        "ramulator_read_row_conflicts": "",
        "ramulator_write_row_hits": "",
        "ramulator_write_row_misses": "",
        "ramulator_write_row_conflicts": "",
        "ramulator_read_latency": "",
        "ramulator_avg_read_latency": "",
        "ramulator_queue_len_avg_sum": "",
        "ramulator_read_queue_len_avg_sum": "",
        "ramulator_write_queue_len_avg_sum": "",
        "ramulator_priority_queue_len_avg_sum": "",
        "ramulator_num_read_reqs_by_channel": "",
        "ramulator_row_hits_by_channel": "",
        "ramulator_row_misses_by_channel": "",
        "ramulator_row_conflicts_by_channel": "",
        "ramulator_avg_read_latency_by_channel": "",
        "ramulator_queue_len_avg_by_channel": "",
        "ramulator_read_queue_len_avg_by_channel": "",
    }


def extract_bridge_ramulator_stats(stdout: str) -> dict[str, str | int]:
    per_partition: dict[int, tuple[int, int, int]] = {}
    max_ticks = 0
    for match in BACKEND_RAMULATOR_STAT_RE.finditer(stdout):
        partition = int(match.group("partition"))
        ticks = int(match.group("ticks"))
        reads = int(match.group("reads"))
        completed_reads = int(match.group("completed_reads"))
        writes = int(match.group("writes"))
        max_ticks = max(max_ticks, ticks)
        per_partition[partition] = (reads, completed_reads, writes)

    if not per_partition:
        return empty_ramulator_stats()

    partition_count = max(per_partition) + 1
    reads_by_partition = [
        per_partition.get(partition, (0, 0, 0))[0]
        for partition in range(partition_count)
    ]
    writes_by_partition = [
        per_partition.get(partition, (0, 0, 0))[2]
        for partition in range(partition_count)
    ]

    stats = empty_ramulator_stats()
    stats.update(
        {
            "ramulator_stats_present": 1,
            "ramulator_stats_source": "bridge",
            "ramulator_memory_system_cycles": str(max_ticks),
            "ramulator_total_num_read_requests": str(sum(reads_by_partition)),
            "ramulator_total_num_write_requests": str(sum(writes_by_partition)),
            "ramulator_num_read_reqs": str(sum(reads_by_partition)),
            "ramulator_num_write_reqs": str(sum(writes_by_partition)),
            "ramulator_num_read_reqs_by_channel": format_int_list(reads_by_partition),
        }
    )
    return stats


def extract_ramulator_stats(stdout: str) -> dict[str, str | int]:
    raw_stats: dict[str, float | int] = {}
    for line in stdout.splitlines():
        match = RAMULATOR_YAML_STAT_RE.match(line)
        if not match:
            continue
        value = parse_ramulator_scalar(match.group(2))
        if value is not None:
            raw_stats[match.group(1)] = value

    channel_ids = sorted(
        {
            int(match.group(1))
            for key in raw_stats
            if (match := re.match(r"num_read_reqs_(\d+)$", key))
        }
    )
    if not channel_ids and "memory_system_cycles" not in raw_stats:
        return extract_bridge_ramulator_stats(stdout)

    def channel_values(base: str) -> list[float | int]:
        return [raw_stats.get(f"{base}_{channel}", 0) for channel in channel_ids]

    def sum_channel(base: str) -> float | int:
        values = channel_values(base)
        if any(isinstance(value, float) for value in values):
            return float(sum(float(value) for value in values))
        return int(sum(int(value) for value in values))

    def format_channel_values(base: str, default: float | int | None = 0) -> str:
        return ",".join(
            format_numeric(raw_stats.get(f"{base}_{channel}", default))
            for channel in channel_ids
        )

    num_read_reqs = sum_channel("num_read_reqs") if channel_ids else None
    read_latency = sum_channel("read_latency") if channel_ids else None
    avg_read_latency = ""
    if isinstance(num_read_reqs, (int, float)) and float(num_read_reqs) > 0:
        avg_read_latency = format_float(float(read_latency) / float(num_read_reqs))

    return {
        "ramulator_stats_present": 1,
        "ramulator_stats_source": "yaml",
        "ramulator_memory_system_cycles": format_numeric(raw_stats.get("memory_system_cycles")),
        "ramulator_total_num_read_requests": format_numeric(raw_stats.get("total_num_read_requests")),
        "ramulator_total_num_write_requests": format_numeric(raw_stats.get("total_num_write_requests")),
        "ramulator_num_read_reqs": format_numeric(num_read_reqs),
        "ramulator_num_write_reqs": format_numeric(sum_channel("num_write_reqs") if channel_ids else None),
        "ramulator_row_hits": format_numeric(sum_channel("row_hits") if channel_ids else None),
        "ramulator_row_misses": format_numeric(sum_channel("row_misses") if channel_ids else None),
        "ramulator_row_conflicts": format_numeric(sum_channel("row_conflicts") if channel_ids else None),
        "ramulator_read_row_hits": format_numeric(sum_channel("read_row_hits") if channel_ids else None),
        "ramulator_read_row_misses": format_numeric(sum_channel("read_row_misses") if channel_ids else None),
        "ramulator_read_row_conflicts": format_numeric(sum_channel("read_row_conflicts") if channel_ids else None),
        "ramulator_write_row_hits": format_numeric(sum_channel("write_row_hits") if channel_ids else None),
        "ramulator_write_row_misses": format_numeric(sum_channel("write_row_misses") if channel_ids else None),
        "ramulator_write_row_conflicts": format_numeric(sum_channel("write_row_conflicts") if channel_ids else None),
        "ramulator_read_latency": format_numeric(read_latency),
        "ramulator_avg_read_latency": avg_read_latency,
        "ramulator_queue_len_avg_sum": format_numeric(sum_channel("queue_len_avg") if channel_ids else None),
        "ramulator_read_queue_len_avg_sum": format_numeric(sum_channel("read_queue_len_avg") if channel_ids else None),
        "ramulator_write_queue_len_avg_sum": format_numeric(sum_channel("write_queue_len_avg") if channel_ids else None),
        "ramulator_priority_queue_len_avg_sum": format_numeric(sum_channel("priority_queue_len_avg") if channel_ids else None),
        "ramulator_num_read_reqs_by_channel": format_channel_values("num_read_reqs"),
        "ramulator_row_hits_by_channel": format_channel_values("row_hits"),
        "ramulator_row_misses_by_channel": format_channel_values("row_misses"),
        "ramulator_row_conflicts_by_channel": format_channel_values("row_conflicts"),
        "ramulator_avg_read_latency_by_channel": format_channel_values("avg_read_latency", None),
        "ramulator_queue_len_avg_by_channel": format_channel_values("queue_len_avg"),
        "ramulator_read_queue_len_avg_by_channel": format_channel_values("read_queue_len_avg"),
    }


def extract_backend_partition_stats(
    stdout: str, known_partitions: set[int]
) -> dict[str, str | int]:
    stats: dict[int, tuple[int, int, int, int, int, int, int]] = {}
    global_inflight_reads = ""
    inflight_limit = ""
    for match in BACKEND_PARTITION_STAT_RE.finditer(stdout):
        partition = int(match.group(1))
        accepted_reads = int(match.group(2))
        completed_reads = int(match.group(3))
        accepted_writes = int(match.group(4))
        rejected = int(match.group(5))
        rejected_inflight = int(match.group(6) or 0)
        rejected_ramulator = int(match.group(7) or 0)
        backend_full = int(match.group(8) or 0)
        if match.group(9) is not None:
            global_inflight_reads = match.group(9)
        if match.group(10) is not None:
            inflight_limit = match.group(10)
        stats[partition] = (
            accepted_reads,
            completed_reads,
            accepted_writes,
            rejected,
            rejected_inflight,
            rejected_ramulator,
            backend_full,
        )

    if not stats and not known_partitions:
        return {
            "backend_active_partitions": "",
            "backend_max_partition_share": "",
            "backend_partition_cv": "",
            "backend_total_accepted_reads": "",
            "backend_total_completed_reads": "",
            "backend_total_accepted_writes": "",
            "backend_total_rejected": "",
            "backend_total_rejected_inflight": "",
            "backend_total_rejected_ramulator": "",
            "backend_total_full_stalls": "",
            "backend_global_inflight_reads": "",
            "backend_inflight_limit": "",
            "backend_accepted_reads_by_partition": "",
            "backend_accepted_writes_by_partition": "",
            "backend_rejected_by_partition": "",
            "backend_rejected_inflight_by_partition": "",
            "backend_rejected_ramulator_by_partition": "",
            "backend_full_by_partition": "",
        }

    partition_count = max(set(stats) | known_partitions) + 1
    accepted_reads_by_partition = [
        stats.get(partition, (0, 0, 0, 0, 0, 0, 0))[0]
        for partition in range(partition_count)
    ]
    completed_reads_by_partition = [
        stats.get(partition, (0, 0, 0, 0, 0, 0, 0))[1]
        for partition in range(partition_count)
    ]
    accepted_writes_by_partition = [
        stats.get(partition, (0, 0, 0, 0, 0, 0, 0))[2]
        for partition in range(partition_count)
    ]
    rejected_by_partition = [
        stats.get(partition, (0, 0, 0, 0, 0, 0, 0))[3]
        for partition in range(partition_count)
    ]
    rejected_inflight_by_partition = [
        stats.get(partition, (0, 0, 0, 0, 0, 0, 0))[4]
        for partition in range(partition_count)
    ]
    rejected_ramulator_by_partition = [
        stats.get(partition, (0, 0, 0, 0, 0, 0, 0))[5]
        for partition in range(partition_count)
    ]
    backend_full_by_partition = [
        stats.get(partition, (0, 0, 0, 0, 0, 0, 0))[6]
        for partition in range(partition_count)
    ]
    accepted_by_partition = [
        reads + writes
        for reads, writes in zip(accepted_reads_by_partition, accepted_writes_by_partition)
    ]
    total_accepted = sum(accepted_by_partition)
    active_partitions = sum(1 for value in accepted_by_partition if value > 0)
    max_partition_share = (
        f"{max(accepted_by_partition) / total_accepted:.6f}"
        if total_accepted
        else ""
    )

    return {
        "backend_active_partitions": active_partitions,
        "backend_max_partition_share": max_partition_share,
        "backend_partition_cv": compute_cv(accepted_by_partition),
        "backend_total_accepted_reads": sum(accepted_reads_by_partition),
        "backend_total_completed_reads": sum(completed_reads_by_partition),
        "backend_total_accepted_writes": sum(accepted_writes_by_partition),
        "backend_total_rejected": sum(rejected_by_partition),
        "backend_total_rejected_inflight": sum(rejected_inflight_by_partition),
        "backend_total_rejected_ramulator": sum(rejected_ramulator_by_partition),
        "backend_total_full_stalls": sum(backend_full_by_partition),
        "backend_global_inflight_reads": global_inflight_reads,
        "backend_inflight_limit": inflight_limit,
        "backend_accepted_reads_by_partition": format_int_list(
            accepted_reads_by_partition
        ),
        "backend_accepted_writes_by_partition": format_int_list(
            accepted_writes_by_partition
        ),
        "backend_rejected_by_partition": format_int_list(rejected_by_partition),
        "backend_rejected_inflight_by_partition": format_int_list(
            rejected_inflight_by_partition
        ),
        "backend_rejected_ramulator_by_partition": format_int_list(
            rejected_ramulator_by_partition
        ),
        "backend_full_by_partition": format_int_list(backend_full_by_partition),
    }


def run_one(
    bench: Benchmark,
    latency: int,
    queue_limit: int,
    max_cycle: int,
    timeout_s: int,
    out_dir: Path,
    gpgpusim_config: Path,
    l2_cache_config: str,
    config_override_files: tuple[Path, ...],
    backend: str,
    config_variant: str,
    config_overrides: tuple[str, ...],
    gpgpusim_host_timing: str,
    ramulator_config: Path,
    ramulator_inflight_read_limit: int,
    ramulator_ticks_per_dram_cycle: str,
    ramulator_finalize_stats: str,
) -> dict[str, str | int | float]:
    run_dir = (out_dir / config_variant / bench.name / f"{backend}_lat{latency}_q{queue_limit}").resolve()
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    write_config(
        run_dir,
        gpgpusim_config,
        max_cycle,
        l2_cache_config,
        config_overrides,
        config_override_files,
        gpgpusim_host_timing,
    )
    core_freq_mhz, icnt_freq_mhz, l2_freq_mhz, dram_freq_mhz = extract_clock_domains(
        run_dir / "gpgpusim.config"
    )
    prepare_benchmark_inputs(bench, run_dir)

    cmd = benchmark_command(bench)
    run_ramulator_config = ""
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"

    backend_env = ""
    if backend == "fixed":
        backend_env = f"""
export SGRAM_BACKEND=fixed
export SGRAM_FIXED_LATENCY={latency}
export SGRAM_QUEUE_LIMIT={queue_limit}
""".strip()
    elif backend == "ramulator2":
        bridge_lib = INTEGRATION_ROOT / "build" / "ramulator2_bridge" / "libsgram_ramulator2_bridge.so"
        run_ramulator_config = str(prepare_ramulator_config(run_dir, ramulator_config))
        skip_finalize_stats = ramulator_finalize_stats == "off"
        finalize_stats_env = (
            "export SGRAM_RAMULATOR_SKIP_FINALIZE_STATS=1"
            if skip_finalize_stats
            else "unset SGRAM_RAMULATOR_SKIP_FINALIZE_STATS"
        )
        backend_env = f"""
export SGRAM_BACKEND=ramulator2
export SGRAM_QUEUE_LIMIT={queue_limit}
export SGRAM_RAMULATOR_LIB={quote(str(bridge_lib))}
export SGRAM_RAMULATOR_CONFIG={quote(run_ramulator_config)}
export SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT={ramulator_inflight_read_limit}
export SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE={quote(str(ramulator_ticks_per_dram_cycle))}
export SGRAM_ACCELSIM_DRAM_FREQ_MHZ={quote(str(dram_freq_mhz))}
{finalize_stats_env}
""".strip()

    run_cmd = shell_join(cmd)
    if timeout_s > 0:
        run_cmd = f"timeout --kill-after=5s {timeout_s}s {run_cmd}"

    bash = f"""
set -euo pipefail
source {quote(str(GPGPU_SETUP))}
export LD_LIBRARY_PATH={quote(str(GPGPU_BUILD))}:{quote(str(INTEGRATION_ROOT / "build" / "ramulator2_bridge"))}:{quote(str(RAMULATOR2_ROOT))}:${{LD_LIBRARY_PATH:-}}
{backend_env}
exec {run_cmd}
""".strip()

    start = time.time()
    with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as err:
        proc = subprocess.run(
            ["bash", "-lc", bash],
            cwd=run_dir,
            stdout=out,
            stderr=err,
            check=False,
        )
    elapsed = time.time() - start

    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    timed_out = proc.returncode in (124, 137)
    status = classify_status(proc.returncode, timed_out, stdout, stderr, backend != "native")

    enabled_partitions = set(int(x) for x in ENABLED_RE.findall(stdout))
    printed_partitions = set(int(x) for x in BACKEND_PRINT_RE.findall(stdout))
    backend_partition_stats = extract_backend_partition_stats(
        stdout, enabled_partitions | printed_partitions
    )
    ramulator_stats = extract_ramulator_stats(stdout)
    ramulator_clock_stats = extract_ramulator_clock_stats(stdout)
    host_timing_stats = extract_host_timing_stats(stdout)
    launches = len(LAUNCH_RE.findall(stdout))
    l2_accesses = extract_last_numeric(stdout, "L2_total_cache_accesses")
    l2_misses = extract_last_numeric(stdout, "L2_total_cache_misses")

    return {
        "benchmark": bench.name,
        "suite": bench.suite,
        "expected_class": bench.expected_class,
        "benchmark_workdir": bench.workdir,
        "main_reason": bench.main_reason,
        "config_variant": config_variant,
        "gpgpusim_config_source": str(gpgpusim_config),
        "gpgpusim_config_run": str(run_dir / "gpgpusim.config"),
        "config_override_files": ";".join(str(path) for path in config_override_files),
        "config_overrides": ";".join(config_overrides),
        "gpgpusim_host_timing": gpgpusim_host_timing,
        "accelsim_core_freq_mhz": core_freq_mhz,
        "accelsim_icnt_freq_mhz": icnt_freq_mhz,
        "accelsim_l2_freq_mhz": l2_freq_mhz,
        "accelsim_dram_freq_mhz": dram_freq_mhz,
        "backend": backend,
        "ramulator_config_source": str(ramulator_config) if backend == "ramulator2" else "",
        "ramulator_config_run": run_ramulator_config,
        "ramulator_inflight_read_limit": ramulator_inflight_read_limit if backend == "ramulator2" else "",
        "ramulator_ticks_per_dram_cycle": ramulator_ticks_per_dram_cycle if backend == "ramulator2" else "",
        "ramulator_finalize_stats": ramulator_finalize_stats if backend == "ramulator2" else "",
        **ramulator_clock_stats,
        "latency": latency,
        "queue_limit": queue_limit,
        "l2_cache_config": l2_cache_config,
        "status": status,
        "exit_code": proc.returncode,
        "seconds": round(elapsed, 3),
        "backend_enabled_partitions": len(enabled_partitions | printed_partitions),
        "backend_runtime_print_partitions": len(printed_partitions),
        **backend_partition_stats,
        **ramulator_stats,
        **host_timing_stats,
        "kernel_launches": launches,
        "max_cycle_hit": int("break due to reaching the maximum cycles" in stdout),
        "l2_accesses": l2_accesses,
        "l2_misses": l2_misses,
        "l2_miss_rate": compute_ratio(l2_misses, l2_accesses),
        "l2_pending_hits": extract_last_numeric(stdout, "L2_total_cache_pending_hits"),
        "l2_reservation_fails": extract_last_numeric(stdout, "L2_total_cache_reservation_fails"),
        "l2_bw_gbs": extract_last_numeric(stdout, "L2_BW"),
        "l2_bw_total_gbs": extract_last_numeric(stdout, "L2_BW_total"),
        "sim_cycles": extract_last_numeric(stdout, "gpu_sim_cycle"),
        "tot_sim_cycles": extract_last_numeric(stdout, "gpu_tot_sim_cycle"),
        "sim_insn": extract_last_numeric(stdout, "gpu_sim_insn"),
        "tot_sim_insn": extract_last_numeric(stdout, "gpu_tot_sim_insn"),
        "ipc": extract_last_numeric(stdout, "gpu_ipc"),
        "tot_ipc": extract_last_numeric(stdout, "gpu_tot_ipc"),
        "stall_dramfull": extract_last_numeric(stdout, "gpu_stall_dramfull"),
        "stall_icnt2sh": extract_last_numeric(stdout, "gpu_stall_icnt2sh"),
        "mem_read_global": extract_last_numeric(stdout, "gpgpu_n_mem_read_global"),
        "mem_write_global": extract_last_numeric(stdout, "gpgpu_n_mem_write_global"),
        "load_insn": extract_last_numeric(stdout, "gpgpu_n_load_insn"),
        "store_insn": extract_last_numeric(stdout, "gpgpu_n_store_insn"),
        "stall_shd_mem": extract_last_numeric(stdout, "gpgpu_n_stall_shd_mem"),
        "l1cache_bkconflict": extract_last_numeric(stdout, "gpgpu_n_l1cache_bkconflict"),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "command": shell_join(cmd),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--latencies",
        default="1,10,50,190",
        help="Comma-separated fixed latency cycle values.",
    )
    parser.add_argument(
        "--queue-limits",
        default="32",
        help="Comma-separated SGRAM_QUEUE_LIMIT values.",
    )
    parser.add_argument(
        "--backend",
        choices=("fixed", "native", "ramulator2"),
        default="fixed",
        help="Use the SG-Ramulator fixed backend or the native Accel-Sim DRAM path.",
    )
    parser.add_argument(
        "--config-variant",
        choices=sorted(CONFIG_VARIANTS),
        default="a100_full",
        help="Accel-Sim geometry override preset.",
    )
    parser.add_argument(
        "--config-overrides",
        default="",
        help="Extra semicolon-separated gpgpusim.config override lines applied after the variant.",
    )
    parser.add_argument(
        "--gpgpusim-config",
        type=Path,
        default=GPGPU_CONFIG,
        help=(
            "Base AccelSim/GPGPU-Sim config to copy into each run directory. "
            "Relative paths are resolved from the current directory, the integration root, then the workspace root."
        ),
    )
    parser.add_argument(
        "--accelsim-config-override-file",
        type=Path,
        action="append",
        default=[],
        help=(
            "Apply an AccelSim/GPGPU-Sim config fragment after --config-variant "
            "and --config-overrides. May be specified multiple times."
        ),
    )
    parser.add_argument("--max-cycle", type=int, default=50_000)
    parser.add_argument("--timeout", type=int, default=120, help="Per-run wall-clock timeout in seconds. Use 0 to disable.")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 1, 32))
    parser.add_argument(
        "--ramulator-inflight-read-limit",
        default="auto",
        help=(
            "SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT for --backend ramulator2. "
            "Use 'auto' to set the bridge-wide read cap near Ramulator2's "
            "Generic controller read-side buffering: channels * 32 read-buffer "
            "entries * 2 read-side buffers. Use 0 to disable the guard."
        ),
    )
    parser.add_argument(
        "--ramulator-ticks-per-dram-cycle",
        default="auto",
        help=(
            "SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE for --backend ramulator2. "
            "Use 'auto' to derive Ramulator ticks per AccelSim DRAM tick from "
            "-gpgpu_clock_domains and Ramulator tCK."
        ),
    )
    parser.add_argument(
        "--gpgpusim-host-timing",
        choices=("on", "off"),
        default="on",
        help="Apply -gpgpu_host_timing to collect GPGPU-Sim stage wall-time metrics.",
    )
    parser.add_argument(
        "--ramulator-finalize-stats",
        choices=("auto", "on", "off"),
        default="auto",
        help=(
            "Control Ramulator2 finalize stats. auto enables internal stats and "
            "falls back to bridge counters if the process exits before finalization."
        ),
    )
    parser.add_argument(
        "--ramulator-config",
        type=Path,
        default=DEFAULT_RAMULATOR_CONFIG,
        help=(
            "Ramulator2 YAML for --backend ramulator2. The file is copied into "
            "each run directory as ramulator2.yaml before being passed to the bridge."
        ),
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit benchmark count for smoke tests.")
    parser.add_argument(
        "--preset",
        choices=sorted(BENCHMARK_PRESETS),
        default="accelsim_ramulator_main",
        help="Built-in benchmark preset.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Load benchmarks from a TSV manifest instead of --preset.",
    )
    parser.add_argument(
        "--benchmarks",
        default="",
        help="Comma-separated benchmark names to run. Defaults to the built-in matrix.",
    )
    parser.add_argument(
        "--list-benchmarks",
        action="store_true",
        help="List selected benchmarks and exit without running Accel-Sim.",
    )
    parser.add_argument(
        "--a100-l2-8mb",
        action="store_true",
        help=f"Override A100 L2 to about 8 MiB using {A100_L2_8MB_CONFIG}.",
    )
    parser.add_argument(
        "--l2-cache-config",
        default="",
        help="Explicit -gpgpu_cache:dl2 override. Takes precedence over --a100-l2-8mb.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=INTEGRATION_ROOT / "results" / "fixed_backend_matrix",
    )
    args = parser.parse_args()

    gpgpusim_config = resolve_input_path(args.gpgpusim_config)
    ramulator_config = resolve_input_path(args.ramulator_config)
    config_override_files = tuple(resolve_input_path(path) for path in args.accelsim_config_override_file)
    l2_cache_config = args.l2_cache_config or (A100_L2_8MB_CONFIG if args.a100_l2_8mb else "")
    config_overrides = CONFIG_VARIANTS[args.config_variant]
    if args.config_overrides:
        config_overrides += tuple(
            item.strip() for item in args.config_overrides.split(";") if item.strip()
        )

    benches = load_manifest_benchmarks(args.manifest) if args.manifest else BENCHMARK_PRESETS[args.preset]
    if args.benchmarks:
        requested = {item.strip() for item in args.benchmarks.split(",") if item.strip()}
        benches = tuple(bench for bench in benches if bench.name in requested)
        missing_names = requested - {bench.name for bench in benches}
        if missing_names:
            print("unknown benchmark(s): " + ",".join(sorted(missing_names)), file=sys.stderr)
            return 2
    if args.limit:
        benches = benches[: args.limit]
    if not benches:
        source = str(args.manifest) if args.manifest else args.preset
        print(f"no benchmarks selected from {source}", file=sys.stderr)
        return 2
    if args.list_benchmarks:
        writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
        writer.writerow(["name", "suite", "expected_class", "workdir", "command", "main_reason"])
        for bench in benches:
            writer.writerow(
                [
                    bench.name,
                    bench.suite,
                    bench.expected_class,
                    bench.workdir,
                    shell_join(list(bench.command)),
                    bench.main_reason,
                ]
            )
        return 0
    missing = [path for path in (GPGPU_SETUP, GPGPU_BUILD / "libcudart.so", gpgpusim_config) if not path.exists()]
    if args.backend == "ramulator2" and not ramulator_config.exists():
        missing.append(ramulator_config)
    missing.extend(path for path in config_override_files if not path.exists())
    if missing:
        for path in missing:
            print(f"missing required file: {path}", file=sys.stderr)
        return 2
    try:
        ramulator_inflight_read_limit = (
            resolve_ramulator_inflight_read_limit(
                args.ramulator_inflight_read_limit, ramulator_config
            )
            if args.backend == "ramulator2"
            else 0
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    (GPGPU_BUILD / "libcudart.so.12").symlink_to("libcudart.so") if not (
        GPGPU_BUILD / "libcudart.so.12"
    ).exists() else None
    latencies = parse_csv_ints(args.latencies)
    queue_limits = parse_csv_ints(args.queue_limits)
    out_dir = args.out_dir if args.out_dir.is_absolute() else (Path.cwd() / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        (bench, latency, queue_limit)
        for bench in benches
        for latency in latencies
        for queue_limit in queue_limits
    ]
    print(
        f"running {len(tasks)} jobs: benchmarks={len(benches)} "
        f"latencies={latencies} queue_limits={queue_limits} jobs={args.jobs} "
        f"backend={args.backend} config_variant={args.config_variant} "
        f"gpgpusim_config={gpgpusim_config} "
        f"workspace_root={WORKSPACE_ROOT} "
        f"gpu_benchmark_root={GPU_BENCHMARK_ROOT} "
        f"l2_cache_config={l2_cache_config or 'base-config'} "
        f"gpgpusim_host_timing={args.gpgpusim_host_timing} "
        f"config_override_files={';'.join(str(path) for path in config_override_files) or 'none'} "
        f"config_overrides={';'.join(config_overrides) or 'none'} "
        f"ramulator_config={ramulator_config if args.backend == 'ramulator2' else 'n/a'} "
        f"ramulator_inflight_read_limit={ramulator_inflight_read_limit} "
        f"ramulator_ticks_per_dram_cycle={args.ramulator_ticks_per_dram_cycle} "
        f"ramulator_finalize_stats={args.ramulator_finalize_stats}"
        ,
        flush=True,
    )

    rows: list[dict[str, str | int | float]] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [
            pool.submit(
                run_one,
                bench,
                latency,
                queue_limit,
                args.max_cycle,
                args.timeout,
                out_dir,
                gpgpusim_config,
                l2_cache_config,
                config_override_files,
                args.backend,
                args.config_variant,
                config_overrides,
                args.gpgpusim_host_timing,
                ramulator_config,
                ramulator_inflight_read_limit,
                args.ramulator_ticks_per_dram_cycle,
                args.ramulator_finalize_stats,
            )
            for bench, latency, queue_limit in tasks
        ]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(
                f"[{len(rows):03d}/{len(tasks):03d}] {row['benchmark']} "
                f"{row['backend']} lat={row['latency']} q={row['queue_limit']} "
                f"{row['status']} enabled={row['backend_enabled_partitions']} "
                f"launches={row['kernel_launches']} {row['seconds']}s"
                ,
                flush=True,
            )

    rows.sort(key=lambda r: (str(r["benchmark"]), int(r["latency"]), int(r["queue_limit"])))
    summary = out_dir / "summary.csv"
    fields = [
        "benchmark",
        "suite",
        "expected_class",
        "benchmark_workdir",
        "main_reason",
        "config_variant",
        "gpgpusim_config_source",
        "gpgpusim_config_run",
        "config_override_files",
        "config_overrides",
        "gpgpusim_host_timing",
        "accelsim_core_freq_mhz",
        "accelsim_icnt_freq_mhz",
        "accelsim_l2_freq_mhz",
        "accelsim_dram_freq_mhz",
        "backend",
        "ramulator_config_source",
        "ramulator_config_run",
        "ramulator_inflight_read_limit",
        "ramulator_ticks_per_dram_cycle",
        "ramulator_effective_ticks_per_dram_cycle",
        "ramulator_tick_source",
        "ramulator_tck_ns",
        "ramulator_mhz",
        "ramulator_finalize_stats",
        "latency",
        "queue_limit",
        "l2_cache_config",
        "status",
        "exit_code",
        "seconds",
        "backend_enabled_partitions",
        "backend_runtime_print_partitions",
        "backend_active_partitions",
        "backend_max_partition_share",
        "backend_partition_cv",
        "backend_total_accepted_reads",
        "backend_total_completed_reads",
        "backend_total_accepted_writes",
        "backend_total_rejected",
        "backend_total_rejected_inflight",
        "backend_total_rejected_ramulator",
        "backend_total_full_stalls",
        "backend_global_inflight_reads",
        "backend_inflight_limit",
        "backend_accepted_reads_by_partition",
        "backend_accepted_writes_by_partition",
        "backend_rejected_by_partition",
        "backend_rejected_inflight_by_partition",
        "backend_rejected_ramulator_by_partition",
        "backend_full_by_partition",
        "ramulator_stats_present",
        "ramulator_stats_source",
        "ramulator_memory_system_cycles",
        "ramulator_total_num_read_requests",
        "ramulator_total_num_write_requests",
        "ramulator_num_read_reqs",
        "ramulator_num_write_reqs",
        "ramulator_row_hits",
        "ramulator_row_misses",
        "ramulator_row_conflicts",
        "ramulator_read_row_hits",
        "ramulator_read_row_misses",
        "ramulator_read_row_conflicts",
        "ramulator_write_row_hits",
        "ramulator_write_row_misses",
        "ramulator_write_row_conflicts",
        "ramulator_read_latency",
        "ramulator_avg_read_latency",
        "ramulator_queue_len_avg_sum",
        "ramulator_read_queue_len_avg_sum",
        "ramulator_write_queue_len_avg_sum",
        "ramulator_priority_queue_len_avg_sum",
        "ramulator_num_read_reqs_by_channel",
        "ramulator_row_hits_by_channel",
        "ramulator_row_misses_by_channel",
        "ramulator_row_conflicts_by_channel",
        "ramulator_avg_read_latency_by_channel",
        "ramulator_queue_len_avg_by_channel",
        "ramulator_read_queue_len_avg_by_channel",
        "kernel_launches",
        "max_cycle_hit",
        "l2_accesses",
        "l2_misses",
        "l2_miss_rate",
        "l2_pending_hits",
        "l2_reservation_fails",
        "l2_bw_gbs",
        "l2_bw_total_gbs",
        "sim_cycles",
        "tot_sim_cycles",
        "sim_insn",
        "tot_sim_insn",
        "ipc",
        "tot_ipc",
        "stall_dramfull",
        "stall_icnt2sh",
        "mem_read_global",
        "mem_write_global",
        "load_insn",
        "store_insn",
        "stall_shd_mem",
        "l1cache_bkconflict",
        "gpgpusim_host_timing_enabled",
        *(
            f"gpgpusim_host_timing_{stage}_{suffix}"
            for stage in HOST_TIMING_STAGES
            for suffix in ("us", "calls", "pct")
        ),
        "stdout",
        "stderr",
        "command",
    ]
    with summary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[str(row["status"])] = status_counts.get(str(row["status"]), 0) + 1
    print(f"summary={summary}", flush=True)
    print("status_counts=" + ",".join(f"{k}:{v}" for k, v in sorted(status_counts.items())), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

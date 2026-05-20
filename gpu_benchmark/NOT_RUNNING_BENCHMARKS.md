# Current Non-Running Benchmark Audit

Checked on RTX 3090 with CUDA 12.3 after the Pannotia and Parboil SGEMM fixes.

Primary logs:

- `traces/run_logs/recheck_not_running/`
- `traces/run_logs/pannotia_smoke/summary.tsv`
- `traces/run_logs/recheck_not_running/build_parboil_after_fixes.log`

## Recovered

- Pannotia: all 10 binaries run with data.
  - `bc`, `color_max`, `color_maxmin`, `fw`, `fw_block`, `mis`,
    `pagerank`, `pagerank_spmv`, `sssp`, `sssp_ell`
- PolyBench:
  - `polybench-2mm` passes with a 300s timeout, 112 seconds observed.
  - `polybench-gramschmidt` passes with a 300s timeout, 95 seconds observed.
- Parboil:
  - `parboil-sgemm` now passes after adding missing `return true` in the
    SGEMM matrix reader.
  - `parboil-lbm` runs when invoked directly with `-i` and `-o`; the Parboil
    Python output checker is Python 2 syntax and fails under Python 3.
- LonestarGPU:
  - `lonestar-dmr` passes on the `25k` input with `maxfactor=12`.
  - `lonestar-pta` passes for `pine` with `_constraints_after_hcd` and
    verification disabled.

## Still Not Running

- Parboil `bfs`, `sad`, `spmv`
  - Build fails under CUDA 12 because they use the removed legacy texture API:
    `texture<>`, `tex1Dfetch`, `tex2D`, `cudaBindTexture*`,
    `cudaUnbindTexture`.
  - Next fix would be a CUDA 12 texture-object port or replacing those reads
    with direct global-memory loads.

- LonestarGPU `lonestar-bh`
  - `lonestar-bh 100 1 0` times out at 120 seconds, so it is not just an input
    size issue.
  - It likely needs a CUDA 12/SM86 compatibility pass.

- LonestarGPU `lonestar-pta` with verification enabled
  - Small `ex` input solves, but exits 255 during verification because output
    differs from the provided reference.
  - Larger `vim` with verification hits an illegal memory access in the HCD
    rule.
  - Trace-only runs can use `verify=0`.

- Parboil `sgemm` `cuda_k1` variant
  - Times out at 120 seconds after the matrix-reader fix.
  - Main `cuda` and `cuda_base` variants pass.

- GraphBIG GraphColoring extra variants
  - Only `gc_topo_thread_centric` is built and runnable.
  - `gc_data_thread_centric`, `gc_data_warp_centric`, and
    `gc_topo_warp_centric` are not currently produced as executables.
  - The warp-centric sources still use deprecated `__all()` and need
    `__all_sync()`.

## False Positives In Older Logs

- ISPASS BFS/NN failures in `available_benchmarks` were no-arg/data issues;
  data-backed ISPASS smoke passes all 7.
- Parboil LBM failure in `data_backed_benchmarks` was caused by running with
  `-C`, which suppresses output while the code still writes an output file.
- Parboil SGEMM illegal-instruction failure was the missing return in
  `readColMajorMatrixFile()`, now fixed.

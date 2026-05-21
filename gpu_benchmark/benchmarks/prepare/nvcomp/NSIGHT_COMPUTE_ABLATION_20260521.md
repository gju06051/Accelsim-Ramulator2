# nvCOMP Nsight Compute Ablation, 2026-05-21

## Setup

- Host workspace: `/home/gju06051/Accelsim-Ramulator`
- GPU: NVIDIA GeForce RTX 3090, SM 8.6, 24 GiB memory, 6 MiB L2
- nvCOMP library: Python wheel under `/home/gju06051/.local/lib/python3.11/site-packages/nvidia/libnvcomp`
- Benchmark: `gpu_benchmark/benchmarks/prepare/bin/nvcomp_codec_bench`
- Input generator: in-device deterministic compressible byte pattern
- Fixed chunk size: 64 KiB
- Iterations: 1 compression + 1 decompression per run
- Nsight Compute: 2024.3.0 from `/home/gju06051/workspace/etc/target/linux-desktop-glibc_2_11_3-x64/ncu`

The CUDA 12.3 `ncu` in `/usr/local/cuda-12.3/bin/ncu` failed on this host with
`cuStreamGetCtx_v2` injection symbol mismatch against the current 580-series
driver, so the newer 2024.3.0 deployment was used.

Nsight Compute was run with `--cache-control none`. The summary excludes the
benchmark's input-fill and mismatch-check kernels, so the reported metrics are
for nvCOMP library kernels only.

## Metrics

- `native GiB/s`: benchmark's native non-NCU elapsed time.
- `dram/input`: `(dram__bytes_read.sum + dram__bytes_write.sum) / input_bytes`.
- `L1 hit`: `l1tex__t_sectors_lookup_hit.sum / (hit + miss)`.
- `L2 hit`: `lts__t_sectors_lookup_hit.sum / (hit + miss)`.
- `IPC`: `sm__inst_executed.sum / sm__cycles_active.sum`, i.e. warp instructions per active SM cycle.

Raw files and generated summaries are in:

- `results/nvcomp_ncu_20260521/summary.csv`
- `results/nvcomp_ncu_20260521/summary.md`
- `results/nvcomp_ncu_20260521/*.ncu.csv`
- `results/nvcomp_ncu_20260521/*.native.log`

## Summary

| codec | input | ratio | native GiB/s | dram/input | L1 hit | L2 hit | IPC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| lz4 | 1 GiB | 0.2421 | 22.18 | 14.88x | 78.8% | 73.9% | 1.366 |
| lz4 | 2 GiB | 0.2421 | 24.67 | 14.89x | 78.7% | 73.9% | 1.387 |
| lz4 | 4 GiB | 0.2421 | 25.81 | 14.90x | 78.7% | 73.9% | 1.389 |
| snappy | 1 GiB | 0.2544 | 22.05 | 6.78x | 77.0% | 50.7% | 1.746 |
| snappy | 2 GiB | 0.2544 | 23.99 | 6.81x | 77.0% | 50.3% | 1.752 |
| snappy | 4 GiB | 0.2544 | 24.89 | 6.83x | 77.0% | 50.1% | 1.759 |
| gdeflate | 1 GiB | 0.2104 | 14.89 | 17.53x | 67.6% | 74.4% | 1.129 |
| gdeflate | 2 GiB | 0.2104 | 16.25 | 17.54x | 67.5% | 74.3% | 1.142 |
| deflate | 1 GiB | 0.2076 | 12.29 | 19.27x | 72.7% | 75.1% | 1.327 |
| zstd | 1 GiB | 0.1666 | 11.81 | 26.54x | 57.9% | 70.4% | 1.609 |
| cascaded | 1 GiB | 0.2911 | 64.30 | 3.17x | 12.0% | 51.9% | 2.108 |
| cascaded | 2 GiB | 0.2911 | 84.03 | 3.17x | 12.0% | 51.9% | 2.117 |
| cascaded | 4 GiB | 0.2911 | 122.20 | 3.17x | 11.9% | 51.9% | 2.121 |
| bitcomp | 1 GiB | 0.5004 | 55.94 | 4.14x | 12.7% | 53.6% | 2.269 |
| bitcomp | 2 GiB | 0.5004 | 87.70 | 4.14x | 12.7% | 53.5% | 2.275 |
| bitcomp | 4 GiB | 0.5004 | 117.51 | 4.15x | 12.6% | 53.5% | 2.278 |
| ans | 1 GiB | 0.9995 | 55.47 | 9.00x | 39.5% | 56.3% | 1.937 |
| ans | 2 GiB | 0.9995 | 70.42 | 8.93x | 39.5% | 56.2% | 1.941 |

## Observations

1. The measured metrics are stable as input grows beyond L2.
   LZ4, Snappy, Cascaded, Bitcomp, and ANS show nearly unchanged compression
   ratio, L1 hit rate, L2 hit rate, IPC, and DRAM traffic per input byte from
   1 GiB to their largest successful point. This suggests that the large-data
   nvCOMP behavior is not qualitatively different from the large end of the
   local benchmark once the total input is well beyond L2.

2. The 64 KiB chunk size does not mean the whole workload is L2-resident.
   A 1 GiB input is about 171x the RTX 3090 L2, and 4 GiB is about 683x L2.
   LZ4 and GDeflate still move about 15-18x input bytes through DRAM, while
   Zstd moves about 27x input bytes for the 1 GiB point.

3. Codec classes split into different locality/traffic regimes.
   LZ4/GDeflate/Deflate/Zstd have higher DRAM traffic per input byte and
   relatively high L2 hit rates, while Cascaded/Bitcomp have much lower
   DRAM/input but low L1 hit rates and higher IPC. Snappy sits between these
   groups, with high L1 hit rate but only about 50% L2 hit rate.

4. The current 64 MiB manifest input is already larger than this GPU's L2, but
   the 1-4 GiB sweep is a better calibration point for nvCOMP's intended use.
   The large-input sweep supports using nvCOMP as a streaming/mixed-locality
   benchmark, but any 16 KiB or 64 KiB total-input trace would be too small to
   represent production nvCOMP traffic.

## Limits and Follow-up

- GDeflate 4 GiB and ANS 4 GiB failed on the 24 GiB RTX 3090 due to device OOM.
  ANS failed while allocating the decompressed output after allocating the input
  and compressed workspace; GDeflate failed inside nvCOMP runtime allocation.
- Deflate and Zstd were profiled at 1 GiB only because the heavier codecs already
  showed high NCU replay cost and the main size-scaling question was answered by
  LZ4, Snappy, GDeflate, Cascaded, Bitcomp, and ANS.
- For simulation trace generation, prefer at least 1 GiB total input when trace
  size is manageable. If simulator runtime forces tiny traces, label them as
  chunk-level micro-traces and do not use their cache-locality ratios as direct
  evidence for full nvCOMP workloads.

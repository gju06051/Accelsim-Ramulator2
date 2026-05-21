# nvCOMP Compression-Phase Nsight Compute Summary, 2026-05-21

This summary uses the simulation trace kernel ranges, not the full benchmark
kernel sequence. The trace kernel numbers are 1-based. Nsight Compute's CSV
`ID` column is 0-based, so trace kernel 3 maps to NCU `ID=2`.

## Selected Trace Ranges

| codec | trace kernels | NCU IDs | selected phase |
| --- | ---: | ---: | --- |
| lz4 | 3 | 2 | `lz4CompressBatchKernel` |
| snappy | 3 | 2 | `snap_kernel` |
| cascaded | 3 | 2 | `composite_compression_kernel` |
| bitcomp | 3 | 2 | `batch_encoder_kernel` |
| gdeflate | 3-5 | 2-4 | temp pointer setup, LZ compression, GDeflate encode |
| deflate | 3-7 | 2-6 | output sizing, zero output, temp pointer setup, LZ compression, Deflate encode |
| zstd | 3-8 | 2-7 | buffer init, frame setup, LZ, literal, sequence, frame compaction |
| ans | 3-7 | 2-6 | histogram, normalization, table construction, compression, chunk coalescing |

The excluded kernels are synthetic input fill, generic nvCOMP front/back setup,
decompression, status reductions outside the selected range, and mismatch check.

## Aggregate Metrics

| codec | input | trace | time ms | DRAM/input | read/input | write/input | L1 hit | L2 hit | IPC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| lz4 | 1 GiB | 3 | 62.146 | 12.04x | 7.22x | 4.82x | 72.8% | 52.6% | 1.155 |
| lz4 | 2 GiB | 3 | 121.936 | 12.05x | 7.23x | 4.82x | 72.8% | 52.6% | 1.170 |
| lz4 | 4 GiB | 3 | 242.608 | 12.05x | 7.23x | 4.82x | 72.8% | 52.6% | 1.170 |
| snappy | 1 GiB | 3 | 62.882 | 4.77x | 4.52x | 0.26x | 78.9% | 47.4% | 1.094 |
| snappy | 2 GiB | 3 | 124.576 | 4.80x | 4.54x | 0.26x | 78.9% | 47.0% | 1.093 |
| snappy | 4 GiB | 3 | 248.047 | 4.82x | 4.56x | 0.26x | 78.9% | 46.8% | 1.095 |
| gdeflate | 1 GiB | 3-5 | 86.995 | 14.41x | 8.61x | 5.80x | 69.8% | 52.9% | 0.963 |
| gdeflate | 2 GiB | 3-5 | 171.170 | 14.42x | 8.62x | 5.80x | 69.8% | 52.8% | 0.974 |
| deflate | 1 GiB | 3-7 | 95.410 | 16.87x | 8.82x | 8.06x | 59.1% | 61.0% | 0.908 |
| zstd | 1 GiB | 3-8 | 121.035 | 22.72x | 13.06x | 9.67x | 45.9% | 62.8% | 1.614 |
| cascaded | 1 GiB | 3 | 8.381 | 1.29x | 1.00x | 0.29x | 13.4% | 27.7% | 2.205 |
| cascaded | 2 GiB | 3 | 16.682 | 1.29x | 1.00x | 0.29x | 13.4% | 27.7% | 2.213 |
| cascaded | 4 GiB | 3 | 33.293 | 1.29x | 1.00x | 0.29x | 13.4% | 27.7% | 2.216 |
| bitcomp | 1 GiB | 3 | 3.078 | 1.50x | 1.00x | 0.50x | 15.9% | 37.1% | 2.596 |
| bitcomp | 2 GiB | 3 | 6.130 | 1.50x | 1.00x | 0.50x | 15.9% | 37.1% | 2.604 |
| bitcomp | 4 GiB | 3 | 12.232 | 1.50x | 1.00x | 0.50x | 15.9% | 37.1% | 2.607 |
| ans | 1 GiB | 3-7 | 8.048 | 4.84x | 2.90x | 1.94x | 38.8% | 52.3% | 1.764 |
| ans | 2 GiB | 3-7 | 15.902 | 4.77x | 2.90x | 1.87x | 38.7% | 52.3% | 1.781 |

## Takeaways

1. Compression-only metrics are stable with input size for the codecs measured
   at multiple sizes. This holds for LZ4, Snappy, Cascaded, Bitcomp, ANS, and
   GDeflate up to the largest successful point.

2. Compression-only L2 behavior is lower than the earlier full-nvCOMP summary
   for several codecs because the full summary included setup, compaction,
   decompression, and status kernels. For simulation comparison, use this file.

3. The compression kernels still generate substantial traffic relative to input:
   LZ4 about 12.05x, GDeflate about 14.4x, Deflate about 16.9x, and Zstd about
   22.7x. Cascaded and Bitcomp are much lighter at about 1.3-1.5x.

Raw outputs:

- `results/nvcomp_ncu_20260521/compression_phase_summary.csv`
- `results/nvcomp_ncu_20260521/compression_phase_summary.md`
- `results/nvcomp_ncu_20260521/compression_phase_per_kernel.csv`

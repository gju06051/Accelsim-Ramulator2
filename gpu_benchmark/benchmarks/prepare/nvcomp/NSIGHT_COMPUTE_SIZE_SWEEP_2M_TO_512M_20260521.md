# nvCOMP Compression-Phase Size Sweep, 2 MiB to 512 MiB

This sweep repeats the Nsight Compute compression-phase analysis for input sizes
from 2 MiB through 512 MiB, doubling each step. The selected kernels match the
simulation trace ranges:

- LZ4, Snappy, Cascaded, Bitcomp: trace kernel 3
- GDeflate: trace kernels 3-5
- Deflate: trace kernels 3-7
- Zstd: trace kernels 3-8
- ANS: trace kernels 3-7

Trace kernel numbers are 1-based. Nsight Compute CSV `ID` values are 0-based.
The RTX 3090 used here has a 6 MiB L2, so 2 MiB and 4 MiB are below L2, while
8 MiB is just above it.

Raw and generated outputs:

- `results/nvcomp_ncu_2m_to_512m_20260521/compression_phase_summary.csv`
- `results/nvcomp_ncu_2m_to_512m_20260521/compression_phase_summary.md`
- `results/nvcomp_ncu_2m_to_512m_20260521/compression_phase_per_kernel.csv`
- `results/nvcomp_ncu_2m_to_512m_20260521/*.ncu.csv`
- `results/nvcomp_ncu_2m_to_512m_20260521/*.native.log`

## Selected Points

| codec | input | DRAM/input | L1 hit | L2 hit | IPC |
| --- | ---: | ---: | ---: | ---: | ---: |
| lz4 | 2 MiB | 1.48x | 95.3% | 89.2% | 0.115 |
| lz4 | 8 MiB | 5.47x | 90.2% | 80.2% | 0.167 |
| lz4 | 32 MiB | 11.39x | 76.0% | 54.5% | 0.553 |
| lz4 | 64 MiB | 11.95x | 73.6% | 52.9% | 0.993 |
| lz4 | 512 MiB | 12.01x | 72.9% | 52.7% | 1.128 |
| snappy | 2 MiB | 1.55x | 90.3% | 81.9% | 0.133 |
| snappy | 8 MiB | 1.54x | 87.5% | 83.7% | 0.206 |
| snappy | 32 MiB | 4.16x | 81.7% | 51.2% | 0.728 |
| snappy | 64 MiB | 4.21x | 79.5% | 53.5% | 0.930 |
| snappy | 512 MiB | 4.75x | 78.9% | 47.8% | 1.093 |
| gdeflate | 2 MiB | 3.32x | 90.2% | 85.8% | 0.107 |
| gdeflate | 8 MiB | 7.87x | 86.0% | 76.7% | 0.154 |
| gdeflate | 32 MiB | 13.69x | 73.5% | 54.6% | 0.527 |
| gdeflate | 64 MiB | 14.26x | 71.0% | 53.1% | 0.836 |
| gdeflate | 512 MiB | 14.38x | 69.9% | 53.0% | 0.946 |
| deflate | 2 MiB | 4.72x | 77.7% | 89.4% | 0.106 |
| deflate | 8 MiB | 10.17x | 73.9% | 81.3% | 0.152 |
| deflate | 32 MiB | 16.12x | 62.8% | 62.6% | 0.514 |
| deflate | 64 MiB | 16.72x | 60.6% | 61.2% | 0.799 |
| deflate | 512 MiB | 16.96x | 59.3% | 61.0% | 0.893 |
| zstd | 2 MiB | 35.64x | 57.1% | 95.7% | 0.404 |
| zstd | 8 MiB | 24.07x | 51.4% | 78.3% | 0.436 |
| zstd | 32 MiB | 21.01x | 48.3% | 71.7% | 0.834 |
| zstd | 64 MiB | 21.45x | 47.2% | 68.1% | 1.417 |
| zstd | 512 MiB | 22.70x | 45.9% | 63.0% | 1.548 |
| cascaded | 2 MiB | 1.47x | 16.1% | 32.5% | 0.465 |
| cascaded | 8 MiB | 1.41x | 15.7% | 28.3% | 0.708 |
| cascaded | 32 MiB | 1.32x | 13.6% | 28.1% | 1.868 |
| cascaded | 64 MiB | 1.31x | 13.6% | 27.9% | 1.920 |
| cascaded | 512 MiB | 1.29x | 13.5% | 27.8% | 2.190 |
| bitcomp | 2 MiB | 1.54x | 18.0% | 37.0% | 1.231 |
| bitcomp | 8 MiB | 1.50x | 16.5% | 36.3% | 1.613 |
| bitcomp | 32 MiB | 1.50x | 15.9% | 36.9% | 2.296 |
| bitcomp | 64 MiB | 1.50x | 15.8% | 37.1% | 2.434 |
| bitcomp | 512 MiB | 1.50x | 15.8% | 37.1% | 2.583 |
| ans | 2 MiB | 4.80x | 43.0% | 63.6% | 0.691 |
| ans | 8 MiB | 5.41x | 41.7% | 56.6% | 1.017 |
| ans | 32 MiB | 5.03x | 40.7% | 53.0% | 1.472 |
| ans | 64 MiB | 4.77x | 39.3% | 52.4% | 1.675 |
| ans | 512 MiB | 4.77x | 38.8% | 52.3% | 1.766 |

## Interpretation

1. For LZ4, Snappy, GDeflate, and Deflate, sub-L2 inputs clearly overstate cache
   locality and understate DRAM traffic. Their L2 hit rates are around 82-89% at
   2-4 MiB, then settle near the large-input behavior after roughly 32-64 MiB.

2. For these byte/Deflate-family codecs, 64 MiB is already a much better
   simulation point than 2-8 MiB. LZ4 and GDeflate are very close to their
   512 MiB DRAM/input and L2-hit behavior by 64 MiB.

3. Zstd has a different small-input artifact: DRAM/input is highest at 2 MiB
   because fixed compression-phase work dominates, while L2 hit is also very
   high. It stabilizes more gradually and is closer to large-input behavior by
   128-256 MiB.

4. Cascaded and Bitcomp are relatively stable in DRAM/input even at 2 MiB, but
   their IPC still grows strongly with input size. For throughput/occupancy
   comparison, use at least 32-64 MiB.

5. ANS stabilizes around 32-64 MiB. Its compression ratio is also odd below
   64 MiB in native logs, where compressed output can exceed input size.

For simulation comparison against realistic nvCOMP compression behavior, avoid
2-8 MiB traces for LZ4/Snappy/GDeflate/Deflate/Zstd unless the goal is explicitly
to model a small-chunk microcase. A practical minimum is 64 MiB, with 128 MiB+
preferred for Zstd and for IPC-sensitive comparisons.

#include <cuda_runtime.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#define CHECK_CUDA(call)                                                      \
  do {                                                                        \
    cudaError_t err__ = (call);                                                \
    if (err__ != cudaSuccess) {                                                \
      std::fprintf(stderr, "CUDA error %s:%d: %s\n", __FILE__, __LINE__,      \
                   cudaGetErrorString(err__));                                \
      std::exit(1);                                                            \
    }                                                                         \
  } while (0)

static int parse_int_arg(int argc, char** argv, const char* name, int value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], name) == 0) {
      return std::atoi(argv[i + 1]);
    }
  }
  return value;
}

static bool is_power_of_two(int value) {
  return value > 1 && (value & (value - 1)) == 0;
}

static int ilog2_int(int value) {
  int log_value = 0;
  while ((1 << log_value) < value) {
    ++log_value;
  }
  return log_value;
}

__device__ unsigned bit_reverse(unsigned value, int bits) {
  unsigned result = 0;
  for (int i = 0; i < bits; ++i) {
    result = (result << 1) | (value & 1u);
    value >>= 1;
  }
  return result;
}

__global__ void init_fft_input(float2* data, int points, int log_points,
                               int batches) {
  int tid = blockIdx.x * blockDim.x + threadIdx.x;
  int total = points * batches;
  if (tid >= total) {
    return;
  }

  int sample = tid % points;
  int batch = tid / points;
  int dst = batch * points + bit_reverse(static_cast<unsigned>(sample),
                                         log_points);
  float x = static_cast<float>(sample + 1);
  float b = static_cast<float>(batch + 1);
  data[dst] = make_float2(sinf(0.011f * x) + cosf(0.00013f * b * x),
                          0.25f * cosf(0.017f * x + 0.0007f * b));
}

__global__ void fft_stage(float2* data, int points, int half_span) {
  int tid = blockIdx.x * blockDim.x + threadIdx.x;
  int butterflies_per_batch = points >> 1;
  if (tid >= butterflies_per_batch) {
    return;
  }

  int batch = blockIdx.y;
  int j = tid;
  int lane = j & (half_span - 1);
  int group = j / half_span;
  int base = batch * points + group * (half_span << 1) + lane;

  const float two_pi = 6.28318530717958647692f;
  float angle = -two_pi * static_cast<float>(lane) /
                static_cast<float>(half_span << 1);
  float s;
  float c;
  __sincosf(angle, &s, &c);

  float2 a = data[base];
  float2 b = data[base + half_span];
  float2 wb = make_float2(c * b.x - s * b.y, s * b.x + c * b.y);
  data[base] = make_float2(a.x + wb.x, a.y + wb.y);
  data[base + half_span] = make_float2(a.x - wb.x, a.y - wb.y);
}

__global__ void checksum_fft(const float2* data, float* partial, int total) {
  extern __shared__ float scratch[];
  int tid = threadIdx.x;
  int idx = blockIdx.x * blockDim.x + tid;
  float value = 0.0f;
  if (idx < total) {
    float2 z = data[idx];
    value = fabsf(z.x) + fabsf(z.y);
  }
  scratch[tid] = value;
  __syncthreads();

  for (int stride = blockDim.x >> 1; stride > 0; stride >>= 1) {
    if (tid < stride) {
      scratch[tid] += scratch[tid + stride];
    }
    __syncthreads();
  }
  if (tid == 0) {
    partial[blockIdx.x] = scratch[0];
  }
}

int main(int argc, char** argv) {
  int points = parse_int_arg(argc, argv, "--points", 1024);
  int batches = parse_int_arg(argc, argv, "--batches", 4096);
  int iters = parse_int_arg(argc, argv, "--iters", 4);

  if (!is_power_of_two(points)) {
    std::fprintf(stderr, "--points must be a power of two greater than 1\n");
    return 2;
  }
  if (batches <= 0 || iters <= 0) {
    std::fprintf(stderr, "--batches and --iters must be positive\n");
    return 2;
  }

  int log_points = ilog2_int(points);
  int total = points * batches;
  float2* data = nullptr;
  CHECK_CUDA(cudaMalloc(&data, static_cast<size_t>(total) * sizeof(float2)));

  int threads = 256;
  int init_blocks = (total + threads - 1) / threads;
  init_fft_input<<<init_blocks, threads>>>(data, points, log_points, batches);
  CHECK_CUDA(cudaGetLastError());

  int butterflies = points >> 1;
  dim3 stage_grid((butterflies + threads - 1) / threads, batches);
  for (int iter = 0; iter < iters; ++iter) {
    for (int half_span = 1; half_span < points; half_span <<= 1) {
      fft_stage<<<stage_grid, threads>>>(data, points, half_span);
      CHECK_CUDA(cudaGetLastError());
    }
  }

  int reduce_blocks = (total + threads - 1) / threads;
  float* partial = nullptr;
  CHECK_CUDA(cudaMalloc(&partial, static_cast<size_t>(reduce_blocks) *
                                      sizeof(float)));
  checksum_fft<<<reduce_blocks, threads, threads * sizeof(float)>>>(data,
                                                                    partial,
                                                                    total);
  CHECK_CUDA(cudaGetLastError());

  float* host = static_cast<float*>(std::malloc(static_cast<size_t>(
      reduce_blocks) * sizeof(float)));
  CHECK_CUDA(cudaMemcpy(host, partial,
                        static_cast<size_t>(reduce_blocks) * sizeof(float),
                        cudaMemcpyDeviceToHost));

  double checksum = 0.0;
  for (int i = 0; i < reduce_blocks; ++i) {
    checksum += host[i];
  }

  std::printf("fft_stockham points=%d batches=%d iters=%d checksum=%.6e\n",
              points, batches, iters, checksum);

  std::free(host);
  CHECK_CUDA(cudaFree(partial));
  CHECK_CUDA(cudaFree(data));
  return 0;
}

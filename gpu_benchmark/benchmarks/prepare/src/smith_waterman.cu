#include <cuda_runtime.h>

#include <algorithm>
#include <cstdint>
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

static constexpr int kMaxLen = 256;

static int parse_int_arg(int argc, char** argv, const char* name, int value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], name) == 0) {
      return std::atoi(argv[i + 1]);
    }
  }
  return value;
}

__global__ void init_sequences(uint8_t* seq_a, uint8_t* seq_b, int pairs,
                               int len) {
  int tid = blockIdx.x * blockDim.x + threadIdx.x;
  int total = pairs * len;
  if (tid >= total) {
    return;
  }
  int pair = tid / len;
  int pos = tid - pair * len;
  uint32_t x = static_cast<uint32_t>(pair * 1103515245u + pos * 12345u);
  x ^= x >> 13;
  seq_a[tid] = static_cast<uint8_t>(x & 3u);
  x = x * 1664525u + 1013904223u;
  seq_b[tid] = static_cast<uint8_t>((x >> 3) & 3u);
}

__global__ void smith_waterman_kernel(const uint8_t* seq_a,
                                      const uint8_t* seq_b, int pairs, int len,
                                      int* scores) {
  int pair = blockIdx.x * blockDim.x + threadIdx.x;
  if (pair >= pairs) {
    return;
  }

  int prev[kMaxLen + 1];
  int curr[kMaxLen + 1];
  for (int j = 0; j <= len; ++j) {
    prev[j] = 0;
    curr[j] = 0;
  }

  int best = 0;
  int base = pair * len;
  for (int i = 1; i <= len; ++i) {
    curr[0] = 0;
    uint8_t a = seq_a[base + i - 1];
    for (int j = 1; j <= len; ++j) {
      uint8_t b = seq_b[base + j - 1];
      int diag = prev[j - 1] + (a == b ? 2 : -1);
      int del = prev[j] - 2;
      int ins = curr[j - 1] - 2;
      int score = max(0, max(diag, max(del, ins)));
      curr[j] = score;
      best = max(best, score);
    }
    for (int j = 0; j <= len; ++j) {
      prev[j] = curr[j];
    }
  }
  scores[pair] = best;
}

__global__ void reduce_scores(const int* scores, int* partial, int pairs) {
  extern __shared__ int scratch[];
  int tid = threadIdx.x;
  int idx = blockIdx.x * blockDim.x + tid;
  int value = (idx < pairs) ? scores[idx] : 0;
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
  int pairs = parse_int_arg(argc, argv, "--pairs", 32768);
  int len = parse_int_arg(argc, argv, "--len", 128);
  if (pairs <= 0 || len <= 0 || len > kMaxLen) {
    std::fprintf(stderr, "--pairs must be positive and --len must be 1..%d\n",
                 kMaxLen);
    return 2;
  }

  uint8_t* seq_a = nullptr;
  uint8_t* seq_b = nullptr;
  int* scores = nullptr;
  size_t seq_bytes = static_cast<size_t>(pairs) * static_cast<size_t>(len);
  CHECK_CUDA(cudaMalloc(&seq_a, seq_bytes));
  CHECK_CUDA(cudaMalloc(&seq_b, seq_bytes));
  CHECK_CUDA(cudaMalloc(&scores, static_cast<size_t>(pairs) * sizeof(int)));

  int threads = 128;
  int init_threads = 256;
  int init_blocks = (static_cast<int>(seq_bytes) + init_threads - 1) /
                    init_threads;
  init_sequences<<<init_blocks, init_threads>>>(seq_a, seq_b, pairs, len);
  CHECK_CUDA(cudaGetLastError());

  int sw_blocks = (pairs + threads - 1) / threads;
  smith_waterman_kernel<<<sw_blocks, threads>>>(seq_a, seq_b, pairs, len,
                                                scores);
  CHECK_CUDA(cudaGetLastError());

  int reduce_threads = 256;
  int reduce_blocks = (pairs + reduce_threads - 1) / reduce_threads;
  int* partial = nullptr;
  CHECK_CUDA(cudaMalloc(&partial, static_cast<size_t>(reduce_blocks) *
                                      sizeof(int)));
  reduce_scores<<<reduce_blocks, reduce_threads,
                  reduce_threads * sizeof(int)>>>(scores, partial, pairs);
  CHECK_CUDA(cudaGetLastError());

  int* host = static_cast<int*>(std::malloc(static_cast<size_t>(
      reduce_blocks) * sizeof(int)));
  CHECK_CUDA(cudaMemcpy(host, partial,
                        static_cast<size_t>(reduce_blocks) * sizeof(int),
                        cudaMemcpyDeviceToHost));
  long long checksum = 0;
  for (int i = 0; i < reduce_blocks; ++i) {
    checksum += host[i];
  }

  std::printf("smith_waterman pairs=%d len=%d score_sum=%lld\n", pairs, len,
              checksum);

  std::free(host);
  CHECK_CUDA(cudaFree(partial));
  CHECK_CUDA(cudaFree(scores));
  CHECK_CUDA(cudaFree(seq_b));
  CHECK_CUDA(cudaFree(seq_a));
  return 0;
}

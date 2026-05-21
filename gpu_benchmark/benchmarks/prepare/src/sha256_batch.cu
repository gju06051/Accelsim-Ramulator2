#include <cuda_runtime.h>

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

static int parse_int_arg(int argc, char** argv, const char* name, int value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], name) == 0) {
      return std::atoi(argv[i + 1]);
    }
  }
  return value;
}

__constant__ uint32_t k_sha256[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu,
    0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u, 0xd807aa98u, 0x12835b01u,
    0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u,
    0xc19bf174u, 0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau, 0x983e5152u,
    0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u,
    0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu,
    0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u, 0xd192e819u,
    0xd6990624u, 0xf40e3585u, 0x106aa070u, 0x19a4c116u, 0x1e376c08u,
    0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu,
    0x682e6ff3u, 0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};

__device__ uint32_t rotr(uint32_t x, int n) {
  return (x >> n) | (x << (32 - n));
}

__device__ uint32_t ch(uint32_t x, uint32_t y, uint32_t z) {
  return (x & y) ^ (~x & z);
}

__device__ uint32_t maj(uint32_t x, uint32_t y, uint32_t z) {
  return (x & y) ^ (x & z) ^ (y & z);
}

__device__ uint32_t big_sigma0(uint32_t x) {
  return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22);
}

__device__ uint32_t big_sigma1(uint32_t x) {
  return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25);
}

__device__ uint32_t small_sigma0(uint32_t x) {
  return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3);
}

__device__ uint32_t small_sigma1(uint32_t x) {
  return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10);
}

__device__ uint32_t make_word(uint32_t seed, int word) {
  uint32_t x = seed ^ (0x9e3779b9u * static_cast<uint32_t>(word + 1));
  x ^= x >> 16;
  x *= 0x7feb352du;
  x ^= x >> 15;
  x *= 0x846ca68bu;
  x ^= x >> 16;
  return x;
}

__device__ uint32_t sha256_one(uint32_t seed) {
  uint32_t w[64];
#pragma unroll
  for (int i = 0; i < 13; ++i) {
    w[i] = make_word(seed, i);
  }
  w[13] = (make_word(seed, 13) & 0xffffff00u) | 0x80u;
  w[14] = 0u;
  w[15] = 55u * 8u;
#pragma unroll
  for (int i = 16; i < 64; ++i) {
    w[i] = small_sigma1(w[i - 2]) + w[i - 7] + small_sigma0(w[i - 15]) +
           w[i - 16];
  }

  uint32_t a = 0x6a09e667u;
  uint32_t b = 0xbb67ae85u;
  uint32_t c = 0x3c6ef372u;
  uint32_t d = 0xa54ff53au;
  uint32_t e = 0x510e527fu;
  uint32_t f = 0x9b05688cu;
  uint32_t g = 0x1f83d9abu;
  uint32_t h = 0x5be0cd19u;

#pragma unroll 64
  for (int i = 0; i < 64; ++i) {
    uint32_t t1 = h + big_sigma1(e) + ch(e, f, g) + k_sha256[i] + w[i];
    uint32_t t2 = big_sigma0(a) + maj(a, b, c);
    h = g;
    g = f;
    f = e;
    e = d + t1;
    d = c;
    c = b;
    b = a;
    a = t1 + t2;
  }

  a += 0x6a09e667u;
  b += 0xbb67ae85u;
  c += 0x3c6ef372u;
  d += 0xa54ff53au;
  e += 0x510e527fu;
  f += 0x9b05688cu;
  g += 0x1f83d9abu;
  h += 0x5be0cd19u;
  return a ^ b ^ c ^ d ^ e ^ f ^ g ^ h;
}

__global__ void sha256_kernel(int messages, int iters, uint32_t* partial) {
  extern __shared__ uint32_t scratch[];
  int tid = threadIdx.x;
  int msg = blockIdx.x * blockDim.x + tid;
  uint32_t digest = 0u;

  if (msg < messages) {
    uint32_t seed = 0x1234567u ^ static_cast<uint32_t>(msg * 2654435761u);
    for (int i = 0; i < iters; ++i) {
      digest ^= sha256_one(seed + static_cast<uint32_t>(i * 7919u));
    }
  }

  scratch[tid] = digest;
  __syncthreads();

  for (int stride = blockDim.x >> 1; stride > 0; stride >>= 1) {
    if (tid < stride) {
      scratch[tid] ^= scratch[tid + stride];
    }
    __syncthreads();
  }
  if (tid == 0) {
    partial[blockIdx.x] = scratch[0];
  }
}

int main(int argc, char** argv) {
  int messages = parse_int_arg(argc, argv, "--messages", 1 << 20);
  int iters = parse_int_arg(argc, argv, "--iters", 4);
  if (messages <= 0 || iters <= 0) {
    std::fprintf(stderr, "--messages and --iters must be positive\n");
    return 2;
  }

  int threads = 256;
  int blocks = (messages + threads - 1) / threads;
  uint32_t* partial = nullptr;
  CHECK_CUDA(cudaMalloc(&partial, static_cast<size_t>(blocks) *
                                      sizeof(uint32_t)));
  sha256_kernel<<<blocks, threads, threads * sizeof(uint32_t)>>>(messages,
                                                                 iters,
                                                                 partial);
  CHECK_CUDA(cudaGetLastError());

  uint32_t* host = static_cast<uint32_t*>(std::malloc(static_cast<size_t>(
      blocks) * sizeof(uint32_t)));
  CHECK_CUDA(cudaMemcpy(host, partial,
                        static_cast<size_t>(blocks) * sizeof(uint32_t),
                        cudaMemcpyDeviceToHost));
  uint32_t checksum = 0u;
  for (int i = 0; i < blocks; ++i) {
    checksum ^= host[i];
  }

  std::printf("sha256_batch messages=%d iters=%d checksum=%08x\n", messages,
              iters, checksum);

  std::free(host);
  CHECK_CUDA(cudaFree(partial));
  return 0;
}

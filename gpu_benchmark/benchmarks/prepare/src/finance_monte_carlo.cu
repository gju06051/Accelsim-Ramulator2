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

__device__ unsigned xorshift32(unsigned state) {
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
}

__device__ float uniform01(unsigned* state) {
  *state = xorshift32(*state);
  return (static_cast<float>((*state >> 8) + 1u)) * (1.0f / 16777217.0f);
}

__device__ float normal01(unsigned* state) {
  const float two_pi = 6.28318530717958647692f;
  float u1 = fmaxf(uniform01(state), 1.0e-7f);
  float u2 = uniform01(state);
  return sqrtf(-2.0f * logf(u1)) * cosf(two_pi * u2);
}

__global__ void asian_option_kernel(int paths, int steps, float* partial_sum,
                                    float* partial_sq) {
  extern __shared__ float scratch[];
  float* scratch_sum = scratch;
  float* scratch_sq = scratch + blockDim.x;
  int tid = threadIdx.x;
  int path = blockIdx.x * blockDim.x + tid;

  float payoff = 0.0f;
  if (path < paths) {
    unsigned rng = 0x9e3779b9u ^ static_cast<unsigned>(path * 747796405u);
    float spot = 100.0f;
    float strike = 101.0f;
    float rate = 0.03f;
    float vol = 0.20f;
    float maturity = 1.0f;
    float dt = maturity / static_cast<float>(steps);
    float drift = (rate - 0.5f * vol * vol) * dt;
    float diffusion = vol * sqrtf(dt);
    float sum_spot = 0.0f;

    for (int step = 0; step < steps; ++step) {
      float z = normal01(&rng);
      spot *= expf(drift + diffusion * z);
      sum_spot += spot;
    }
    float average = sum_spot / static_cast<float>(steps);
    payoff = fmaxf(average - strike, 0.0f) * expf(-rate * maturity);
  }

  scratch_sum[tid] = payoff;
  scratch_sq[tid] = payoff * payoff;
  __syncthreads();

  for (int stride = blockDim.x >> 1; stride > 0; stride >>= 1) {
    if (tid < stride) {
      scratch_sum[tid] += scratch_sum[tid + stride];
      scratch_sq[tid] += scratch_sq[tid + stride];
    }
    __syncthreads();
  }

  if (tid == 0) {
    partial_sum[blockIdx.x] = scratch_sum[0];
    partial_sq[blockIdx.x] = scratch_sq[0];
  }
}

int main(int argc, char** argv) {
  int paths = parse_int_arg(argc, argv, "--paths", 1 << 20);
  int steps = parse_int_arg(argc, argv, "--steps", 64);
  if (paths <= 0 || steps <= 0) {
    std::fprintf(stderr, "--paths and --steps must be positive\n");
    return 2;
  }

  int threads = 256;
  int blocks = (paths + threads - 1) / threads;
  float* partial_sum = nullptr;
  float* partial_sq = nullptr;
  CHECK_CUDA(cudaMalloc(&partial_sum, static_cast<size_t>(blocks) *
                                      sizeof(float)));
  CHECK_CUDA(cudaMalloc(&partial_sq, static_cast<size_t>(blocks) *
                                     sizeof(float)));

  asian_option_kernel<<<blocks, threads, 2 * threads * sizeof(float)>>>(
      paths, steps, partial_sum, partial_sq);
  CHECK_CUDA(cudaGetLastError());

  float* host_sum = static_cast<float*>(std::malloc(static_cast<size_t>(
      blocks) * sizeof(float)));
  float* host_sq = static_cast<float*>(std::malloc(static_cast<size_t>(
      blocks) * sizeof(float)));
  CHECK_CUDA(cudaMemcpy(host_sum, partial_sum,
                        static_cast<size_t>(blocks) * sizeof(float),
                        cudaMemcpyDeviceToHost));
  CHECK_CUDA(cudaMemcpy(host_sq, partial_sq,
                        static_cast<size_t>(blocks) * sizeof(float),
                        cudaMemcpyDeviceToHost));

  double sum = 0.0;
  double sum_sq = 0.0;
  for (int i = 0; i < blocks; ++i) {
    sum += host_sum[i];
    sum_sq += host_sq[i];
  }
  double mean = sum / static_cast<double>(paths);
  double variance = sum_sq / static_cast<double>(paths) - mean * mean;
  double std_err = sqrt(fmax(variance, 0.0) / static_cast<double>(paths));

  std::printf("finance_monte_carlo paths=%d steps=%d price=%.6f stderr=%.6f\n",
              paths, steps, mean, std_err);

  std::free(host_sum);
  std::free(host_sq);
  CHECK_CUDA(cudaFree(partial_sq));
  CHECK_CUDA(cudaFree(partial_sum));
  return 0;
}

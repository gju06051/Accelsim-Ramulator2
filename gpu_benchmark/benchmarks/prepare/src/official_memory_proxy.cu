#include <cuda_runtime.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define CHECK_CUDA(call)                                                      \
  do {                                                                        \
    cudaError_t err__ = (call);                                                \
    if (err__ != cudaSuccess) {                                                \
      std::fprintf(stderr, "CUDA error %s:%d: %s\n", __FILE__, __LINE__,      \
                   cudaGetErrorString(err__));                                \
      std::exit(1);                                                            \
    }                                                                         \
  } while (0)

static bool arg_eq(const char* a, const char* b) { return std::strcmp(a, b) == 0; }

static int parse_int_arg(int argc, char** argv, const char* name, int value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (arg_eq(argv[i], name)) {
      return std::atoi(argv[i + 1]);
    }
  }
  return value;
}

static float parse_float_arg(int argc, char** argv, const char* name,
                             float value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (arg_eq(argv[i], name)) {
      return std::strtof(argv[i + 1], nullptr);
    }
  }
  return value;
}

static const char* parse_string_arg(int argc, char** argv, const char* name,
                                    const char* value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (arg_eq(argv[i], name)) {
      return argv[i + 1];
    }
  }
  return value;
}

static int div_up(int value, int divisor) {
  return (value + divisor - 1) / divisor;
}

static unsigned mix32(unsigned x) {
  x ^= x >> 16;
  x *= 0x7feb352du;
  x ^= x >> 15;
  x *= 0x846ca68bu;
  x ^= x >> 16;
  return x;
}

__global__ void dlrm_embedding_kernel(const float* __restrict__ table,
                                      const unsigned* __restrict__ indices,
                                      float* __restrict__ out, int bags,
                                      int lookups, int dim) {
  int linear = blockIdx.x * blockDim.x + threadIdx.x;
  int total = bags * dim;
  if (linear >= total) {
    return;
  }
  int d = linear % dim;
  int bag = linear / dim;
  float sum = 0.0f;
  for (int k = 0; k < lookups; ++k) {
    unsigned idx = indices[bag * lookups + k];
    sum += table[idx * dim + d];
  }
  out[linear] = sum;
}

__global__ void dlrm_sequence_kernel(const float* __restrict__ table,
                                     const unsigned* __restrict__ indices,
                                     float* __restrict__ out, int sequences,
                                     int seq_len, int dim) {
  int linear = blockIdx.x * blockDim.x + threadIdx.x;
  int total = sequences * dim;
  if (linear >= total) {
    return;
  }
  int d = linear % dim;
  int seq = linear / dim;
  float sum = 0.0f;
  for (int t = 0; t < seq_len; ++t) {
    unsigned idx = indices[seq * seq_len + t];
    float position_scale = 1.0f + 0.0001f * static_cast<float>((t + d) & 31);
    sum += table[idx * dim + d] * position_scale;
  }
  out[linear] = sum;
}

__global__ void gnn_feature_fetch_kernel(const float* __restrict__ features,
                                         const unsigned* __restrict__ src,
                                         float* __restrict__ edge_out,
                                         int edges, int dim) {
  int linear = blockIdx.x * blockDim.x + threadIdx.x;
  int total = edges * dim;
  if (linear >= total) {
    return;
  }
  int d = linear % dim;
  int e = linear / dim;
  unsigned node = src[e];
  edge_out[linear] = features[node * dim + d] * 1.0009765625f;
}

__global__ void gnn_relation_agg_kernel(const float* __restrict__ features,
                                        const float* __restrict__ weights,
                                        const unsigned* __restrict__ src,
                                        const unsigned* __restrict__ dst,
                                        const unsigned* __restrict__ rel,
                                        float* __restrict__ out, int edges,
                                        int dim) {
  int e = blockIdx.x * blockDim.x + threadIdx.x;
  if (e >= edges) {
    return;
  }
  unsigned s = src[e];
  unsigned dnode = dst[e];
  unsigned r = rel[e];
  for (int d = 0; d < dim; ++d) {
    float value = features[s * dim + d] * weights[r * dim + d];
    out[e * dim + d] =
        value + 0.000001f * static_cast<float>((dnode + static_cast<unsigned>(d)) & 31u);
  }
}

__global__ void coral_stream_triad_kernel(float* __restrict__ a,
                                          const float* __restrict__ b,
                                          const float* __restrict__ c,
                                          int n, float scalar) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n) {
    a[i] = b[i] + scalar * c[i];
  }
}

__global__ void coral_ltimes_kernel(const float* __restrict__ phi,
                                    const float* __restrict__ ell,
                                    float* __restrict__ psi, int zones,
                                    int groups, int dirs, int moments) {
  int linear = blockIdx.x * blockDim.x + threadIdx.x;
  int total = zones * groups * dirs;
  if (linear >= total) {
    return;
  }
  int z = linear % zones;
  int tmp = linear / zones;
  int g = tmp % groups;
  int dir = tmp / groups;
  float sum = 0.0f;
  for (int m = 0; m < moments; ++m) {
    sum += ell[dir * moments + m] * phi[(m * groups + g) * zones + z];
  }
  psi[linear] = sum;
}

__global__ void coral_energy_kernel(const float* __restrict__ x,
                                    const float* __restrict__ y,
                                    const float* __restrict__ z,
                                    float* __restrict__ e,
                                    float* __restrict__ p, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) {
    return;
  }
  float xi = x[i];
  float yi = y[i];
  float zi = z[i];
  float v = 0.25f * xi * xi + 0.5f * yi + 0.125f * zi;
  e[i] = v;
  p[i] = sqrtf(fabsf(v) + 0.001f) + xi * 0.01f;
}

__global__ void coral_planckian_kernel(const float* __restrict__ temp,
                                       float* __restrict__ out, int n,
                                       int groups) {
  int linear = blockIdx.x * blockDim.x + threadIdx.x;
  int total = n * groups;
  if (linear >= total) {
    return;
  }
  int g = linear % groups;
  int i = linear / groups;
  float t = temp[i] + 0.01f * static_cast<float>(g + 1);
  out[linear] = t * t / (expf(1.0f / fmaxf(t, 0.02f)) - 1.0f);
}

__global__ void coral_reduce3_kernel(const float* __restrict__ a,
                                     const float* __restrict__ b,
                                     const float* __restrict__ c,
                                     float* __restrict__ partial, int n) {
  extern __shared__ float scratch[];
  float* s0 = scratch;
  float* s1 = scratch + blockDim.x;
  float* s2 = scratch + 2 * blockDim.x;
  int tid = threadIdx.x;
  int i = blockIdx.x * blockDim.x + tid;
  s0[tid] = (i < n) ? a[i] : 0.0f;
  s1[tid] = (i < n) ? b[i] : 0.0f;
  s2[tid] = (i < n) ? c[i] : 0.0f;
  __syncthreads();
  for (int stride = blockDim.x >> 1; stride > 0; stride >>= 1) {
    if (tid < stride) {
      s0[tid] += s0[tid + stride];
      s1[tid] += s1[tid + stride];
      s2[tid] += s2[tid + stride];
    }
    __syncthreads();
  }
  if (tid == 0) {
    partial[3 * blockIdx.x + 0] = s0[0];
    partial[3 * blockIdx.x + 1] = s1[0];
    partial[3 * blockIdx.x + 2] = s2[0];
  }
}

static void fill_float(float* ptr, int n, unsigned seed) {
  std::vector<float> host(static_cast<size_t>(n));
  for (int i = 0; i < n; ++i) {
    unsigned h = mix32(seed ^ static_cast<unsigned>(i));
    host[static_cast<size_t>(i)] =
        static_cast<float>(h & 0xffffu) * (1.0f / 65536.0f);
  }
  CHECK_CUDA(cudaMemcpy(ptr, host.data(), static_cast<size_t>(n) * sizeof(float),
                        cudaMemcpyHostToDevice));
}

static void fill_indices(unsigned* ptr, int n, int modulo, unsigned seed) {
  std::vector<unsigned> host(static_cast<size_t>(n));
  for (int i = 0; i < n; ++i) {
    host[static_cast<size_t>(i)] =
        mix32(seed + static_cast<unsigned>(i) * 747796405u) %
        static_cast<unsigned>(modulo);
  }
  CHECK_CUDA(cudaMemcpy(ptr, host.data(),
                        static_cast<size_t>(n) * sizeof(unsigned),
                        cudaMemcpyHostToDevice));
}

static void fill_relations(unsigned* src, unsigned* dst, unsigned* rel,
                           int edges, int nodes, int relations) {
  std::vector<unsigned> host_src(static_cast<size_t>(edges));
  std::vector<unsigned> host_dst(static_cast<size_t>(edges));
  std::vector<unsigned> host_rel(static_cast<size_t>(edges));
  for (int i = 0; i < edges; ++i) {
    unsigned h = mix32(0x1234abcdU ^ static_cast<unsigned>(i));
    host_src[static_cast<size_t>(i)] = h % static_cast<unsigned>(nodes);
    host_dst[static_cast<size_t>(i)] =
        mix32(h ^ 0x9e3779b9U) % static_cast<unsigned>(nodes);
    host_rel[static_cast<size_t>(i)] =
        mix32(h ^ 0x51ed270bU) % static_cast<unsigned>(relations);
  }
  CHECK_CUDA(cudaMemcpy(src, host_src.data(),
                        static_cast<size_t>(edges) * sizeof(unsigned),
                        cudaMemcpyHostToDevice));
  CHECK_CUDA(cudaMemcpy(dst, host_dst.data(),
                        static_cast<size_t>(edges) * sizeof(unsigned),
                        cudaMemcpyHostToDevice));
  CHECK_CUDA(cudaMemcpy(rel, host_rel.data(),
                        static_cast<size_t>(edges) * sizeof(unsigned),
                        cudaMemcpyHostToDevice));
}

static float sample_value(const float* device_ptr) {
  float value = 0.0f;
  CHECK_CUDA(cudaMemcpy(&value, device_ptr, sizeof(float),
                        cudaMemcpyDeviceToHost));
  return value;
}

static int run_dlrm_embedding(int argc, char** argv, const char* mode) {
  int bags = parse_int_arg(argc, argv, "--bags",
                           arg_eq(mode, "dlrm_embedding_quantile") ? 16384 : 32768);
  int lookups = parse_int_arg(argc, argv, "--lookups",
                              arg_eq(mode, "dlrm_embedding_quantile") ? 100 : 32);
  int dim = parse_int_arg(argc, argv, "--dim", 64);
  int entries = parse_int_arg(argc, argv, "--entries", 262144);
  int iters = parse_int_arg(argc, argv, "--iters", 1);
  if (bags <= 0 || lookups <= 0 || dim <= 0 || entries <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid DLRM embedding arguments\n");
    return 2;
  }

  float* table = nullptr;
  float* out = nullptr;
  unsigned* indices = nullptr;
  CHECK_CUDA(cudaMalloc(&table, static_cast<size_t>(entries) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&out, static_cast<size_t>(bags) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&indices, static_cast<size_t>(bags) * lookups * sizeof(unsigned)));
  fill_float(table, entries * dim, 0xd1a50001u);
  fill_indices(indices, bags * lookups, entries, 0xd1a50002u);

  int threads = 256;
  int total = bags * dim;
  for (int i = 0; i < iters; ++i) {
    dlrm_embedding_kernel<<<div_up(total, threads), threads>>>(
        table, indices, out, bags, lookups, dim);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(out);
  std::printf("%s bags=%d lookups=%d dim=%d entries=%d iters=%d sample=%0.6f\n",
              mode, bags, lookups, dim, entries, iters, value);
  CHECK_CUDA(cudaFree(indices));
  CHECK_CUDA(cudaFree(out));
  CHECK_CUDA(cudaFree(table));
  return 0;
}

static int run_dlrm_sequence(int argc, char** argv) {
  int sequences = parse_int_arg(argc, argv, "--sequences", 32768);
  int seq_len = parse_int_arg(argc, argv, "--seq-len", 64);
  int dim = parse_int_arg(argc, argv, "--dim", 32);
  int entries = parse_int_arg(argc, argv, "--entries", 524288);
  int iters = parse_int_arg(argc, argv, "--iters", 1);
  if (sequences <= 0 || seq_len <= 0 || dim <= 0 || entries <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid DLRM sequence arguments\n");
    return 2;
  }

  float* table = nullptr;
  float* out = nullptr;
  unsigned* indices = nullptr;
  CHECK_CUDA(cudaMalloc(&table, static_cast<size_t>(entries) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&out, static_cast<size_t>(sequences) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&indices, static_cast<size_t>(sequences) * seq_len * sizeof(unsigned)));
  fill_float(table, entries * dim, 0xd1a50011u);
  fill_indices(indices, sequences * seq_len, entries, 0xd1a50012u);

  int threads = 256;
  int total = sequences * dim;
  for (int i = 0; i < iters; ++i) {
    dlrm_sequence_kernel<<<div_up(total, threads), threads>>>(
        table, indices, out, sequences, seq_len, dim);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(out);
  std::printf("dlrm_v3_sequence_gather sequences=%d seq_len=%d dim=%d entries=%d iters=%d sample=%0.6f\n",
              sequences, seq_len, dim, entries, iters, value);
  CHECK_CUDA(cudaFree(indices));
  CHECK_CUDA(cudaFree(out));
  CHECK_CUDA(cudaFree(table));
  return 0;
}

static int run_gnn_feature_fetch(int argc, char** argv, const char* label) {
  int edges = parse_int_arg(argc, argv, "--edges", 262144);
  int nodes = parse_int_arg(argc, argv, "--nodes", 65536);
  int dim = parse_int_arg(argc, argv, "--dim", 64);
  int iters = parse_int_arg(argc, argv, "--iters", 1);
  if (edges <= 0 || nodes <= 0 || dim <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid GNN fetch arguments\n");
    return 2;
  }

  float* features = nullptr;
  float* out = nullptr;
  unsigned* src = nullptr;
  CHECK_CUDA(cudaMalloc(&features, static_cast<size_t>(nodes) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&out, static_cast<size_t>(edges) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&src, static_cast<size_t>(edges) * sizeof(unsigned)));
  fill_float(features, nodes * dim, 0x600df001u);
  fill_indices(src, edges, nodes, 0x600df002u);

  int threads = 256;
  int total = edges * dim;
  for (int i = 0; i < iters; ++i) {
    gnn_feature_fetch_kernel<<<div_up(total, threads), threads>>>(
        features, src, out, edges, dim);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(out);
  std::printf("%s edges=%d nodes=%d dim=%d iters=%d sample=%0.6f\n",
              label, edges, nodes, dim, iters, value);
  CHECK_CUDA(cudaFree(src));
  CHECK_CUDA(cudaFree(out));
  CHECK_CUDA(cudaFree(features));
  return 0;
}

static int run_gnn_relation_agg(int argc, char** argv, const char* label) {
  int edges = parse_int_arg(argc, argv, "--edges", 131072);
  int nodes = parse_int_arg(argc, argv, "--nodes", 32768);
  int dim = parse_int_arg(argc, argv, "--dim", 32);
  int relations = parse_int_arg(argc, argv, "--relations", 4);
  int iters = parse_int_arg(argc, argv, "--iters", 1);
  if (edges <= 0 || nodes <= 0 || dim <= 0 || relations <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid GNN aggregation arguments\n");
    return 2;
  }

  float* features = nullptr;
  float* weights = nullptr;
  float* out = nullptr;
  unsigned* src = nullptr;
  unsigned* dst = nullptr;
  unsigned* rel = nullptr;
  CHECK_CUDA(cudaMalloc(&features, static_cast<size_t>(nodes) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&weights, static_cast<size_t>(relations) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&out, static_cast<size_t>(edges) * dim * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&src, static_cast<size_t>(edges) * sizeof(unsigned)));
  CHECK_CUDA(cudaMalloc(&dst, static_cast<size_t>(edges) * sizeof(unsigned)));
  CHECK_CUDA(cudaMalloc(&rel, static_cast<size_t>(edges) * sizeof(unsigned)));
  fill_float(features, nodes * dim, 0x600da001u);
  fill_float(weights, relations * dim, 0x600da002u);
  fill_relations(src, dst, rel, edges, nodes, relations);

  for (int i = 0; i < iters; ++i) {
    gnn_relation_agg_kernel<<<div_up(edges, 128), 128>>>(
        features, weights, src, dst, rel, out, edges, dim);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(out);
  std::printf("%s edges=%d nodes=%d dim=%d relations=%d iters=%d sample=%0.6f\n",
              label, edges, nodes, dim, relations, iters, value);
  CHECK_CUDA(cudaFree(rel));
  CHECK_CUDA(cudaFree(dst));
  CHECK_CUDA(cudaFree(src));
  CHECK_CUDA(cudaFree(out));
  CHECK_CUDA(cudaFree(weights));
  CHECK_CUDA(cudaFree(features));
  return 0;
}

static int run_coral_stream(int argc, char** argv) {
  int n = parse_int_arg(argc, argv, "--elements", 4194304);
  int iters = parse_int_arg(argc, argv, "--iters", 3);
  float scalar = parse_float_arg(argc, argv, "--scalar", 1.618f);
  if (n <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid CORAL stream arguments\n");
    return 2;
  }
  float* a = nullptr;
  float* b = nullptr;
  float* c = nullptr;
  CHECK_CUDA(cudaMalloc(&a, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&b, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&c, static_cast<size_t>(n) * sizeof(float)));
  fill_float(b, n, 0xc02a1001u);
  fill_float(c, n, 0xc02a1002u);
  for (int i = 0; i < iters; ++i) {
    coral_stream_triad_kernel<<<div_up(n, 256), 256>>>(a, b, c, n, scalar);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(a);
  std::printf("coral_stream_triad elements=%d iters=%d sample=%0.6f\n", n, iters, value);
  CHECK_CUDA(cudaFree(c));
  CHECK_CUDA(cudaFree(b));
  CHECK_CUDA(cudaFree(a));
  return 0;
}

static int run_coral_ltimes(int argc, char** argv) {
  int zones = parse_int_arg(argc, argv, "--zones", 8192);
  int groups = parse_int_arg(argc, argv, "--groups", 32);
  int dirs = parse_int_arg(argc, argv, "--dirs", 32);
  int moments = parse_int_arg(argc, argv, "--moments", 8);
  int iters = parse_int_arg(argc, argv, "--iters", 1);
  if (zones <= 0 || groups <= 0 || dirs <= 0 || moments <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid CORAL LTimes arguments\n");
    return 2;
  }
  float* phi = nullptr;
  float* ell = nullptr;
  float* psi = nullptr;
  int phi_n = zones * groups * moments;
  int ell_n = dirs * moments;
  int psi_n = zones * groups * dirs;
  CHECK_CUDA(cudaMalloc(&phi, static_cast<size_t>(phi_n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&ell, static_cast<size_t>(ell_n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&psi, static_cast<size_t>(psi_n) * sizeof(float)));
  fill_float(phi, phi_n, 0xc02a2001u);
  fill_float(ell, ell_n, 0xc02a2002u);
  for (int i = 0; i < iters; ++i) {
    coral_ltimes_kernel<<<div_up(psi_n, 256), 256>>>(
        phi, ell, psi, zones, groups, dirs, moments);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(psi);
  std::printf("coral_ltimes zones=%d groups=%d dirs=%d moments=%d iters=%d sample=%0.6f\n",
              zones, groups, dirs, moments, iters, value);
  CHECK_CUDA(cudaFree(psi));
  CHECK_CUDA(cudaFree(ell));
  CHECK_CUDA(cudaFree(phi));
  return 0;
}

static int run_coral_energy(int argc, char** argv) {
  int n = parse_int_arg(argc, argv, "--elements", 4194304);
  int iters = parse_int_arg(argc, argv, "--iters", 2);
  if (n <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid CORAL energy arguments\n");
    return 2;
  }
  float *x = nullptr, *y = nullptr, *z = nullptr, *e = nullptr, *p = nullptr;
  CHECK_CUDA(cudaMalloc(&x, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&y, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&z, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&e, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&p, static_cast<size_t>(n) * sizeof(float)));
  fill_float(x, n, 0xc02a3001u);
  fill_float(y, n, 0xc02a3002u);
  fill_float(z, n, 0xc02a3003u);
  for (int i = 0; i < iters; ++i) {
    coral_energy_kernel<<<div_up(n, 256), 256>>>(x, y, z, e, p, n);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(e);
  std::printf("coral_energy elements=%d iters=%d sample=%0.6f\n", n, iters, value);
  CHECK_CUDA(cudaFree(p));
  CHECK_CUDA(cudaFree(e));
  CHECK_CUDA(cudaFree(z));
  CHECK_CUDA(cudaFree(y));
  CHECK_CUDA(cudaFree(x));
  return 0;
}

static int run_coral_planckian(int argc, char** argv) {
  int n = parse_int_arg(argc, argv, "--elements", 1048576);
  int groups = parse_int_arg(argc, argv, "--groups", 16);
  int iters = parse_int_arg(argc, argv, "--iters", 1);
  if (n <= 0 || groups <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid CORAL planckian arguments\n");
    return 2;
  }
  float* temp = nullptr;
  float* out = nullptr;
  CHECK_CUDA(cudaMalloc(&temp, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&out, static_cast<size_t>(n) * groups * sizeof(float)));
  fill_float(temp, n, 0xc02a4001u);
  for (int i = 0; i < iters; ++i) {
    coral_planckian_kernel<<<div_up(n * groups, 256), 256>>>(temp, out, n, groups);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(out);
  std::printf("coral_planckian elements=%d groups=%d iters=%d sample=%0.6f\n",
              n, groups, iters, value);
  CHECK_CUDA(cudaFree(out));
  CHECK_CUDA(cudaFree(temp));
  return 0;
}

static int run_coral_reduce3(int argc, char** argv) {
  int n = parse_int_arg(argc, argv, "--elements", 4194304);
  int iters = parse_int_arg(argc, argv, "--iters", 2);
  if (n <= 0 || iters <= 0) {
    std::fprintf(stderr, "invalid CORAL reduce3 arguments\n");
    return 2;
  }
  float *a = nullptr, *b = nullptr, *c = nullptr, *partial = nullptr;
  int threads = 256;
  int blocks = div_up(n, threads);
  CHECK_CUDA(cudaMalloc(&a, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&b, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&c, static_cast<size_t>(n) * sizeof(float)));
  CHECK_CUDA(cudaMalloc(&partial, static_cast<size_t>(blocks) * 3 * sizeof(float)));
  fill_float(a, n, 0xc02a5001u);
  fill_float(b, n, 0xc02a5002u);
  fill_float(c, n, 0xc02a5003u);
  for (int i = 0; i < iters; ++i) {
    coral_reduce3_kernel<<<blocks, threads, 3 * threads * sizeof(float)>>>(
        a, b, c, partial, n);
    CHECK_CUDA(cudaGetLastError());
  }
  CHECK_CUDA(cudaDeviceSynchronize());
  float value = sample_value(partial);
  std::printf("coral_reduce3 elements=%d iters=%d sample=%0.6f\n", n, iters, value);
  CHECK_CUDA(cudaFree(partial));
  CHECK_CUDA(cudaFree(c));
  CHECK_CUDA(cudaFree(b));
  CHECK_CUDA(cudaFree(a));
  return 0;
}

int main(int argc, char** argv) {
  const char* mode = parse_string_arg(argc, argv, "--mode", "");
  if (mode[0] == '\0' || arg_eq(mode, "help") || arg_eq(mode, "--help")) {
    std::printf("usage: official_memory_proxy --mode <mode> [args]\n");
    std::printf("modes: dlrm_embedding_fixed, dlrm_embedding_quantile, dlrm_v3_sequence_gather,\n");
    std::printf("       gnn_feature_fetch, gnn_relation_agg, gsuite_gcn_mp_pubmed,\n");
    std::printf("       gsuite_sage_mp_pubmed, gsuite_gin_wl_pubmed,\n");
    std::printf("       coral_stream_triad, coral_ltimes, coral_energy, coral_planckian, coral_reduce3\n");
    return mode[0] == '\0' ? 2 : 0;
  }

  if (arg_eq(mode, "dlrm_embedding_fixed") ||
      arg_eq(mode, "dlrm_embedding_quantile")) {
    return run_dlrm_embedding(argc, argv, mode);
  }
  if (arg_eq(mode, "dlrm_v3_sequence_gather")) {
    return run_dlrm_sequence(argc, argv);
  }
  if (arg_eq(mode, "gnn_feature_fetch")) {
    return run_gnn_feature_fetch(argc, argv, mode);
  }
  if (arg_eq(mode, "gnn_relation_agg")) {
    return run_gnn_relation_agg(argc, argv, mode);
  }
  if (arg_eq(mode, "gsuite_gcn_mp_pubmed")) {
    return run_gnn_feature_fetch(argc, argv, mode);
  }
  if (arg_eq(mode, "gsuite_sage_mp_pubmed")) {
    return run_gnn_relation_agg(argc, argv, mode);
  }
  if (arg_eq(mode, "gsuite_gin_wl_pubmed")) {
    return run_gnn_feature_fetch(argc, argv, mode);
  }
  if (arg_eq(mode, "coral_stream_triad")) {
    return run_coral_stream(argc, argv);
  }
  if (arg_eq(mode, "coral_ltimes")) {
    return run_coral_ltimes(argc, argv);
  }
  if (arg_eq(mode, "coral_energy")) {
    return run_coral_energy(argc, argv);
  }
  if (arg_eq(mode, "coral_planckian")) {
    return run_coral_planckian(argc, argv);
  }
  if (arg_eq(mode, "coral_reduce3")) {
    return run_coral_reduce3(argc, argv);
  }

  std::fprintf(stderr, "unknown mode: %s\n", mode);
  return 2;
}

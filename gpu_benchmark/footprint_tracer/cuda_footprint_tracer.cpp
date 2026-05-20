#include <cuda_runtime_api.h>
#include <dlfcn.h>
#include <pthread.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>

namespace {

pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
std::unordered_map<void *, size_t> g_live;
size_t g_current = 0;
size_t g_peak = 0;
size_t g_total = 0;
size_t g_max_single = 0;
size_t g_alloc_count = 0;
size_t g_free_count = 0;

template <typename T>
T next_symbol(const char *name) {
  static std::unordered_map<std::string, void *> symbols;
  pthread_mutex_lock(&g_lock);
  auto it = symbols.find(name);
  if (it != symbols.end()) {
    void *sym = it->second;
    pthread_mutex_unlock(&g_lock);
    return reinterpret_cast<T>(sym);
  }
  pthread_mutex_unlock(&g_lock);

  void *sym = dlsym(RTLD_NEXT, name);
  if (!sym) {
    std::fprintf(stderr, "cuda_footprint_tracer: failed to resolve %s: %s\n",
                 name, dlerror());
    std::abort();
  }

  pthread_mutex_lock(&g_lock);
  symbols[name] = sym;
  pthread_mutex_unlock(&g_lock);
  return reinterpret_cast<T>(sym);
}

void record_alloc(void *ptr, size_t size) {
  if (!ptr || size == 0) return;
  pthread_mutex_lock(&g_lock);
  auto old = g_live.find(ptr);
  if (old != g_live.end()) {
    g_current -= old->second;
    old->second = size;
  } else {
    g_live.emplace(ptr, size);
  }
  g_current += size;
  g_total += size;
  g_alloc_count++;
  if (g_current > g_peak) g_peak = g_current;
  if (size > g_max_single) g_max_single = size;
  pthread_mutex_unlock(&g_lock);
}

void record_free(void *ptr) {
  if (!ptr) return;
  pthread_mutex_lock(&g_lock);
  auto it = g_live.find(ptr);
  if (it != g_live.end()) {
    g_current -= it->second;
    g_live.erase(it);
  }
  g_free_count++;
  pthread_mutex_unlock(&g_lock);
}

size_t channel_desc_bytes(const cudaChannelFormatDesc *desc, size_t width,
                          size_t height, size_t depth) {
  if (!desc) return 0;
  int bits = desc->x + desc->y + desc->z + desc->w;
  if (bits <= 0) bits = 8;
  return ((static_cast<size_t>(bits) + 7) / 8) * width * height * depth;
}

std::string exe_path() {
  char path[4096];
  ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
  if (n <= 0) return "unknown";
  path[n] = '\0';
  return std::string(path);
}

void write_summary() {
  const char *log_path = std::getenv("CUDA_FOOTPRINT_LOG");
  if (!log_path || !*log_path) return;

  pthread_mutex_lock(&g_lock);
  size_t current = g_current;
  size_t peak = g_peak;
  size_t total = g_total;
  size_t max_single = g_max_single;
  size_t alloc_count = g_alloc_count;
  size_t free_count = g_free_count;
  size_t outstanding = g_live.size();
  pthread_mutex_unlock(&g_lock);

  FILE *f = std::fopen(log_path, "a");
  if (!f) return;
  std::string exe = exe_path();
  std::fprintf(
      f,
      "pid\texe\tpeak_live_device_bytes\tpeak_live_device_mib\t"
      "total_allocated_bytes\tmax_single_allocation_bytes\talloc_count\t"
      "free_count\tcurrent_live_bytes\toutstanding_allocations\n");
  std::fprintf(f, "%d\t%s\t%zu\t%.6f\t%zu\t%zu\t%zu\t%zu\t%zu\t%zu\n",
               static_cast<int>(getpid()), exe.c_str(), peak,
               static_cast<double>(peak) / (1024.0 * 1024.0), total,
               max_single, alloc_count, free_count, current, outstanding);
  std::fclose(f);
}

}  // namespace

extern "C" {

cudaError_t cudaMalloc(void **devPtr, size_t size) {
  using Fn = cudaError_t (*)(void **, size_t);
  Fn real = next_symbol<Fn>("cudaMalloc");
  cudaError_t err = real(devPtr, size);
  if (err == cudaSuccess && devPtr) record_alloc(*devPtr, size);
  return err;
}

cudaError_t cudaMallocManaged(void **devPtr, size_t size, unsigned int flags) {
  using Fn = cudaError_t (*)(void **, size_t, unsigned int);
  Fn real = next_symbol<Fn>("cudaMallocManaged");
  cudaError_t err = real(devPtr, size, flags);
  if (err == cudaSuccess && devPtr) record_alloc(*devPtr, size);
  return err;
}

cudaError_t cudaMallocPitch(void **devPtr, size_t *pitch, size_t width,
                            size_t height) {
  using Fn = cudaError_t (*)(void **, size_t *, size_t, size_t);
  Fn real = next_symbol<Fn>("cudaMallocPitch");
  cudaError_t err = real(devPtr, pitch, width, height);
  if (err == cudaSuccess && devPtr && pitch) record_alloc(*devPtr, *pitch * height);
  return err;
}

cudaError_t cudaMalloc3D(cudaPitchedPtr *pitchedDevPtr, cudaExtent extent) {
  using Fn = cudaError_t (*)(cudaPitchedPtr *, cudaExtent);
  Fn real = next_symbol<Fn>("cudaMalloc3D");
  cudaError_t err = real(pitchedDevPtr, extent);
  if (err == cudaSuccess && pitchedDevPtr) {
    record_alloc(pitchedDevPtr->ptr, pitchedDevPtr->pitch * extent.height *
                                      extent.depth);
  }
  return err;
}

cudaError_t cudaMallocArray(cudaArray_t *array,
                            const cudaChannelFormatDesc *desc, size_t width,
                            size_t height, unsigned int flags) {
  using Fn = cudaError_t (*)(cudaArray_t *, const cudaChannelFormatDesc *,
                             size_t, size_t, unsigned int);
  Fn real = next_symbol<Fn>("cudaMallocArray");
  cudaError_t err = real(array, desc, width, height, flags);
  if (err == cudaSuccess && array) {
    record_alloc(reinterpret_cast<void *>(*array),
                 channel_desc_bytes(desc, width, height ? height : 1, 1));
  }
  return err;
}

cudaError_t cudaMalloc3DArray(cudaArray_t *array,
                              const cudaChannelFormatDesc *desc,
                              cudaExtent extent, unsigned int flags) {
  using Fn = cudaError_t (*)(cudaArray_t *, const cudaChannelFormatDesc *,
                             cudaExtent, unsigned int);
  Fn real = next_symbol<Fn>("cudaMalloc3DArray");
  cudaError_t err = real(array, desc, extent, flags);
  if (err == cudaSuccess && array) {
    record_alloc(reinterpret_cast<void *>(*array),
                 channel_desc_bytes(desc, extent.width,
                                    extent.height ? extent.height : 1,
                                    extent.depth ? extent.depth : 1));
  }
  return err;
}

cudaError_t cudaFree(void *devPtr) {
  using Fn = cudaError_t (*)(void *);
  Fn real = next_symbol<Fn>("cudaFree");
  cudaError_t err = real(devPtr);
  if (err == cudaSuccess) record_free(devPtr);
  return err;
}

cudaError_t cudaFreeArray(cudaArray_t array) {
  using Fn = cudaError_t (*)(cudaArray_t);
  Fn real = next_symbol<Fn>("cudaFreeArray");
  cudaError_t err = real(array);
  if (err == cudaSuccess) record_free(reinterpret_cast<void *>(array));
  return err;
}

__attribute__((destructor)) void cuda_footprint_tracer_fini() {
  write_summary();
}

}

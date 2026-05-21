#include <cuda_runtime.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <memory>
#include <string>

#include "nvcomp.hpp"
#include "nvcomp/ans.hpp"
#include "nvcomp/bitcomp.hpp"
#include "nvcomp/cascaded.hpp"
#include "nvcomp/deflate.hpp"
#include "nvcomp/gdeflate.hpp"
#include "nvcomp/lz4.hpp"
#include "nvcomp/snappy.hpp"
#include "nvcomp/zstd.hpp"

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

static size_t parse_size_arg(int argc, char** argv, const char* name,
                             size_t value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], name) == 0) {
      return static_cast<size_t>(std::strtoull(argv[i + 1], nullptr, 0));
    }
  }
  return value;
}

static const char* parse_string_arg(int argc, char** argv, const char* name,
                                    const char* value) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (std::strcmp(argv[i], name) == 0) {
      return argv[i + 1];
    }
  }
  return value;
}

__global__ void fill_compressible_bytes(uint8_t* data, size_t bytes) {
  size_t idx = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
  if (idx >= bytes) {
    return;
  }

  size_t record = idx >> 6;
  size_t lane = idx & 63u;
  uint32_t base = static_cast<uint32_t>(record * 1315423911u + lane * 2654435761u);
  base ^= base >> 16;
  base *= 0x7feb352du;
  base ^= base >> 15;

  uint8_t value = static_cast<uint8_t>(base);
  if (lane < 40) {
    value = static_cast<uint8_t>(record & 0xffu);
  } else if (lane < 56) {
    value = static_cast<uint8_t>((record >> 4) & 0xffu);
  }
  data[idx] = value;
}

__global__ void count_mismatches(const uint8_t* expected, const uint8_t* actual,
                                 size_t bytes, unsigned long long* mismatch) {
  size_t idx = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
  if (idx < bytes && expected[idx] != actual[idx]) {
    atomicAdd(mismatch, 1ull);
  }
}

static std::unique_ptr<nvcomp::nvcompManagerBase> make_manager(
    const std::string& codec, size_t chunk_size) {
  if (codec == "lz4") {
    return std::make_unique<nvcomp::LZ4Manager>(chunk_size);
  }
  if (codec == "snappy") {
    return std::make_unique<nvcomp::SnappyManager>(chunk_size);
  }
  if (codec == "gdeflate") {
    return std::make_unique<nvcomp::GdeflateManager>(chunk_size);
  }
  if (codec == "deflate") {
    return std::make_unique<nvcomp::DeflateManager>(chunk_size);
  }
  if (codec == "zstd") {
    return std::make_unique<nvcomp::ZstdManager>(chunk_size);
  }
  if (codec == "cascaded") {
    return std::make_unique<nvcomp::CascadedManager>(chunk_size);
  }
  if (codec == "bitcomp") {
    return std::make_unique<nvcomp::BitcompManager>(chunk_size);
  }
  if (codec == "ans") {
    return std::make_unique<nvcomp::ANSManager>(chunk_size);
  }
  std::fprintf(stderr,
               "unknown --codec '%s' (expected lz4, snappy, gdeflate, "
               "deflate, zstd, cascaded, bitcomp, ans)\n",
               codec.c_str());
  std::exit(2);
}

int main(int argc, char** argv) {
  std::string codec = parse_string_arg(argc, argv, "--codec", "lz4");
  size_t bytes = parse_size_arg(argc, argv, "--bytes", 64ull << 20);
  size_t chunk_size = parse_size_arg(argc, argv, "--chunk-size", 1ull << 16);
  int iters = parse_int_arg(argc, argv, "--iters", 3);

  if (bytes == 0 || chunk_size == 0 || iters <= 0) {
    std::fprintf(stderr, "--bytes, --chunk-size, and --iters must be positive\n");
    return 2;
  }
  bytes = (bytes + 3u) & ~static_cast<size_t>(3u);
  chunk_size = (chunk_size + 3u) & ~static_cast<size_t>(3u);

  try {
    uint8_t* input = nullptr;
    uint8_t* compressed = nullptr;
    uint8_t* decompressed = nullptr;
    unsigned long long* mismatch_device = nullptr;

    CHECK_CUDA(cudaMalloc(&input, bytes));
    int threads = 256;
    int blocks = static_cast<int>((bytes + threads - 1) / threads);
    fill_compressible_bytes<<<blocks, threads>>>(input, bytes);
    CHECK_CUDA(cudaGetLastError());

    auto manager = make_manager(codec, chunk_size);
    auto comp_config = manager->configure_compression(bytes);
    CHECK_CUDA(cudaMalloc(&compressed, comp_config.max_compressed_buffer_size));
    CHECK_CUDA(cudaMalloc(&mismatch_device, sizeof(unsigned long long)));

    cudaEvent_t start;
    cudaEvent_t stop;
    CHECK_CUDA(cudaEventCreate(&start));
    CHECK_CUDA(cudaEventCreate(&stop));
    CHECK_CUDA(cudaEventRecord(start));

    size_t compressed_size = 0;
    size_t decompressed_size = bytes;
    for (int iter = 0; iter < iters; ++iter) {
      manager->compress(input, compressed, comp_config);
      CHECK_CUDA(cudaDeviceSynchronize());
      compressed_size = manager->get_compressed_output_size(compressed);

      auto decomp_config = manager->configure_decompression(compressed);
      decompressed_size = decomp_config.decomp_data_size;
      if (decompressed == nullptr) {
        CHECK_CUDA(cudaMalloc(&decompressed, decompressed_size));
      }
      manager->decompress(decompressed, compressed, decomp_config);
      CHECK_CUDA(cudaDeviceSynchronize());
    }

    CHECK_CUDA(cudaEventRecord(stop));
    CHECK_CUDA(cudaEventSynchronize(stop));
    float ms = 0.0f;
    CHECK_CUDA(cudaEventElapsedTime(&ms, start, stop));

    CHECK_CUDA(cudaMemset(mismatch_device, 0, sizeof(unsigned long long)));
    count_mismatches<<<blocks, threads>>>(input, decompressed, bytes,
                                          mismatch_device);
    CHECK_CUDA(cudaGetLastError());
    unsigned long long mismatches = 0;
    CHECK_CUDA(cudaMemcpy(&mismatches, mismatch_device,
                          sizeof(unsigned long long), cudaMemcpyDeviceToHost));

    double ratio = static_cast<double>(compressed_size) /
                   static_cast<double>(bytes);
    double gib_processed = static_cast<double>(bytes) *
                           static_cast<double>(iters) * 2.0 /
                           static_cast<double>(1ull << 30);
    double seconds = static_cast<double>(ms) / 1000.0;
    double gib_per_s = gib_processed / seconds;

    std::printf(
        "nvcomp_codec codec=%s bytes=%zu chunk_size=%zu iters=%d "
        "compressed=%zu ratio=%.6f decomp_bytes=%zu mismatches=%llu "
        "elapsed_ms=%.3f gib_per_s=%.3f\n",
        codec.c_str(), bytes, chunk_size, iters, compressed_size, ratio,
        decompressed_size, mismatches, ms, gib_per_s);

    CHECK_CUDA(cudaEventDestroy(stop));
    CHECK_CUDA(cudaEventDestroy(start));
    CHECK_CUDA(cudaFree(mismatch_device));
    CHECK_CUDA(cudaFree(decompressed));
    CHECK_CUDA(cudaFree(compressed));
    CHECK_CUDA(cudaFree(input));
  } catch (const std::exception& e) {
    std::fprintf(stderr, "nvCOMP error: %s\n", e.what());
    return 1;
  }

  return 0;
}

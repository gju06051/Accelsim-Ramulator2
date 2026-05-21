NVCC ?= nvcc
CUDAHOSTCXX ?= /usr/bin/g++-11
CUDA_HOME ?= /usr/local/cuda-12.3
CUDA_ARCH ?= 75
NVCOMP_ROOT ?= $(CUDA_HOME)
NVCOMP_INCLUDE_DIR ?= $(NVCOMP_ROOT)/include
NVCOMP_LIB_DIR ?= $(NVCOMP_ROOT)/lib64
NVCOMP_LIB ?= $(firstword $(wildcard $(NVCOMP_LIB_DIR)/libnvcomp.so $(NVCOMP_LIB_DIR)/libnvcomp.so.* $(NVCOMP_LIB_DIR)/libnvcomp.a))
BIN_DIR := bin
SRC_DIR := src

NVCCFLAGS ?= -O3 -std=c++17 -lineinfo -ccbin $(CUDAHOSTCXX) \
	-gencode arch=compute_$(CUDA_ARCH),code=sm_$(CUDA_ARCH) \
	-gencode arch=compute_$(CUDA_ARCH),code=compute_$(CUDA_ARCH)
LDFLAGS ?=
NVCOMP_CPPFLAGS ?= -I$(NVCOMP_INCLUDE_DIR)
NVCOMP_LDFLAGS ?= -L$(NVCOMP_LIB_DIR) -l:$(notdir $(NVCOMP_LIB))

TARGETS := \
	$(BIN_DIR)/fft_stockham \
	$(BIN_DIR)/finance_monte_carlo \
	$(BIN_DIR)/sha256_batch \
	$(BIN_DIR)/smith_waterman

.PHONY: all clean smoke
.PHONY: nvcomp nvcomp-smoke nvcomp-check
.PHONY: tango-fetch tango tango-smoke tango-clean

all: $(TARGETS)

$(BIN_DIR):
	mkdir -p $@

$(BIN_DIR)/%: $(SRC_DIR)/%.cu | $(BIN_DIR)
	$(NVCC) $(NVCCFLAGS) $< -o $@ $(LDFLAGS)

smoke: all
	$(BIN_DIR)/fft_stockham --points 1024 --batches 256 --iters 1
	$(BIN_DIR)/finance_monte_carlo --paths 262144 --steps 32
	$(BIN_DIR)/sha256_batch --messages 262144 --iters 1
	$(BIN_DIR)/smith_waterman --pairs 8192 --len 96

nvcomp-check:
	@if [ ! -f "$(NVCOMP_INCLUDE_DIR)/nvcomp.hpp" ]; then \
		echo "nvCOMP headers not found at $(NVCOMP_INCLUDE_DIR). Set NVCOMP_ROOT=/path/to/nvcomp or install nvCOMP."; \
		exit 2; \
	fi
	@if ! find "$(NVCOMP_LIB_DIR)" -maxdepth 1 \( -name 'libnvcomp*.so*' -o -name 'libnvcomp*.a' \) | grep -q .; then \
		echo "nvCOMP library not found at $(NVCOMP_LIB_DIR). Set NVCOMP_ROOT=/path/to/nvcomp or install nvCOMP."; \
		exit 2; \
	fi

nvcomp: nvcomp-check $(BIN_DIR)/nvcomp_codec_bench

$(BIN_DIR)/nvcomp_codec_bench: $(SRC_DIR)/nvcomp_codec_bench.cu | $(BIN_DIR)
	$(NVCC) $(NVCCFLAGS) $(NVCOMP_CPPFLAGS) $< -o $@ $(NVCOMP_LDFLAGS)

nvcomp-smoke: nvcomp
	$(BIN_DIR)/nvcomp_codec_bench --codec lz4 --bytes 8388608 --chunk-size 65536 --iters 1
	$(BIN_DIR)/nvcomp_codec_bench --codec snappy --bytes 8388608 --chunk-size 65536 --iters 1
	$(BIN_DIR)/nvcomp_codec_bench --codec gdeflate --bytes 8388608 --chunk-size 65536 --iters 1
	$(BIN_DIR)/nvcomp_codec_bench --codec deflate --bytes 8388608 --chunk-size 65536 --iters 1
	$(BIN_DIR)/nvcomp_codec_bench --codec zstd --bytes 8388608 --chunk-size 65536 --iters 1
	$(BIN_DIR)/nvcomp_codec_bench --codec cascaded --bytes 8388608 --chunk-size 65536 --iters 1
	$(BIN_DIR)/nvcomp_codec_bench --codec bitcomp --bytes 8388608 --chunk-size 65536 --iters 1
	$(BIN_DIR)/nvcomp_codec_bench --codec ans --bytes 8388608 --chunk-size 65536 --iters 1

tango-fetch:
	tango/fetch_tango.sh

tango: tango-fetch
	tango/build_tango.sh

tango-smoke: tango
	tango/run_tango.sh cifarnet 1
	tango/run_tango.sh gru
	tango/run_tango.sh lstm 1

tango-clean:
	rm -rf tango/upstream

clean:
	rm -rf $(BIN_DIR)

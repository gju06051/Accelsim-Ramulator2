#ifndef SGRAM_BACKEND_H
#define SGRAM_BACKEND_H

#include <deque>
#include <stdio.h>
#include <zlib.h>

#include "delayqueue.h"

class gpgpu_sim;
class mem_fetch;
class memory_config;
class memory_partition_unit;
class memory_stats_t;

class sgram_backend_t {
 public:
  static sgram_backend_t *create_if_enabled(unsigned partition_id,
                                            const memory_config *config,
                                            memory_stats_t *stats,
                                            memory_partition_unit *mp,
                                            gpgpu_sim *gpu);

  sgram_backend_t(unsigned partition_id, const memory_config *config,
                  memory_stats_t *stats, memory_partition_unit *mp,
                  gpgpu_sim *gpu);
  ~sgram_backend_t();

  bool full(bool is_write) const;
  void push(mem_fetch *data);
  void cycle();

  mem_fetch *return_queue_top();
  mem_fetch *return_queue_pop();
  bool returnq_full() const;
  unsigned que_length() const;

  void print(FILE *fp) const;
  void print_stat(FILE *fp);
  void visualize() const;
  void visualizer_print(gzFile visualizer_file) const;
  void set_dram_power_stats(unsigned &cmd, unsigned &activity, unsigned &nop,
                            unsigned &act, unsigned &pre, unsigned &rd,
                            unsigned &wr, unsigned &wr_WB,
                            unsigned &req) const;

 private:
  struct pending_req_t {
    unsigned long long ready_cycle;
    mem_fetch *req;
  };

  struct completed_req_t {
    unsigned long long ready_cycle;
    mem_fetch *req;
  };

  enum backend_kind_t {
    BACKEND_FIXED,
    BACKEND_RAMULATOR2,
  };

  unsigned long long now() const;
  static unsigned env_u32(const char *name, unsigned default_value);
  static const char *env_str(const char *name, const char *default_value);
  static void ramulator2_complete(void *user, void *payload,
                                  unsigned long long addr, int type,
                                  int source_id, long long arrive,
                                  long long depart);
  void complete(mem_fetch *data);
  bool send_ramulator2(mem_fetch *data);
  void tick_ramulator2_once();

  unsigned m_partition_id;
  const memory_config *m_config;
  memory_stats_t *m_stats;
  memory_partition_unit *m_memory_partition_unit;
  gpgpu_sim *m_gpu;

  backend_kind_t m_backend_kind;
  unsigned m_fixed_latency;
  unsigned m_queue_limit;
  unsigned m_ramulator2_extra_latency;
  fifo_pipeline<mem_fetch> *m_returnq;
  std::deque<pending_req_t> m_pending;
  std::deque<completed_req_t> m_completed;

  unsigned long long m_num_pushes;
  unsigned long long m_num_reads;
  unsigned long long m_num_writes;
  unsigned long long m_num_writebacks;
  unsigned long long m_num_returns;
  unsigned long long m_num_rejected;
  unsigned long long m_num_rejected_inflight;
  unsigned long long m_num_rejected_ramulator;
  mutable unsigned long long m_num_backend_full;
  unsigned long long m_num_ramulator2_accepted_reads;
  unsigned long long m_num_ramulator2_accepted_writes;
  unsigned long long m_num_ramulator2_completed_reads;
  unsigned long long m_num_ramulator2_immediate_writes;
};

#endif

#include "sgram_backend.h"

#include <assert.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>

#include "gpu-sim.h"
#include "l2cache.h"
#include "mem_fetch.h"
#include "mem_latency_stat.h"

namespace {

typedef void (*sgram_ramulator2_complete_cb)(
    void *user, void *payload, unsigned long long addr, int type,
    int source_id, long long arrive, long long depart);
typedef void *(*r2_create_fn)(const char *config_path);
typedef void (*r2_destroy_fn)(void *handle);
typedef int (*r2_send_fn)(void *handle, unsigned long long addr, int type,
                          int source_id, void *payload, void *user,
                          sgram_ramulator2_complete_cb callback);
typedef void (*r2_tick_fn)(void *handle);
typedef void (*r2_finalize_fn)(void *handle);
typedef double (*r2_tck_ns_fn)(void *handle);
typedef unsigned long long (*r2_ticks_fn)(void *handle);
typedef unsigned long long (*r2_counter_fn)(void *handle);
typedef double (*r2_double_fn)(void *handle);

struct ramulator2_api_t {
  r2_create_fn create;
  r2_destroy_fn destroy;
  r2_send_fn send;
  r2_tick_fn tick;
  r2_finalize_fn finalize;
  r2_tck_ns_fn tck_ns;
  r2_ticks_fn ticks;
  r2_counter_fn outstanding_reads;
  r2_counter_fn callback_untracked_writes;
  r2_counter_fn accepted_reads;
  r2_counter_fn completed_reads;
  r2_counter_fn accepted_writes;
  r2_counter_fn completed_writes;
  r2_counter_fn read_latency_samples;
  r2_counter_fn read_latency_sum;
  r2_counter_fn read_latency_max;
  r2_double_fn read_latency_avg;
  r2_counter_fn read_latency_p50;
  r2_counter_fn read_latency_p90;
  r2_counter_fn read_latency_p95;
  r2_counter_fn read_latency_p99;
};

void *g_ramulator2_dso = NULL;
void *g_ramulator2_handle = NULL;
ramulator2_api_t g_ramulator2_api = {};
unsigned g_ramulator2_refcount = 0;
bool g_ramulator2_atexit_registered = false;
unsigned g_ramulator2_inflight_reads = 0;
const unsigned kDefaultRamulator2InflightReadLimit = 5120;
unsigned g_ramulator2_inflight_read_limit = kDefaultRamulator2InflightReadLimit;
double g_ramulator2_ticks_per_dram_cycle = 1.0;
double g_ramulator2_tick_credit = 0.0;
double g_ramulator2_accelsim_dram_freq_mhz = -1.0;
double g_ramulator2_mhz = -1.0;
const char *g_ramulator2_tick_source = "manual";

unsigned env_u32_local(const char *name, unsigned default_value) {
  const char *value = getenv(name);
  if (!value || !value[0]) return default_value;
  char *end = NULL;
  unsigned long parsed = strtoul(value, &end, 0);
  if (end == value) return default_value;
  return static_cast<unsigned>(parsed);
}

double env_double_local(const char *name, double default_value) {
  const char *value = getenv(name);
  if (!value || !value[0]) return default_value;
  char *end = NULL;
  double parsed = strtod(value, &end);
  if (end == value || parsed <= 0.0) return default_value;
  return parsed;
}

bool env_is_auto(const char *value) {
  return !value || !value[0] || strcmp(value, "auto") == 0 ||
         strcmp(value, "AUTO") == 0 || strcmp(value, "Auto") == 0;
}

void *load_symbol(const char *name) {
  dlerror();
  void *symbol = dlsym(g_ramulator2_dso, name);
  const char *err = dlerror();
  if (err != NULL || symbol == NULL) {
    printf("failed to load Ramulator2 bridge symbol %s: %s\n", name,
           err ? err : "symbol is null");
    abort();
  }
  return symbol;
}

void load_ramulator2_api() {
  if (g_ramulator2_dso) return;

  const char *lib = getenv("SGRAM_RAMULATOR_LIB");
  if (!lib || !lib[0]) lib = "libsgram_ramulator2_bridge.so";

  g_ramulator2_dso = dlopen(lib, RTLD_NOW | RTLD_GLOBAL);
  if (!g_ramulator2_dso) {
    printf("failed to dlopen Ramulator2 bridge %s: %s\n", lib, dlerror());
    abort();
  }

  g_ramulator2_api.create =
      reinterpret_cast<r2_create_fn>(load_symbol("sgram_ramulator2_create"));
  g_ramulator2_api.destroy =
      reinterpret_cast<r2_destroy_fn>(load_symbol("sgram_ramulator2_destroy"));
  g_ramulator2_api.send =
      reinterpret_cast<r2_send_fn>(load_symbol("sgram_ramulator2_send"));
  g_ramulator2_api.tick =
      reinterpret_cast<r2_tick_fn>(load_symbol("sgram_ramulator2_tick"));
  g_ramulator2_api.finalize =
      reinterpret_cast<r2_finalize_fn>(load_symbol("sgram_ramulator2_finalize"));
  g_ramulator2_api.tck_ns =
      reinterpret_cast<r2_tck_ns_fn>(load_symbol("sgram_ramulator2_tck_ns"));
  g_ramulator2_api.ticks =
      reinterpret_cast<r2_ticks_fn>(load_symbol("sgram_ramulator2_ticks"));
  g_ramulator2_api.outstanding_reads = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_outstanding_reads"));
  g_ramulator2_api.callback_untracked_writes =
      reinterpret_cast<r2_counter_fn>(
          load_symbol("sgram_ramulator2_callback_untracked_writes"));
  g_ramulator2_api.accepted_reads = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_accepted_reads"));
  g_ramulator2_api.completed_reads = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_completed_reads"));
  g_ramulator2_api.accepted_writes = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_accepted_writes"));
  g_ramulator2_api.completed_writes = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_completed_writes"));
  g_ramulator2_api.read_latency_samples = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_read_latency_samples"));
  g_ramulator2_api.read_latency_sum = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_read_latency_sum"));
  g_ramulator2_api.read_latency_max = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_read_latency_max"));
  g_ramulator2_api.read_latency_avg = reinterpret_cast<r2_double_fn>(
      load_symbol("sgram_ramulator2_read_latency_avg"));
  g_ramulator2_api.read_latency_p50 = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_read_latency_p50"));
  g_ramulator2_api.read_latency_p90 = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_read_latency_p90"));
  g_ramulator2_api.read_latency_p95 = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_read_latency_p95"));
  g_ramulator2_api.read_latency_p99 = reinterpret_cast<r2_counter_fn>(
      load_symbol("sgram_ramulator2_read_latency_p99"));
}

void create_ramulator2_if_needed() {
  load_ramulator2_api();
  if (g_ramulator2_handle) {
    g_ramulator2_refcount++;
    return;
  }

  const char *config = getenv("SGRAM_RAMULATOR_CONFIG");
  if (!config || !config[0]) {
    printf("SGRAM_BACKEND=ramulator2 requires SGRAM_RAMULATOR_CONFIG\n");
    abort();
  }

  g_ramulator2_handle = g_ramulator2_api.create(config);
  if (!g_ramulator2_handle) {
    printf("failed to create Ramulator2 bridge using config %s\n", config);
    abort();
  }
  g_ramulator2_inflight_read_limit =
      env_u32_local("SGRAM_RAMULATOR_INFLIGHT_READ_LIMIT",
                    kDefaultRamulator2InflightReadLimit);
  const char *tick_env = getenv("SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE");
  double ramulator_tck_ns = g_ramulator2_api.tck_ns(g_ramulator2_handle);
  g_ramulator2_accelsim_dram_freq_mhz =
      env_double_local("SGRAM_ACCELSIM_DRAM_FREQ_MHZ", -1.0);
  g_ramulator2_mhz =
      ramulator_tck_ns > 0.0 ? 1000.0 / ramulator_tck_ns : -1.0;
  if (env_is_auto(tick_env)) {
    if (g_ramulator2_mhz > 0.0 && g_ramulator2_accelsim_dram_freq_mhz > 0.0) {
      g_ramulator2_ticks_per_dram_cycle =
          g_ramulator2_mhz / g_ramulator2_accelsim_dram_freq_mhz;
      g_ramulator2_tick_source = "auto";
    } else {
      g_ramulator2_ticks_per_dram_cycle = 1.0;
      g_ramulator2_tick_source = "auto_fallback";
    }
  } else {
    g_ramulator2_ticks_per_dram_cycle =
        env_double_local("SGRAM_RAMULATOR_TICKS_PER_DRAM_CYCLE", 1.0);
    g_ramulator2_tick_source = "manual";
  }
  g_ramulator2_tick_credit = 0.0;
  if (!g_ramulator2_atexit_registered) {
    atexit([]() {
      if (g_ramulator2_handle) g_ramulator2_api.finalize(g_ramulator2_handle);
    });
    g_ramulator2_atexit_registered = true;
  }
  g_ramulator2_refcount = 1;
  printf("SGRAM Ramulator2 bridge created: config=%s tCK=%.3f ns "
         "accelsim_dram_freq_mhz=%.3f ramulator_mhz=%.3f "
         "inflight_read_limit=%u ticks_per_dram_cycle=%.6f source=%s\n",
         config, ramulator_tck_ns, g_ramulator2_accelsim_dram_freq_mhz,
         g_ramulator2_mhz,
         g_ramulator2_inflight_read_limit,
         g_ramulator2_ticks_per_dram_cycle, g_ramulator2_tick_source);
}

void release_ramulator2() {
  if (!g_ramulator2_handle) return;
  assert(g_ramulator2_refcount > 0);
  g_ramulator2_refcount--;
  if (g_ramulator2_refcount != 0) return;

  g_ramulator2_api.destroy(g_ramulator2_handle);
  g_ramulator2_handle = NULL;
}

}  // namespace

sgram_backend_t *sgram_backend_t::create_if_enabled(
    unsigned partition_id, const memory_config *config, memory_stats_t *stats,
    memory_partition_unit *mp, gpgpu_sim *gpu) {
  const char *backend = getenv("SGRAM_BACKEND");
  if (!backend || !backend[0]) return NULL;
  if (strcmp(backend, "fixed") != 0 && strcmp(backend, "fixed_latency") != 0 &&
      strcmp(backend, "ramulator2") != 0) {
    printf("SGRAM_BACKEND=%s is not supported by the scaffolding backend\n",
           backend);
    abort();
  }
  return new sgram_backend_t(partition_id, config, stats, mp, gpu);
}

sgram_backend_t::sgram_backend_t(unsigned partition_id,
                                 const memory_config *config,
                                 memory_stats_t *stats,
                                 memory_partition_unit *mp, gpgpu_sim *gpu)
    : m_partition_id(partition_id),
      m_config(config),
      m_stats(stats),
      m_memory_partition_unit(mp),
      m_gpu(gpu),
      m_backend_kind(BACKEND_FIXED),
      m_fixed_latency(env_u32("SGRAM_FIXED_LATENCY", config->dram_latency)),
      m_queue_limit(env_u32("SGRAM_QUEUE_LIMIT",
                            config->gpgpu_frfcfs_dram_sched_queue_size)),
      m_ramulator2_extra_latency(
          env_u32("SGRAM_RAMULATOR_EXTRA_LATENCY", 0)),
      m_returnq(new fifo_pipeline<mem_fetch>(
          "sgram_returnq", 0,
          config->gpgpu_dram_return_queue_size == 0
              ? 1024
              : config->gpgpu_dram_return_queue_size)),
      m_num_pushes(0),
      m_num_reads(0),
      m_num_writes(0),
      m_num_writebacks(0),
      m_num_returns(0),
      m_num_rejected(0),
      m_num_rejected_inflight(0),
      m_num_rejected_ramulator(0),
      m_num_backend_full(0),
      m_num_ramulator2_accepted_reads(0),
      m_num_ramulator2_accepted_writes(0),
      m_num_ramulator2_completed_reads(0),
      m_num_ramulator2_immediate_writes(0) {
  const char *backend = getenv("SGRAM_BACKEND");
  if (backend && strcmp(backend, "ramulator2") == 0) {
    m_backend_kind = BACKEND_RAMULATOR2;
    create_ramulator2_if_needed();
    printf("SGRAM Ramulator2 backend enabled: partition=%u queue_limit=%u "
           "extra_latency=%u\n",
           m_partition_id, m_queue_limit, m_ramulator2_extra_latency);
  } else {
    printf("SGRAM fixed-latency backend enabled: partition=%u latency=%u "
           "queue_limit=%u\n",
           m_partition_id, m_fixed_latency, m_queue_limit);
  }
}

sgram_backend_t::~sgram_backend_t() {
  if (m_backend_kind == BACKEND_RAMULATOR2) release_ramulator2();
  delete m_returnq;
}

unsigned sgram_backend_t::env_u32(const char *name, unsigned default_value) {
  const char *value = getenv(name);
  if (!value || !value[0]) return default_value;
  char *end = NULL;
  unsigned long parsed = strtoul(value, &end, 0);
  if (end == value) return default_value;
  return static_cast<unsigned>(parsed);
}

const char *sgram_backend_t::env_str(const char *name,
                                     const char *default_value) {
  const char *value = getenv(name);
  if (!value || !value[0]) return default_value;
  return value;
}

unsigned long long sgram_backend_t::now() const {
  return m_gpu->gpu_sim_cycle + m_gpu->gpu_tot_sim_cycle;
}

bool sgram_backend_t::full(bool is_write) const {
  (void)is_write;
  if (m_queue_limit == 0) return false;
  if (m_backend_kind == BACKEND_RAMULATOR2) {
    bool is_full = (m_pending.size() + m_completed.size()) >= m_queue_limit;
    if (is_full) m_num_backend_full++;
    return is_full;
  }
  bool is_full = m_pending.size() >= m_queue_limit;
  if (is_full) m_num_backend_full++;
  return is_full;
}

void sgram_backend_t::push(mem_fetch *data) {
  data->set_status(IN_PARTITION_MC_INTERFACE_QUEUE, now());
  m_stats->memlatstat_dram_access(data);
  unsigned long long ready_cycle =
      m_backend_kind == BACKEND_FIXED ? now() + m_fixed_latency : 0;
  m_pending.push_back({ready_cycle, data});
  m_num_pushes++;
  if (data->get_access_type() == L1_WRBK_ACC ||
      data->get_access_type() == L2_WRBK_ACC) {
    m_num_writebacks++;
  } else if (data->get_is_write()) {
    m_num_writes++;
  } else {
    m_num_reads++;
  }
}

void sgram_backend_t::ramulator2_complete(void *user, void *payload,
                                          unsigned long long addr, int type,
                                          int source_id, long long arrive,
                                          long long depart) {
  (void)addr;
  (void)source_id;
  (void)arrive;
  (void)depart;
  sgram_backend_t *backend = static_cast<sgram_backend_t *>(user);
  if (type != 0) return;
  mem_fetch *data = static_cast<mem_fetch *>(payload);
  if (g_ramulator2_inflight_reads > 0) g_ramulator2_inflight_reads--;
  backend->m_completed.push_back(
      {backend->now() + backend->m_ramulator2_extra_latency, data});
  backend->m_num_ramulator2_completed_reads++;
}

void sgram_backend_t::complete(mem_fetch *data) {
  data->set_status(IN_PARTITION_MC_RETURNQ, now());

  if (data->get_access_type() != L1_WRBK_ACC &&
      data->get_access_type() != L2_WRBK_ACC) {
    data->set_reply();
    m_returnq->push(data);
    m_num_returns++;
  } else {
    m_memory_partition_unit->set_done(data);
    delete data;
  }
}

bool sgram_backend_t::send_ramulator2(mem_fetch *data) {
  assert(g_ramulator2_handle != NULL);
  int type = data->get_is_write() ? 1 : 0;
  int source_id = static_cast<int>(m_partition_id);
  if (type == 0 && g_ramulator2_inflight_read_limit != 0 &&
      g_ramulator2_inflight_reads >= g_ramulator2_inflight_read_limit) {
    m_num_rejected++;
    m_num_rejected_inflight++;
    return false;
  }
  int accepted =
      g_ramulator2_api.send(g_ramulator2_handle, data->get_addr(), type,
                            source_id, data, this, ramulator2_complete);
  if (!accepted) {
    m_num_rejected++;
    m_num_rejected_ramulator++;
    return false;
  }

  if (type == 0) {
    g_ramulator2_inflight_reads++;
    m_num_ramulator2_accepted_reads++;
  } else {
    m_num_ramulator2_accepted_writes++;
    m_num_ramulator2_immediate_writes++;
    m_completed.push_back({now() + m_ramulator2_extra_latency, data});
  }
  return true;
}

void sgram_backend_t::tick_ramulator2_once() {
  if (m_backend_kind != BACKEND_RAMULATOR2) return;
  if (m_partition_id != 0) return;
  g_ramulator2_tick_credit += g_ramulator2_ticks_per_dram_cycle;
  unsigned ticks_to_issue = static_cast<unsigned>(g_ramulator2_tick_credit);
  g_ramulator2_tick_credit -= ticks_to_issue;
  for (unsigned i = 0; i < ticks_to_issue; i++) {
    g_ramulator2_api.tick(g_ramulator2_handle);
  }
}

void sgram_backend_t::cycle() {
  if (m_backend_kind == BACKEND_RAMULATOR2) {
    tick_ramulator2_once();

    while (!m_completed.empty() && !m_returnq->full() &&
           m_completed.front().ready_cycle <= now()) {
      mem_fetch *data = m_completed.front().req;
      m_completed.pop_front();
      complete(data);
    }

    if (!m_pending.empty()) {
      mem_fetch *data = m_pending.front().req;
      if (send_ramulator2(data)) m_pending.pop_front();
    }
    return;
  }

  if (m_pending.empty() || m_returnq->full()) return;
  if (m_pending.front().ready_cycle > now()) return;

  mem_fetch *data = m_pending.front().req;
  m_pending.pop_front();
  complete(data);
}

mem_fetch *sgram_backend_t::return_queue_top() { return m_returnq->top(); }

mem_fetch *sgram_backend_t::return_queue_pop() { return m_returnq->pop(); }

bool sgram_backend_t::returnq_full() const { return m_returnq->full(); }

unsigned sgram_backend_t::que_length() const {
  return static_cast<unsigned>(m_pending.size());
}

void sgram_backend_t::print(FILE *fp) const {
  if (m_backend_kind == BACKEND_RAMULATOR2) {
    unsigned long long ticks =
        g_ramulator2_handle ? g_ramulator2_api.ticks(g_ramulator2_handle) : 0;
    unsigned long long global_outstanding_reads =
        g_ramulator2_handle
            ? g_ramulator2_api.outstanding_reads(g_ramulator2_handle)
            : 0;
    unsigned long long global_callback_untracked_writes =
        g_ramulator2_handle
            ? g_ramulator2_api.callback_untracked_writes(g_ramulator2_handle)
            : 0;
    unsigned long long global_accepted_reads =
        g_ramulator2_handle
            ? g_ramulator2_api.accepted_reads(g_ramulator2_handle)
            : 0;
    unsigned long long global_completed_reads =
        g_ramulator2_handle
            ? g_ramulator2_api.completed_reads(g_ramulator2_handle)
            : 0;
    unsigned long long global_accepted_writes =
        g_ramulator2_handle
            ? g_ramulator2_api.accepted_writes(g_ramulator2_handle)
            : 0;
    unsigned long long global_completed_writes =
        g_ramulator2_handle
            ? g_ramulator2_api.completed_writes(g_ramulator2_handle)
            : 0;
    unsigned long long global_read_latency_samples =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_samples(g_ramulator2_handle)
            : 0;
    unsigned long long global_read_latency_sum =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_sum(g_ramulator2_handle)
            : 0;
    unsigned long long global_read_latency_max =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_max(g_ramulator2_handle)
            : 0;
    double global_read_latency_avg =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_avg(g_ramulator2_handle)
            : 0.0;
    unsigned long long global_read_latency_p50 =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_p50(g_ramulator2_handle)
            : 0;
    unsigned long long global_read_latency_p90 =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_p90(g_ramulator2_handle)
            : 0;
    unsigned long long global_read_latency_p95 =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_p95(g_ramulator2_handle)
            : 0;
    unsigned long long global_read_latency_p99 =
        g_ramulator2_handle
            ? g_ramulator2_api.read_latency_p99(g_ramulator2_handle)
            : 0;
    fprintf(fp,
            "SGRAM Ramulator2 backend partition %u: pending=%zu completed=%zu "
            "returnq_full=%u queue_limit=%u bridge_ticks=%llu "
            "ticks_per_dram_cycle=%.6f "
            "accepted_reads=%llu completed_reads=%llu accepted_writes=%llu "
            "rejected=%llu rejected_inflight=%llu rejected_ramulator=%llu "
            "backend_full=%llu global_inflight_reads=%u inflight_limit=%u "
            "global_outstanding_reads=%llu "
            "global_callback_untracked_writes=%llu "
            "global_accepted_reads=%llu global_completed_reads=%llu "
            "global_accepted_writes=%llu global_completed_writes=%llu "
            "global_read_latency_samples=%llu "
            "global_read_latency_sum=%llu global_read_latency_avg=%.6f "
            "global_read_latency_p50=%llu global_read_latency_p90=%llu "
            "global_read_latency_p95=%llu global_read_latency_p99=%llu "
            "global_read_latency_max=%llu\n",
            m_partition_id, m_pending.size(), m_completed.size(),
            m_returnq->full() ? 1 : 0, m_queue_limit, ticks,
            g_ramulator2_ticks_per_dram_cycle,
            m_num_ramulator2_accepted_reads,
            m_num_ramulator2_completed_reads,
            m_num_ramulator2_accepted_writes, m_num_rejected,
            m_num_rejected_inflight, m_num_rejected_ramulator,
            m_num_backend_full, g_ramulator2_inflight_reads,
            g_ramulator2_inflight_read_limit, global_outstanding_reads,
            global_callback_untracked_writes, global_accepted_reads,
            global_completed_reads, global_accepted_writes,
            global_completed_writes, global_read_latency_samples,
            global_read_latency_sum, global_read_latency_avg,
            global_read_latency_p50, global_read_latency_p90,
            global_read_latency_p95, global_read_latency_p99,
            global_read_latency_max);
  } else {
    fprintf(fp,
            "SGRAM fixed backend partition %u: pending=%zu returnq_full=%u "
            "latency=%u queue_limit=%u\n",
            m_partition_id, m_pending.size(), m_returnq->full() ? 1 : 0,
            m_fixed_latency, m_queue_limit);
  }
}

void sgram_backend_t::print_stat(FILE *fp) {
  const char *prefix =
      m_backend_kind == BACKEND_RAMULATOR2 ? "sgram_ramulator2_backend"
                                           : "sgram_fixed_backend";
  fprintf(fp, "%s[%u]_pushes = %llu\n", prefix, m_partition_id, m_num_pushes);
  fprintf(fp, "%s[%u]_reads = %llu\n", prefix, m_partition_id, m_num_reads);
  fprintf(fp, "%s[%u]_writes = %llu\n", prefix, m_partition_id, m_num_writes);
  fprintf(fp, "%s[%u]_writebacks = %llu\n", prefix, m_partition_id,
          m_num_writebacks);
  fprintf(fp, "%s[%u]_returns = %llu\n", prefix, m_partition_id,
          m_num_returns);
  fprintf(fp, "%s[%u]_rejected = %llu\n", prefix, m_partition_id,
          m_num_rejected);
  fprintf(fp, "%s[%u]_rejected_inflight = %llu\n", prefix, m_partition_id,
          m_num_rejected_inflight);
  fprintf(fp, "%s[%u]_rejected_ramulator = %llu\n", prefix, m_partition_id,
          m_num_rejected_ramulator);
  fprintf(fp, "%s[%u]_backend_full = %llu\n", prefix, m_partition_id,
          m_num_backend_full);
  if (m_backend_kind == BACKEND_RAMULATOR2) {
    fprintf(fp, "%s[%u]_accepted_reads = %llu\n", prefix, m_partition_id,
            m_num_ramulator2_accepted_reads);
    fprintf(fp, "%s[%u]_accepted_writes = %llu\n", prefix, m_partition_id,
            m_num_ramulator2_accepted_writes);
    fprintf(fp, "%s[%u]_completed_reads = %llu\n", prefix, m_partition_id,
            m_num_ramulator2_completed_reads);
    fprintf(fp, "%s[%u]_immediate_writes = %llu\n", prefix, m_partition_id,
            m_num_ramulator2_immediate_writes);
  }
}

void sgram_backend_t::visualize() const {}

void sgram_backend_t::visualizer_print(gzFile visualizer_file) const {
  (void)visualizer_file;
}

void sgram_backend_t::set_dram_power_stats(
    unsigned &cmd, unsigned &activity, unsigned &nop, unsigned &act,
    unsigned &pre, unsigned &rd, unsigned &wr, unsigned &wr_WB,
    unsigned &req) const {
  cmd = 0;
  activity = 0;
  nop = 0;
  act = 0;
  pre = 0;
  rd = static_cast<unsigned>(m_num_reads);
  wr = static_cast<unsigned>(m_num_writes);
  wr_WB = static_cast<unsigned>(m_num_writebacks);
  req = static_cast<unsigned>(m_num_pushes);
}

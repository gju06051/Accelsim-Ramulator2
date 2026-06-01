#include "ramulator2_c_api.h"

#include <exception>
#include <iostream>
#include <memory>
#include <vector>

#include "base/config.h"
#include "base/factory.h"
#include "base/request.h"
#include "frontend/frontend.h"
#include "memory_system/memory_system.h"

namespace {

constexpr unsigned long long kReadLatencyHistMax = 65535;

struct sgram_ramulator2_system {
  Ramulator::IFrontEnd *frontend = nullptr;
  Ramulator::IMemorySystem *memory_system = nullptr;
  bool finalized = false;
  unsigned long long accepted_reads = 0;
  unsigned long long completed_reads = 0;
  unsigned long long outstanding_reads = 0;
  unsigned long long accepted_writes = 0;
  unsigned long long completed_writes = 0;
  unsigned long long callback_untracked_writes = 0;
  unsigned long long ticks = 0;
  unsigned long long read_latency_samples = 0;
  unsigned long long read_latency_sum = 0;
  unsigned long long read_latency_max = 0;
  std::vector<unsigned long long> read_latency_hist =
      std::vector<unsigned long long>(kReadLatencyHistMax + 1, 0);
};

void print_exception(const char *where, const std::exception &e) {
  std::cerr << "sgram_ramulator2_" << where << ": " << e.what() << std::endl;
}

void record_read_latency(sgram_ramulator2_system *system,
                         const Ramulator::Request &completed) {
  if (!system || completed.depart < completed.arrive) return;
  unsigned long long latency =
      static_cast<unsigned long long>(completed.depart - completed.arrive);
  system->read_latency_samples++;
  system->read_latency_sum += latency;
  if (latency > system->read_latency_max) system->read_latency_max = latency;
  unsigned long long bin =
      latency > kReadLatencyHistMax ? kReadLatencyHistMax : latency;
  system->read_latency_hist[bin]++;
}

unsigned long long read_latency_percentile(sgram_ramulator2_system *system,
                                           double percentile) {
  if (!system || system->read_latency_samples == 0) return 0;
  if (percentile <= 0.0) percentile = 0.0;
  if (percentile >= 1.0) percentile = 1.0;
  unsigned long long target = static_cast<unsigned long long>(
      percentile * static_cast<double>(system->read_latency_samples - 1));
  target += 1;
  unsigned long long cumulative = 0;
  for (size_t latency = 0; latency < system->read_latency_hist.size();
       ++latency) {
    cumulative += system->read_latency_hist[latency];
    if (cumulative >= target) return static_cast<unsigned long long>(latency);
  }
  return system->read_latency_max;
}

}  // namespace

extern "C" void *sgram_ramulator2_create(const char *config_path) {
  try {
    if (!config_path || !config_path[0]) {
      std::cerr << "sgram_ramulator2_create: config_path is empty"
                << std::endl;
      return nullptr;
    }

    YAML::Node config = Ramulator::Config::parse_config_file(config_path, {});
    auto *system = new sgram_ramulator2_system();
    system->frontend = Ramulator::Factory::create_frontend(config);
    system->memory_system = Ramulator::Factory::create_memory_system(config);
    system->frontend->connect_memory_system(system->memory_system);
    system->memory_system->connect_frontend(system->frontend);
    return system;
  } catch (const std::exception &e) {
    print_exception("create", e);
    return nullptr;
  }
}

extern "C" void sgram_ramulator2_destroy(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  if (!system) return;
  sgram_ramulator2_finalize(handle);
  if (system->outstanding_reads != 0) {
    std::cerr << "sgram_ramulator2_destroy: leaving Ramulator2 objects alive "
              << "because " << system->outstanding_reads
              << " read callbacks are still outstanding" << std::endl;
    delete system;
    return;
  }
  delete system->memory_system;
  delete system->frontend;
  delete system;
}

extern "C" int sgram_ramulator2_send(
    void *handle, unsigned long long addr, int type, int source_id,
    void *payload, void *user, sgram_ramulator2_complete_cb callback) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  if (!system || !system->memory_system) return 0;

  bool counted = false;
  bool is_read = type == Ramulator::Request::Type::Read;
  bool is_write = type == Ramulator::Request::Type::Write;
  try {
    Ramulator::Request req(
        static_cast<Ramulator::Addr_t>(addr), type, source_id,
        [system, payload, user, callback](Ramulator::Request &completed) {
          if (completed.type_id == Ramulator::Request::Type::Read) {
            if (system->outstanding_reads > 0) system->outstanding_reads--;
            system->completed_reads++;
            record_read_latency(system, completed);
          } else if (completed.type_id == Ramulator::Request::Type::Write) {
            if (system->callback_untracked_writes > 0)
              system->callback_untracked_writes--;
            system->completed_writes++;
          }
          if (callback) {
            callback(user, payload,
                     static_cast<unsigned long long>(completed.addr),
                     completed.type_id, completed.source_id,
                     static_cast<long long>(completed.arrive),
                     static_cast<long long>(completed.depart));
          }
        });
    req.m_payload = payload;
    if (is_read) {
      system->outstanding_reads++;
    } else if (is_write) {
      system->callback_untracked_writes++;
    }
    counted = true;
    if (system->memory_system->send(req)) {
      if (is_read) {
        system->accepted_reads++;
      } else if (is_write) {
        system->accepted_writes++;
      }
      return 1;
    }
    if (is_read && system->outstanding_reads > 0) {
      system->outstanding_reads--;
    } else if (is_write && system->callback_untracked_writes > 0) {
      system->callback_untracked_writes--;
    }
    return 0;
  } catch (const std::exception &e) {
    if (counted && is_read && system->outstanding_reads > 0) {
      system->outstanding_reads--;
    } else if (counted && is_write &&
               system->callback_untracked_writes > 0) {
      system->callback_untracked_writes--;
    }
    print_exception("send", e);
    return 0;
  }
}

extern "C" void sgram_ramulator2_tick(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  if (!system || !system->memory_system) return;

  try {
    system->memory_system->tick();
    system->ticks++;
  } catch (const std::exception &e) {
    print_exception("tick", e);
  }
}

extern "C" void sgram_ramulator2_finalize(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  if (!system || system->finalized) return;

  try {
    const char *skip_stats = std::getenv("SGRAM_RAMULATOR_SKIP_FINALIZE_STATS");
    if (skip_stats && skip_stats[0] &&
        !(skip_stats[0] == '0' && skip_stats[1] == '\0')) {
      std::cerr << "sgram_ramulator2_finalize: skipping Ramulator2 stats "
                << "because SGRAM_RAMULATOR_SKIP_FINALIZE_STATS is set"
                << std::endl;
      system->finalized = true;
      return;
    }
    if (system->outstanding_reads != 0 ||
        system->callback_untracked_writes != 0) {
      std::cerr << "sgram_ramulator2_finalize: emitting Ramulator2 stats with "
                << "outstanding_reads=" << system->outstanding_reads
                << " callback_untracked_writes="
                << system->callback_untracked_writes
                << " accepted_reads=" << system->accepted_reads
                << " completed_reads=" << system->completed_reads
                << " accepted_writes=" << system->accepted_writes
                << " completed_writes=" << system->completed_writes
                << std::endl;
    }
    if (system->frontend) system->frontend->finalize();
    if (system->memory_system) system->memory_system->finalize();
  } catch (const std::exception &e) {
    print_exception("finalize", e);
  }
  system->finalized = true;
}

extern "C" double sgram_ramulator2_tck_ns(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  if (!system || !system->memory_system) return -1.0;

  try {
    return static_cast<double>(system->memory_system->get_tCK());
  } catch (const std::exception &e) {
    print_exception("tck_ns", e);
    return -1.0;
  }
}

extern "C" unsigned long long sgram_ramulator2_ticks(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->ticks : 0;
}

extern "C" unsigned long long sgram_ramulator2_outstanding_reads(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->outstanding_reads : 0;
}

extern "C" unsigned long long
sgram_ramulator2_callback_untracked_writes(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->callback_untracked_writes : 0;
}

extern "C" unsigned long long sgram_ramulator2_accepted_reads(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->accepted_reads : 0;
}

extern "C" unsigned long long sgram_ramulator2_completed_reads(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->completed_reads : 0;
}

extern "C" unsigned long long sgram_ramulator2_accepted_writes(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->accepted_writes : 0;
}

extern "C" unsigned long long sgram_ramulator2_completed_writes(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->completed_writes : 0;
}

extern "C" unsigned long long
sgram_ramulator2_read_latency_samples(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->read_latency_samples : 0;
}

extern "C" unsigned long long sgram_ramulator2_read_latency_sum(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->read_latency_sum : 0;
}

extern "C" unsigned long long sgram_ramulator2_read_latency_max(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return system ? system->read_latency_max : 0;
}

extern "C" double sgram_ramulator2_read_latency_avg(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  if (!system || system->read_latency_samples == 0) return 0.0;
  return static_cast<double>(system->read_latency_sum) /
         static_cast<double>(system->read_latency_samples);
}

extern "C" unsigned long long sgram_ramulator2_read_latency_p50(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return read_latency_percentile(system, 0.50);
}

extern "C" unsigned long long sgram_ramulator2_read_latency_p90(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return read_latency_percentile(system, 0.90);
}

extern "C" unsigned long long sgram_ramulator2_read_latency_p95(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return read_latency_percentile(system, 0.95);
}

extern "C" unsigned long long sgram_ramulator2_read_latency_p99(void *handle) {
  auto *system = static_cast<sgram_ramulator2_system *>(handle);
  return read_latency_percentile(system, 0.99);
}

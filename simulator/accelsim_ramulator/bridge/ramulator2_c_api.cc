#include "ramulator2_c_api.h"

#include <exception>
#include <iostream>
#include <memory>

#include "base/config.h"
#include "base/factory.h"
#include "base/request.h"
#include "frontend/frontend.h"
#include "memory_system/memory_system.h"

namespace {

struct sgram_ramulator2_system {
  Ramulator::IFrontEnd *frontend = nullptr;
  Ramulator::IMemorySystem *memory_system = nullptr;
  bool finalized = false;
  unsigned long long outstanding = 0;
  unsigned long long ticks = 0;
};

void print_exception(const char *where, const std::exception &e) {
  std::cerr << "sgram_ramulator2_" << where << ": " << e.what() << std::endl;
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
  if (system->outstanding != 0) {
    std::cerr << "sgram_ramulator2_destroy: leaving Ramulator2 objects alive "
              << "because " << system->outstanding
              << " requests are still outstanding" << std::endl;
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
  try {
    Ramulator::Request req(
        static_cast<Ramulator::Addr_t>(addr), type, source_id,
        [system, payload, user, callback](Ramulator::Request &completed) {
          if (system->outstanding > 0) system->outstanding--;
          if (callback) {
            callback(user, payload,
                     static_cast<unsigned long long>(completed.addr),
                     completed.type_id, completed.source_id,
                     static_cast<long long>(completed.arrive),
                     static_cast<long long>(completed.depart));
          }
        });
    req.m_payload = payload;
    system->outstanding++;
    counted = true;
    if (system->memory_system->send(req)) return 1;
    system->outstanding--;
    return 0;
  } catch (const std::exception &e) {
    if (counted && system->outstanding > 0) system->outstanding--;
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
    if (system->outstanding != 0) {
      std::cerr << "sgram_ramulator2_finalize: emitting Ramulator2 stats with "
                << system->outstanding << " requests still outstanding"
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

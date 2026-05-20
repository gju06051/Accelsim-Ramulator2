#include "ramulator2_c_api.h"

#include <cstdlib>
#include <iostream>

namespace {

struct smoke_state {
  unsigned completed = 0;
};

void on_complete(void *user, void *payload, unsigned long long addr, int type,
                 int source_id, long long arrive, long long depart) {
  auto *state = static_cast<smoke_state *>(user);
  state->completed++;
  std::cout << "complete payload=" << payload << " addr=0x" << std::hex
            << addr << std::dec << " type=" << type
            << " source_id=" << source_id << " arrive=" << arrive
            << " depart=" << depart << std::endl;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr << "usage: " << argv[0] << " <ramulator2-yaml>" << std::endl;
    return 2;
  }

  void *handle = sgram_ramulator2_create(argv[1]);
  if (!handle) return 1;

  smoke_state state;
  const unsigned long long base = 0x100000;
  for (unsigned i = 0; i < 8; i++) {
    int ok = sgram_ramulator2_send(handle, base + i * 64, 0, i,
                                   reinterpret_cast<void *>(0x1000 + i),
                                   &state, on_complete);
    if (!ok) {
      std::cerr << "request " << i << " was rejected" << std::endl;
      sgram_ramulator2_destroy(handle);
      return 1;
    }
  }

  for (unsigned i = 0; i < 5000 && state.completed < 8; i++) {
    sgram_ramulator2_tick(handle);
  }

  std::cout << "completed=" << state.completed
            << " ticks=" << sgram_ramulator2_ticks(handle)
            << " tck_ns=" << sgram_ramulator2_tck_ns(handle) << std::endl;

  sgram_ramulator2_destroy(handle);
  return state.completed == 8 ? 0 : 1;
}

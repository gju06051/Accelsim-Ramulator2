#include "ramulator2_c_api.h"

#include <cstdlib>
#include <iostream>

namespace {

struct smoke_state {
  unsigned read_completed = 0;
  unsigned write_completed = 0;
};

void on_complete(void *user, void *payload, unsigned long long addr, int type,
                 int source_id, long long arrive, long long depart) {
  auto *state = static_cast<smoke_state *>(user);
  if (type == 0) {
    state->read_completed++;
  } else if (type == 1) {
    state->write_completed++;
  }
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
  const unsigned num_reads = 4;
  const unsigned num_writes = 4;
  for (unsigned i = 0; i < num_reads; i++) {
    int ok = sgram_ramulator2_send(handle, base + i * 64, 0, i,
                                   reinterpret_cast<void *>(0x1000 + i),
                                   &state, on_complete);
    if (!ok) {
      std::cerr << "request " << i << " was rejected" << std::endl;
      sgram_ramulator2_destroy(handle);
      return 1;
    }
  }
  for (unsigned i = 0; i < num_writes; i++) {
    int ok = sgram_ramulator2_send(handle, base + (num_reads + i) * 64, 1,
                                   num_reads + i,
                                   reinterpret_cast<void *>(0x2000 + i),
                                   &state, on_complete);
    if (!ok) {
      std::cerr << "write request " << i << " was rejected" << std::endl;
      sgram_ramulator2_destroy(handle);
      return 1;
    }
  }

  for (unsigned i = 0; i < 5000 &&
                       sgram_ramulator2_completed_reads(handle) < num_reads;
       i++) {
    sgram_ramulator2_tick(handle);
  }

  unsigned long long accepted_reads = sgram_ramulator2_accepted_reads(handle);
  unsigned long long completed_reads = sgram_ramulator2_completed_reads(handle);
  unsigned long long outstanding_reads =
      sgram_ramulator2_outstanding_reads(handle);
  unsigned long long accepted_writes = sgram_ramulator2_accepted_writes(handle);
  unsigned long long completed_writes =
      sgram_ramulator2_completed_writes(handle);
  unsigned long long callback_untracked_writes =
      sgram_ramulator2_callback_untracked_writes(handle);

  std::cout << "read_callbacks=" << state.read_completed
            << " write_callbacks=" << state.write_completed
            << " accepted_reads=" << accepted_reads
            << " completed_reads=" << completed_reads
            << " outstanding_reads=" << outstanding_reads
            << " accepted_writes=" << accepted_writes
            << " completed_writes=" << completed_writes
            << " callback_untracked_writes=" << callback_untracked_writes
            << " ticks=" << sgram_ramulator2_ticks(handle)
            << " tck_ns=" << sgram_ramulator2_tck_ns(handle) << std::endl;

  sgram_ramulator2_destroy(handle);
  bool reads_ok = accepted_reads == num_reads && completed_reads == num_reads &&
                  outstanding_reads == 0;
  bool writes_ok =
      accepted_writes == num_writes &&
      completed_writes + callback_untracked_writes == num_writes;
  return reads_ok && writes_ok ? 0 : 1;
}

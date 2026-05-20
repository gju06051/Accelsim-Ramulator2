#include <filesystem>
#include <fstream>
#include <map>

#include "base/base.h"
#include "dram_controller/controller.h"
#include "dram_controller/plugin.h"

namespace Ramulator {

class SIDMaskCounter : public IControllerPlugin, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IControllerPlugin, SIDMaskCounter, "SIDMaskCounter", "Counting SID_valid_mask demand on completed memory accesses.")

  private:
    IDRAM* m_dram = nullptr;

    int m_num_slices = 4;
    int m_slice_bytes = 8;
    int m_full_mask = 0xf;

    size_t m_total_accesses = 0;
    size_t m_total_required_bytes = 0;
    size_t m_read_accesses = 0;
    size_t m_read_required_bytes = 0;
    size_t m_write_accesses = 0;
    size_t m_write_required_bytes = 0;
    size_t m_noncontiguous_masks = 0;
    std::map<int, size_t> m_mask_counts;
    std::map<int, size_t> m_mask_read_counts;
    std::map<int, size_t> m_mask_write_counts;

    std::filesystem::path m_save_path;

    static int popcount(int value) {
      int count = 0;
      while (value != 0) {
        count += value & 1;
        value >>= 1;
      }
      return count;
    }

    static bool is_contiguous_mask(int mask) {
      if (mask == 0) {
        return false;
      }
      while ((mask & 1) == 0) {
        mask >>= 1;
      }
      return (mask & (mask + 1)) == 0;
    }

  public:
    void init() override {
      m_num_slices = param<int>("num_slices").desc("Number of SID slices in one access atom.").default_val(4);
      m_slice_bytes = param<int>("slice_bytes").desc("Bytes covered by each SID slice.").default_val(8);
      m_save_path = param<std::string>("path").desc("Path to the SID mask counter CSV.").required();

      if (m_num_slices <= 0 || m_num_slices > 30) {
        throw ConfigurationError("SIDMaskCounter num_slices={} is invalid.", m_num_slices);
      }
      if (m_slice_bytes <= 0) {
        throw ConfigurationError("SIDMaskCounter slice_bytes={} is invalid.", m_slice_bytes);
      }
      m_full_mask = (1 << m_num_slices) - 1;

      auto parent_path = m_save_path.parent_path();
      std::filesystem::create_directories(parent_path);
      if (!(std::filesystem::exists(parent_path) && std::filesystem::is_directory(parent_path))) {
        throw ConfigurationError("Invalid path to SID mask counter file: {}", parent_path.string());
      }
    };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      m_ctrl = cast_parent<IDRAMController>();
      m_dram = m_ctrl->m_dram;
    };

    void update(bool request_found, ReqBuffer::iterator& req_it) override {
      if (!request_found) {
        return;
      }
      if (req_it->command != req_it->final_command) {
        return;
      }
      if (!m_dram->m_command_meta(req_it->command).is_accessing) {
        return;
      }

      int mask = req_it->scratchpad[0];
      if (mask == 0) {
        mask = m_full_mask;
      }
      mask &= m_full_mask;

      size_t required_bytes = size_t(popcount(mask)) * size_t(m_slice_bytes);
      m_mask_counts[mask]++;
      m_total_accesses++;
      m_total_required_bytes += required_bytes;
      if (req_it->type_id == Request::Type::Read) {
        m_mask_read_counts[mask]++;
        m_read_accesses++;
        m_read_required_bytes += required_bytes;
      } else if (req_it->type_id == Request::Type::Write) {
        m_mask_write_counts[mask]++;
        m_write_accesses++;
        m_write_required_bytes += required_bytes;
      }
      if (!is_contiguous_mask(mask)) {
        m_noncontiguous_masks++;
      }
    };

    void finalize() override {
      std::ofstream output(m_save_path);
      output << "mask,count,required_bytes,read_count,read_required_bytes,write_count,write_required_bytes\n";
      for (const auto& [mask, count] : m_mask_counts) {
        size_t read_count = m_mask_read_counts[mask];
        size_t write_count = m_mask_write_counts[mask];
        output << fmt::format(
            "0x{:x},{},{},{},{},{},{}\n",
            mask,
            count,
            count * size_t(popcount(mask)) * size_t(m_slice_bytes),
            read_count,
            read_count * size_t(popcount(mask)) * size_t(m_slice_bytes),
            write_count,
            write_count * size_t(popcount(mask)) * size_t(m_slice_bytes)
        );
      }
      output << fmt::format(
          "total,{},{},{},{},{},{}\n",
          m_total_accesses,
          m_total_required_bytes,
          m_read_accesses,
          m_read_required_bytes,
          m_write_accesses,
          m_write_required_bytes
      );
      output << fmt::format("noncontiguous,{},,,,,\n", m_noncontiguous_masks);
      output.close();
    };
};

}       // namespace Ramulator

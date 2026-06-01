#include <vector>

#include "base/base.h"
#include "dram/dram.h"
#include "addr_mapper/addr_mapper.h"
#include "memory_system/memory_system.h"

namespace Ramulator {

class LinearMapperBase : public IAddrMapper {
  public:
    IDRAM* m_dram = nullptr;

    int m_num_levels = -1;          // How many levels in the hierarchy?
    std::vector<int> m_addr_bits;   // How many address bits for each level in the hierarchy?
    Addr_t m_tx_offset = -1;

    int m_col_bits_idx = -1;
    int m_row_bits_idx = -1;


  protected:
    Addr_t lower_addr_without_external_channel(Addr_t raw_addr,
                                               int num_channels,
                                               int channel_start_bit) const {
      if (channel_start_bit < 0) {
        Addr_t addr = raw_addr >> m_tx_offset;
        slice_lower_bits(addr, m_addr_bits[0]);
        return addr;
      }

      if (channel_start_bit < m_tx_offset) {
        throw ConfigurationError(
            "External channel start bit {} must be >= access atom offset {}.",
            channel_start_bit, m_tx_offset);
      }

      Addr_t low_mask = (Addr_t(1) << channel_start_bit) - 1;
      Addr_t low = raw_addr & low_mask;
      Addr_t high = raw_addr >> channel_start_bit;
      Addr_t rest = ((high / static_cast<Addr_t>(num_channels))
                     << channel_start_bit) | low;
      return rest >> m_tx_offset;
    }

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) {
      m_dram = memory_system->get_ifce<IDRAM>();

      // Populate m_addr_bits vector with the number of address bits for each level in the hierachy
      const auto& count = m_dram->m_organization.count;
      m_num_levels = count.size();
      m_addr_bits.resize(m_num_levels);
      for (size_t level = 0; level < m_addr_bits.size(); level++) {
        m_addr_bits[level] = calc_log2(count[level]);
      }

      // Last (Column) address have the granularity of the prefetch size
      m_addr_bits[m_num_levels - 1] -= calc_log2(m_dram->m_internal_prefetch_size);

      int tx_bytes = m_dram->m_internal_prefetch_size * m_dram->m_channel_width / 8;
      m_tx_offset = calc_log2(tx_bytes);

      // Determine where are the row and col bits for ChRaBaRoCo and RoBaRaCoCh
      try {
        m_row_bits_idx = m_dram->m_levels("row");
      } catch (const std::out_of_range& r) {
        throw std::runtime_error(fmt::format("Organization \"row\" not found in the spec, cannot use linear mapping!"));
      }

      // Assume column is always the last level
      m_col_bits_idx = m_num_levels - 1;
    }

};


class ChRaBaRoCo final : public LinearMapperBase, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IAddrMapper, ChRaBaRoCo, "ChRaBaRoCo", "Applies a trival mapping to the address.");

  public:
    void init() override { };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      LinearMapperBase::setup(frontend, memory_system);
    }

    void apply(Request& req) override {
      req.addr_vec.resize(m_num_levels, -1);
      Addr_t addr = req.addr >> m_tx_offset;
      for (int i = m_addr_bits.size() - 1; i >= 0; i--) {
        req.addr_vec[i] = slice_lower_bits(addr, m_addr_bits[i]);
      }
    }
};


class RoBaRaCoCh final : public LinearMapperBase, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IAddrMapper, RoBaRaCoCh, "RoBaRaCoCh", "Applies a RoBaRaCoCh mapping to the address.");

  public:
    void init() override { };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      LinearMapperBase::setup(frontend, memory_system);
    }

    void apply(Request& req) override {
      req.addr_vec.resize(m_num_levels, -1);
      Addr_t addr = req.addr >> m_tx_offset;
      req.addr_vec[0] = slice_lower_bits(addr, m_addr_bits[0]);
      req.addr_vec[m_addr_bits.size() - 1] = slice_lower_bits(addr, m_addr_bits[m_addr_bits.size() - 1]);
      for (int i = 1; i <= m_row_bits_idx; i++) {
        req.addr_vec[i] = slice_lower_bits(addr, m_addr_bits[i]);
      }
    }
};

class ExternalChannelRoBaRaCoCh final : public LinearMapperBase, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IAddrMapper, ExternalChannelRoBaRaCoCh, "ExternalChannelRoBaRaCoCh", "Uses Request::source_id as the channel and RoBaRaCoCh for lower levels.");

  private:
    int m_channel_start_bit = -1;

  public:
    void init() override { };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      LinearMapperBase::setup(frontend, memory_system);
      m_channel_start_bit = param<int>("channel_start_bit").default_val(-1);
    }

    void apply(Request& req) override {
      req.addr_vec.resize(m_num_levels, -1);

      int num_channels = m_dram->m_organization.count[0];
      if (req.source_id < 0 || req.source_id >= num_channels) {
        throw std::runtime_error(fmt::format(
            "ExternalChannelRoBaRaCoCh requires source_id in [0, {}), got {}.",
            num_channels, req.source_id));
      }

      Addr_t addr = lower_addr_without_external_channel(
          req.addr, num_channels, m_channel_start_bit);

      // Keep the lower-level RoBaRaCoCh bit layout identical to the baseline
      // mapper, but take the channel from the external simulator.
      req.addr_vec[0] = req.source_id;
      req.addr_vec[m_addr_bits.size() - 1] = slice_lower_bits(addr, m_addr_bits[m_addr_bits.size() - 1]);
      for (int i = 1; i <= m_row_bits_idx; i++) {
        req.addr_vec[i] = slice_lower_bits(addr, m_addr_bits[i]);
      }
    }
};

class ExternalChannelModuloRoBaRaCoCh final : public LinearMapperBase, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IAddrMapper, ExternalChannelModuloRoBaRaCoCh, "ExternalChannelModuloRoBaRaCoCh", "Folds Request::source_id into the available physical channels and uses RoBaRaCoCh for lower levels.");

  private:
    int m_channel_start_bit = -1;

  public:
    void init() override { };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      LinearMapperBase::setup(frontend, memory_system);
      m_channel_start_bit = param<int>("channel_start_bit").default_val(-1);
    }

    void apply(Request& req) override {
      req.addr_vec.resize(m_num_levels, -1);

      int num_channels = m_dram->m_organization.count[0];
      if (req.source_id < 0 || num_channels <= 0) {
        throw std::runtime_error(fmt::format(
            "ExternalChannelModuloRoBaRaCoCh requires non-negative source_id and positive channels, got source_id={} channels={}.",
            req.source_id, num_channels));
      }

      Addr_t addr = lower_addr_without_external_channel(
          req.addr, num_channels, m_channel_start_bit);

      req.addr_vec[0] = req.source_id % num_channels;
      req.addr_vec[m_addr_bits.size() - 1] = slice_lower_bits(addr, m_addr_bits[m_addr_bits.size() - 1]);
      for (int i = 1; i <= m_row_bits_idx; i++) {
        req.addr_vec[i] = slice_lower_bits(addr, m_addr_bits[i]);
      }
    }
};

class ExternalChannelGroupRoBaRaCoCh final : public LinearMapperBase, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IAddrMapper, ExternalChannelGroupRoBaRaCoCh, "ExternalChannelGroupRoBaRaCoCh", "Maps each Request::source_id to a group of physical channels and uses address bits to choose a channel within the group.");

  private:
    int m_channels_per_source = 1;
    int m_split_granularity_bytes = 32;
    int m_split_granularity_bits = 5;
    int m_channel_start_bit = -1;

  public:
    void init() override { };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      LinearMapperBase::setup(frontend, memory_system);
      m_channels_per_source = param<int>("channels_per_source").default_val(1);
      m_split_granularity_bytes = param<int>("split_granularity_bytes").default_val(32);
      m_channel_start_bit = param<int>("channel_start_bit").default_val(-1);

      if (m_channels_per_source <= 0) {
        throw ConfigurationError("ExternalChannelGroupRoBaRaCoCh channels_per_source must be positive.");
      }
      if (m_split_granularity_bytes <= 0 ||
          (m_split_granularity_bytes & (m_split_granularity_bytes - 1)) != 0) {
        throw ConfigurationError("ExternalChannelGroupRoBaRaCoCh split_granularity_bytes must be a positive power of two.");
      }
      m_split_granularity_bits = calc_log2(m_split_granularity_bytes);
    }

    void apply(Request& req) override {
      req.addr_vec.resize(m_num_levels, -1);

      int num_channels = m_dram->m_organization.count[0];
      int base_channel = req.source_id * m_channels_per_source;
      int channel_lane =
          static_cast<int>((req.addr >> m_split_granularity_bits) %
                           static_cast<Addr_t>(m_channels_per_source));
      int channel_id = base_channel + channel_lane;
      if (req.source_id < 0 || channel_id >= num_channels) {
        throw std::runtime_error(fmt::format(
            "ExternalChannelGroupRoBaRaCoCh requires source_id groups within [0, {}), got source_id={} channels_per_source={} lane={}.",
            num_channels, req.source_id, m_channels_per_source, channel_lane));
      }

      Addr_t addr = lower_addr_without_external_channel(
          req.addr, num_channels, m_channel_start_bit);

      req.addr_vec[0] = channel_id;
      req.addr_vec[m_addr_bits.size() - 1] = slice_lower_bits(addr, m_addr_bits[m_addr_bits.size() - 1]);
      for (int i = 1; i <= m_row_bits_idx; i++) {
        req.addr_vec[i] = slice_lower_bits(addr, m_addr_bits[i]);
      }
    }
};


class MOP4CLXOR final : public LinearMapperBase, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IAddrMapper, MOP4CLXOR, "MOP4CLXOR", "Applies a MOP4CLXOR mapping to the address.");

  public:
    void init() override { };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      LinearMapperBase::setup(frontend, memory_system);
    }

    void apply(Request& req) override {
      req.addr_vec.resize(m_num_levels, -1);
      Addr_t addr = req.addr >> m_tx_offset;
      req.addr_vec[m_col_bits_idx] = slice_lower_bits(addr, 2);
      for (int lvl = 0 ; lvl < m_row_bits_idx ; lvl++)
          req.addr_vec[lvl] = slice_lower_bits(addr, m_addr_bits[lvl]);
      req.addr_vec[m_col_bits_idx] += slice_lower_bits(addr, m_addr_bits[m_col_bits_idx]-2) << 2;
      req.addr_vec[m_row_bits_idx] = (int) addr;

      int row_xor_index = 0; 
      for (int lvl = 0 ; lvl < m_col_bits_idx ; lvl++){
        if (m_addr_bits[lvl] > 0){
          int mask = (req.addr_vec[m_col_bits_idx] >> row_xor_index) & ((1<<m_addr_bits[lvl])-1);
          req.addr_vec[lvl] = req.addr_vec[lvl] xor mask;
          row_xor_index += m_addr_bits[lvl];
        }
      }
    }
};

}   // namespace Ramulator

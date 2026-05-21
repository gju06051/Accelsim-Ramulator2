#include "dram/dram.h"
#include "dram/lambdas.h"

namespace Ramulator {

class HBM3SID : public IDRAM, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IDRAM, HBM3SID, "HBM3SID", "HBM3 Device Model with SID level")

  public:
    inline static const std::map<std::string, Organization> org_presets = {
      //   name        density   DQ    Ch Pch SID Bg Ba   Ro     Co
      {"HBM3SID_2Gb",   {2<<10,  128,  {1, 2,  4, 4,  4, 1<<11, 1<<6}}},
      {"HBM3SID_4Gb",   {4<<10,  128,  {1, 2,  4, 4,  4, 1<<12, 1<<6}}},
      {"HBM3SID_8Gb",   {8<<10,  128,  {1, 2,  4, 4,  4, 1<<13, 1<<6}}},
    };

    inline static const std::map<std::string, std::vector<int>> timing_presets = {
      //   name          rate   nBL  nCL  nRCDRD  nRCDWR  nRP  nRAS  nRC  nWR  nRTPS  nRTPL  nCWL  nCCDS  nCCDR  nCCDL  nRRDS  nRRDL  nWTRS  nWTRL  nRTW  nFAW  nRFC  nRFCSB  nREFI  nREFISB  nRREFD  tCK_ps
      {"HBM3SID_2Gbps",  {2000,   4,   7,    7,      7,     7,   17,  19,   8,    2,     3,    2,    1,      2,      2,     2,     3,     3,     4,    3,    15,   -1,   160,   3900,     -1,      8,   2000}},
      // JEDEC HBM3 6.4Gbps/pin uses CK=1600MHz, i.e. tCK=0.625ns.
      {"HBM3SID_6.4Gbps", {6400,   4,  23,   23,     23,    21,   52,  72,  10,    4,     4,   10,    2,      3,      4,     4,     4,     7,     7,    7,    26,   -1,   256,   6240,     -1,      8,    625}},
      // H100 SXM effective HBM3 rate: 3.35 TB/s over a 5120-bit interface
      // is about 5.234 Gbps/pin. Timings are scaled from the 6.4Gbps preset
      // to keep similar absolute ns values until vendor timing tables are added.
      {"HBM3SID_H100_SXM_5.234Gbps", {5234,   4,  19,   19,     19,    17,   43,  59,   8,    3,     3,    8,    2,      2,      3,     3,     3,     6,     6,    6,    21,   -1,   209,   5105,     -1,      7,    764}},
    };


  /************************************************
   *                Organization
   ***********************************************/
    const int m_internal_prefetch_size = 2;

    inline static constexpr ImplDef m_levels = {
      "channel", "pseudochannel", "sid", "bankgroup", "bank", "row", "column",
    };


  /************************************************
   *             Requests & Commands
   ***********************************************/
    inline static constexpr ImplDef m_commands = {
      "ACT",
      "PRE", "PREA",
      "RD",  "WR",  "RDA",  "WRA",
      "REFab", "REFsb",
      "RFMab", "RFMsb"
    };

    inline static const ImplLUT m_command_scopes = LUT (
      m_commands, m_levels, {
        {"ACT",   "row"},
        {"PRE",   "bank"},    {"PREA",   "channel"},
        {"RD",    "column"},  {"WR",     "column"}, {"RDA",   "column"}, {"WRA",   "column"},
        {"REFab", "channel"}, {"REFsb",  "bank"},
        {"RFMab", "channel"}, {"RFMsb",  "bank"},
      }
    );

    inline static const ImplLUT m_command_meta = LUT<DRAMCommandMeta> (
      m_commands, {
                // open?   close?   access?  refresh?
        {"ACT",   {true,   false,   false,   false}},
        {"PRE",   {false,  true,    false,   false}},
        {"PREA",  {false,  true,    false,   false}},
        {"RD",    {false,  false,   true,    false}},
        {"WR",    {false,  false,   true,    false}},
        {"RDA",   {false,  true,    true,    false}},
        {"WRA",   {false,  true,    true,    false}},
        {"REFab", {false,  false,   false,   true }},
        {"REFsb", {false,  false,   false,   true }},
        {"RFMab", {false,  false,   false,   true }},
        {"RFMsb", {false,  false,   false,   true }},
      }
    );

    inline static constexpr ImplDef m_requests = {
      "read", "write", "all-bank-refresh", "per-bank-refresh", "all-bank-rfm", "per-bank-rfm"
    };

    inline static const ImplLUT m_request_translations = LUT (
      m_requests, m_commands, {
        {"read", "RD"}, {"write", "WR"}, {"all-bank-refresh", "REFab"}, {"per-bank-refresh", "REFsb"},
        {"all-bank-rfm", "RFMab"}, {"per-bank-rfm", "RFMsb"},
      }
    );


  /************************************************
   *                   Timing
   ***********************************************/
    inline static constexpr ImplDef m_timings = {
      "rate",
      "nBL", "nCL", "nRCDRD", "nRCDWR", "nRP", "nRAS", "nRC", "nWR", "nRTPS", "nRTPL", "nCWL",
      "nCCDS", "nCCDR", "nCCDL",
      "nRRDS", "nRRDL",
      "nWTRS", "nWTRL",
      "nRTW",
      "nFAW",
      "nRFC", "nRFCSB", "nREFI", "nREFISB", "nRREFD",
      "tCK_ps"
    };


  /************************************************
   *                 Node States
   ***********************************************/
    inline static constexpr ImplDef m_states = {
       "Opened", "Closed", "N/A", "Refreshing"
    };

    inline static const ImplLUT m_init_states = LUT (
      m_levels, m_states, {
        {"channel",       "N/A"},
        {"pseudochannel", "N/A"},
        {"sid",           "N/A"},
        {"bankgroup",     "N/A"},
        {"bank",          "Closed"},
        {"row",           "Closed"},
        {"column",        "N/A"},
      }
    );

  public:
    struct Node : public DRAMNodeBase<HBM3SID> {
      Node(HBM3SID* dram, Node* parent, int level, int id) : DRAMNodeBase<HBM3SID>(dram, parent, level, id) {};
    };
    std::vector<Node*> m_channels;

    FuncMatrix<ActionFunc_t<Node>>  m_actions;
    FuncMatrix<PreqFunc_t<Node>>    m_preqs;
    FuncMatrix<RowhitFunc_t<Node>>  m_rowhits;
    FuncMatrix<RowopenFunc_t<Node>> m_rowopens;


  public:
    void tick() override {
      m_clk++;
    };

    void init() override {
      RAMULATOR_DECLARE_SPECS();
      set_organization();
      set_timing_vals();

      set_actions();
      set_preqs();
      set_rowhits();
      set_rowopens();

      create_nodes();
    };

    void issue_command(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      m_channels[channel_id]->update_timing(command, addr_vec, m_clk);
      m_channels[channel_id]->update_states(command, addr_vec, m_clk);
    };

    int get_preq_command(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->get_preq_command(command, addr_vec, m_clk);
    };

    bool check_ready(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->check_ready(command, addr_vec, m_clk);
    };

    bool check_rowbuffer_hit(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->check_rowbuffer_hit(command, addr_vec, m_clk);
    };

    bool check_node_open(int command, const AddrVec_t& addr_vec) override {
      int channel_id = addr_vec[m_levels["channel"]];
      return m_channels[channel_id]->check_node_open(command, addr_vec, m_clk);
    };

  private:
    static void PREab(Node* node, int cmd, int target_id, Clk_t clk) {
      for (auto pc : node->m_child_nodes) {
        for (auto sid : pc->m_child_nodes) {
          for (auto bg : sid->m_child_nodes) {
            for (auto bank : bg->m_child_nodes) {
              bank->m_state = m_states["Closed"];
              bank->m_row_state.clear();
            }
          }
        }
      }
    };

    static int RequireAllBanksClosed(Node* node, int cmd, const AddrVec_t& addr_vec, Clk_t clk) {
      for (auto pc : node->m_child_nodes) {
        for (auto sid : pc->m_child_nodes) {
          for (auto bg : sid->m_child_nodes) {
            for (auto bank : bg->m_child_nodes) {
              if (bank->m_state != m_states["Closed"]) {
                return m_commands["PREA"];
              }
            }
          }
        }
      }
      return cmd;
    };

    void set_organization() {
      // HBM3 exposes 64-bit top-level channels. Existing AccelSim-oriented
      // configs may still override this to 128-bit logical channels.
      m_channel_width = param_group("org").param<int>("channel_width").default_val(64);

      // Organization
      m_organization.count.resize(m_levels.size(), -1);

      // Load organization preset if provided
      if (auto preset_name = param_group("org").param<std::string>("preset").optional()) {
        if (org_presets.count(*preset_name) > 0) {
          m_organization = org_presets.at(*preset_name);
        } else {
          throw ConfigurationError("Unrecognized organization preset \"{}\" in {}!", *preset_name, get_name());
        }
      }

      // Override the preset with any provided settings
      if (auto dq = param_group("org").param<int>("dq").optional()) {
        m_organization.dq = *dq;
      }

      for (int i = 0; i < m_levels.size(); i++){
        auto level_name = m_levels(i);
        if (auto sz = param_group("org").param<int>(level_name).optional()) {
          m_organization.count[i] = *sz;
        }
      }

      if (auto density = param_group("org").param<int>("density").optional()) {
        m_organization.density = *density;
      }

      size_t _density = size_t(m_organization.count[m_levels["pseudochannel"]]) *
                        size_t(m_organization.count[m_levels["sid"]]) *
                        size_t(m_organization.count[m_levels["bankgroup"]]) *
                        size_t(m_organization.count[m_levels["bank"]]) *
                        size_t(m_organization.count[m_levels["row"]]) *
                        size_t(m_organization.count[m_levels["column"]]) *
                        size_t(m_organization.dq);
      _density >>= 20;
      if (m_organization.density != _density) {
        throw ConfigurationError(
            "Calculated {} channel density {} Mb does not equal the provided density {} Mb!",
            get_name(),
            _density,
            m_organization.density
        );
      }

      int tx_bytes = m_internal_prefetch_size * m_channel_width / 8;
      if (tx_bytes != 16 && tx_bytes != 32) {
        throw ConfigurationError(
            "{} expects a 16B or 32B access atom, but internal_prefetch_size={} and channel_width={} produce {}B.",
            get_name(),
            m_internal_prefetch_size,
            m_channel_width,
            tx_bytes
        );
      }
    };

    void set_timing_vals() {
      m_timing_vals.resize(m_timings.size(), -1);

      // Load timing preset if provided
      bool preset_provided = false;
      if (auto preset_name = param_group("timing").param<std::string>("preset").optional()) {
        if (timing_presets.count(*preset_name) > 0) {
          m_timing_vals = timing_presets.at(*preset_name);
          preset_provided = true;
        } else {
          throw ConfigurationError("Unrecognized timing preset \"{}\" in {}!", *preset_name, get_name());
        }
      }

      // HBM3 speed bins are specified as data rate per pin. WDQS/RDQS run at
      // twice CK and DQ is DDR on those strobes, so data_rate = 4 * fCK.
      if (auto dq = param_group("timing").param<int>("rate").optional()) {
        if (preset_provided) {
          throw ConfigurationError("Cannot change the transfer rate of {} when using a speed preset !", get_name());
        }
        m_timing_vals("rate") = *dq;
      }
      int tCK_ps = (4000000 + m_timing_vals("rate") / 2) / m_timing_vals("rate");
      m_timing_vals("tCK_ps") = tCK_ps;

      // tRFC and tREFISB tables use nanoseconds.
      constexpr int tRFC_TABLE[1][4] = {
      //  2Gb   4Gb   8Gb  16Gb
        { 160,  260,  350,  450},
      };

      constexpr int tREFISB_TABLE[1][4] = {
      //  2Gb    4Gb    8Gb    16Gb
        { 4875,  4875,  2438,  2438},
      };

      int density_id = [](int density_Mb) -> int {
        switch (density_Mb) {
          case 2048:  return 0;
          case 4096:  return 1;
          case 8192:  return 2;
          case 16384: return 3;
          default:    return -1;
        }
      }(m_organization.density);

      m_timing_vals("nRFC") = JEDEC_rounding(tRFC_TABLE[0][density_id], tCK_ps);
      m_timing_vals("nREFISB") = JEDEC_rounding(tREFISB_TABLE[0][density_id], tCK_ps);

      // Overwrite timing parameters with any user-provided value.
      // Rate and tCK should not be overwritten.
      for (int i = 1; i < m_timings.size() - 1; i++) {
        auto timing_name = std::string(m_timings(i));

        if (auto provided_timing = param_group("timing").param<int>(timing_name).optional()) {
          m_timing_vals(i) = *provided_timing;
        } else if (auto provided_timing = param_group("timing").param<float>(timing_name.replace(0, 1, "t")).optional()) {
          m_timing_vals(i) = JEDEC_rounding(*provided_timing, tCK_ps);
        }
      }

      for (int i = 0; i < m_timing_vals.size(); i++) {
        if (m_timing_vals(i) == -1) {
          throw ConfigurationError("In \"{}\", timing {} is not specified!", get_name(), m_timings(i));
        }
      }

      m_read_latency = m_timing_vals("nCL") + m_timing_vals("nBL");

      #define V(timing) (m_timing_vals(timing))
      populate_timingcons(this, {
          /*** Channel ***/
          {.level = "channel", .preceding = {"ACT"}, .following = {"ACT", "PRE", "PREA", "REFab", "REFsb", "RFMab", "RFMsb"}, .latency = 2},

          /*** Pseudo Channel ***/
          {.level = "pseudochannel", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nRRDS")},
          {.level = "pseudochannel", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nFAW"), .window = 4},
          {.level = "pseudochannel", .preceding = {"ACT"}, .following = {"REFsb", "RFMsb"}, .latency = V("nRRDS") + 1},
          {.level = "pseudochannel", .preceding = {"REFsb", "RFMsb"}, .following = {"REFsb", "RFMsb"}, .latency = V("nRREFD")},
          {.level = "pseudochannel", .preceding = {"REFsb", "RFMsb"}, .following = {"ACT"}, .latency = V("nRREFD") - 1},

          {.level = "pseudochannel", .preceding = {"RD", "RDA"}, .following = {"RD", "RDA"}, .latency = V("nBL")},
          {.level = "pseudochannel", .preceding = {"WR", "WRA"}, .following = {"WR", "WRA"}, .latency = V("nBL")},
          {.level = "pseudochannel", .preceding = {"RD", "RDA"}, .following = {"RD", "RDA"}, .latency = V("nCCDS")},
          {.level = "pseudochannel", .preceding = {"WR", "WRA"}, .following = {"WR", "WRA"}, .latency = V("nCCDS")},
          {.level = "pseudochannel", .preceding = {"RD", "RDA"}, .following = {"WR", "WRA"}, .latency = V("nCL") + V("nBL") + 2 - V("nCWL")},
          {.level = "pseudochannel", .preceding = {"WR", "WRA"}, .following = {"RD", "RDA"}, .latency = V("nCWL") + V("nBL") + V("nWTRS")},
          {.level = "pseudochannel", .preceding = {"RD"}, .following = {"PREA"}, .latency = V("nRTPS")},
          {.level = "pseudochannel", .preceding = {"WR"}, .following = {"PREA"}, .latency = V("nCWL") + V("nBL") + V("nWR")},
          {.level = "pseudochannel", .preceding = {"ACT"}, .following = {"PREA"}, .latency = V("nRAS")},
          {.level = "pseudochannel", .preceding = {"PREA"}, .following = {"ACT"}, .latency = V("nRP")},
          {.level = "pseudochannel", .preceding = {"ACT"}, .following = {"REFab", "RFMab"}, .latency = V("nRC")},
          {.level = "pseudochannel", .preceding = {"PRE", "PREA"}, .following = {"REFab", "RFMab"}, .latency = V("nRP")},
          {.level = "pseudochannel", .preceding = {"RDA"}, .following = {"REFab", "RFMab"}, .latency = V("nRP") + V("nRTPS")},
          {.level = "pseudochannel", .preceding = {"WRA"}, .following = {"REFab", "RFMab"}, .latency = V("nCWL") + V("nBL") + V("nWR") + V("nRP")},
          {.level = "pseudochannel", .preceding = {"REFab", "RFMab"}, .following = {"ACT", "REFsb", "RFMsb"}, .latency = V("nRFC")},

          /*** Different Stack ID ***/
          {.level = "sid", .preceding = {"RD", "RDA"}, .following = {"RD", "RDA"}, .latency = V("nCCDR"), .is_sibling = true},

          /*** Same Bank Group ***/
          {.level = "bankgroup", .preceding = {"RD", "RDA"}, .following = {"RD", "RDA"}, .latency = V("nCCDL")},
          {.level = "bankgroup", .preceding = {"WR", "WRA"}, .following = {"WR", "WRA"}, .latency = V("nCCDL")},
          {.level = "bankgroup", .preceding = {"WR", "WRA"}, .following = {"RD", "RDA"}, .latency = V("nCWL") + V("nBL") + V("nWTRL")},
          {.level = "bankgroup", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nRRDL")},
          {.level = "bankgroup", .preceding = {"ACT"}, .following = {"REFsb", "RFMsb"}, .latency = V("nRRDL") + 1},
          {.level = "bankgroup", .preceding = {"REFsb", "RFMsb"}, .following = {"ACT"}, .latency = V("nRRDL") - 1},

          /*** Bank ***/
          {.level = "bank", .preceding = {"RD"},  .following = {"PRE"}, .latency = V("nRTPS")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nRC")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"RD", "RDA"}, .latency = V("nRCDRD")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"WR", "WRA"}, .latency = V("nRCDWR")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"PRE"}, .latency = V("nRAS")},
          {.level = "bank", .preceding = {"PRE"}, .following = {"ACT"}, .latency = V("nRP")},
          {.level = "bank", .preceding = {"RD"},  .following = {"PRE"}, .latency = V("nRTPL")},
          {.level = "bank", .preceding = {"WR"},  .following = {"PRE"}, .latency = V("nCWL") + V("nBL") + V("nWR")},
          {.level = "bank", .preceding = {"RDA"}, .following = {"ACT", "REFsb", "RFMsb"}, .latency = V("nRTPL") + V("nRP")},
          {.level = "bank", .preceding = {"WRA"}, .following = {"ACT", "REFsb", "RFMsb"}, .latency = V("nCWL") + V("nBL") + V("nWR") + V("nRP")},
        }
      );
      #undef V
    };

    void set_actions() {
      m_actions.resize(m_levels.size(), std::vector<ActionFunc_t<Node>>(m_commands.size()));

      m_actions[m_levels["channel"]][m_commands["PREA"]] = PREab;

      m_actions[m_levels["bank"]][m_commands["ACT"]] = Lambdas::Action::Bank::ACT<HBM3SID>;
      m_actions[m_levels["bank"]][m_commands["PRE"]] = Lambdas::Action::Bank::PRE<HBM3SID>;
      m_actions[m_levels["bank"]][m_commands["RDA"]] = Lambdas::Action::Bank::PRE<HBM3SID>;
      m_actions[m_levels["bank"]][m_commands["WRA"]] = Lambdas::Action::Bank::PRE<HBM3SID>;
    };

    void set_preqs() {
      m_preqs.resize(m_levels.size(), std::vector<PreqFunc_t<Node>>(m_commands.size()));

      m_preqs[m_levels["channel"]][m_commands["REFab"]] = RequireAllBanksClosed;

      m_preqs[m_levels["bank"]][m_commands["REFsb"]] = Lambdas::Preq::Bank::RequireBankClosed<HBM3SID>;
      m_preqs[m_levels["bank"]][m_commands["RD"]] = Lambdas::Preq::Bank::RequireRowOpen<HBM3SID>;
      m_preqs[m_levels["bank"]][m_commands["WR"]] = Lambdas::Preq::Bank::RequireRowOpen<HBM3SID>;
    };

    void set_rowhits() {
      m_rowhits.resize(m_levels.size(), std::vector<RowhitFunc_t<Node>>(m_commands.size()));

      m_rowhits[m_levels["bank"]][m_commands["RD"]] = Lambdas::RowHit::Bank::RDWR<HBM3SID>;
      m_rowhits[m_levels["bank"]][m_commands["WR"]] = Lambdas::RowHit::Bank::RDWR<HBM3SID>;
    }


    void set_rowopens() {
      m_rowopens.resize(m_levels.size(), std::vector<RowhitFunc_t<Node>>(m_commands.size()));

      m_rowopens[m_levels["bank"]][m_commands["RD"]] = Lambdas::RowOpen::Bank::RDWR<HBM3SID>;
      m_rowopens[m_levels["bank"]][m_commands["WR"]] = Lambdas::RowOpen::Bank::RDWR<HBM3SID>;
    }


    void create_nodes() {
      int num_channels = m_organization.count[m_levels["channel"]];
      for (int i = 0; i < num_channels; i++) {
        Node* channel = new Node(this, nullptr, 0, i);
        m_channels.push_back(channel);
      }
    };
};


}        // namespace Ramulator

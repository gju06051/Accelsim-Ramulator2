#include "dram/dram.h"
#include "dram/lambdas.h"

namespace Ramulator {

class GDDR7 : public IDRAM, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IDRAM, GDDR7, "GDDR7", "GDDR7 Device Model")

  public:
    inline static const std::map<std::string, Organization> org_presets = {
      // JESD239B Table 2. Column count includes the 32n prefetch slots, so
      // the address mapper exposes C[5:0] after subtracting log2(32).
      //    name              density  DQ   Ch  Ba   Ro      Co
      {"GDDR7_16Gb_4ch",      {16<<10,  8,  {4,  16,  1<<14,  1<<11}}},
      {"GDDR7_16Gb_2ch",      {16<<10,  8,  {2,  16,  1<<15,  1<<11}}},
      {"GDDR7_32Gb_4ch",      {32<<10,  8,  {4,  16,  1<<15,  1<<11}}},
      {"GDDR7_32Gb_2ch",      {32<<10,  8,  {2,  16,  1<<16,  1<<11}}},
      {"GDDR7_64Gb_4ch",      {64<<10,  8,  {4,  16,  1<<16,  1<<11}}},
      {"GDDR7_64Gb_2ch",      {64<<10,  8,  {2,  16,  1<<17,  1<<11}}},
    };

    inline static const std::map<std::string, std::vector<int>> timing_presets = {
      // Baseline timing presets use CK4 cycles. JESD239B leaves many AC
      // timings vendor-specific; these presets anchor row/refresh values to
      // Table 142 IDD conditions and use conservative command defaults for
      // functional architectural studies. Intermediate speed bins cover public
      // ISSCC silicon points: 30.3Gbps low-VDDQ, 35.4/37Gbps 16Gb devices,
      // Samsung 38.8/42.5Gbps, and SK hynix 48Gbps 24Gb devices.
      //
      // name             rate   nBL nCL nRCDRD nRCDWR nRP nRAS nRC nWR nRTP nCWL nCCD nCCDSB nRRD nWTR nWTRSB nRTW nFAW nRFCab nRFCpb nRREFD nREFI tCK_ps
      {"GDDR7_28Gbps",   {28000,  2, 10,    32,    32,  36,  53,  88, 53,  4,   9,   2,    4,   22,  14,   18,    7,  88,   351,   211,    36,  3328,   571}},
      {"GDDR7_30p3Gbps", {30300,  2, 11,    35,    35,  38,  57,  95, 57,  4,  10,   2,    4,   23,  15,   19,    8,  95,   379,   228,    38,  3599,   528}},
      {"GDDR7_32Gbps",   {32000,  2, 12,    36,    36,  40,  60, 100, 60,  4,  10,   2,    4,   24,  15,   20,    8, 100,   400,   240,    40,  3800,   500}},
      {"GDDR7_35p4Gbps", {35400,  2, 13,    40,    40,  45,  67, 111, 67,  4,  11,   2,    4,   27,  17,   23,    8, 111,   443,   266,    45,  4204,   452}},
      {"GDDR7_37Gbps",   {37000,  2, 13,    42,    42,  47,  70, 116, 70,  4,  11,   2,    4,   28,  18,   24,    8, 116,   463,   278,    47,  4399,   432}},
      {"GDDR7_38p8Gbps", {38800,  2, 14,    44,    44,  49,  73, 122, 73,  4,  12,   2,    4,   30,  19,   25,    8, 122,   486,   292,    49,  4612,   412}},
      {"GDDR7_40Gbps",   {40000,  2, 14,    45,    45,  50,  75, 125, 75,  4,  12,   2,    4,   30,  19,   25,    8, 125,   500,   300,    50,  4750,   400}},
      {"GDDR7_42p5Gbps", {42500,  2, 15,    48,    48,  54,  80, 133, 80,  4,  13,   2,    4,   32,  20,   27,    8, 133,   532,   320,    54,  5054,   376}},
      {"GDDR7_48Gbps",   {48000,  2, 16,    55,    55,  61,  91, 151, 91,  4,  14,   2,    4,   37,  23,   31,    8, 151,   601,   361,    61,  5706,   333}},
    };


  /************************************************
   *                Organization
   ***********************************************/
    const int m_internal_prefetch_size = 32;

    inline static constexpr ImplDef m_levels = {
      "channel", "bank", "row", "column",
    };


  /************************************************
   *             Requests & Commands
   ***********************************************/
    inline static constexpr ImplDef m_commands = {
      "ACT",
      "PREA", "PRE",
      "RD", "WR", "RDA", "WRA",
      "REFab", "REFpb",
      "RFMab", "RFMpb",
    };

    inline static const ImplLUT m_command_scopes = LUT (
      m_commands, m_levels, {
        {"ACT",   "row"},
        {"PREA",  "channel"}, {"PRE",   "bank"},
        {"RD",    "column"},  {"WR",    "column"}, {"RDA",   "column"}, {"WRA",   "column"},
        {"REFab", "channel"}, {"REFpb", "bank"},
        {"RFMab", "channel"}, {"RFMpb", "bank"},
      }
    );

    inline static const ImplLUT m_command_meta = LUT<DRAMCommandMeta> (
      m_commands, {
                // open?   close?   access?  refresh?
        {"ACT",   {true,   false,   false,   false}},
        {"PREA",  {false,  true,    false,   false}},
        {"PRE",   {false,  true,    false,   false}},
        {"RD",    {false,  false,   true,    false}},
        {"WR",    {false,  false,   true,    false}},
        {"RDA",   {false,  true,    true,    false}},
        {"WRA",   {false,  true,    true,    false}},
        {"REFab", {false,  false,   false,   true }},
        {"REFpb", {false,  false,   false,   true }},
        {"RFMab", {false,  false,   false,   true }},
        {"RFMpb", {false,  false,   false,   true }},
      }
    );

    inline static constexpr ImplDef m_requests = {
      "read", "write", "all-bank-refresh", "per-bank-refresh", "all-bank-rfm", "per-bank-rfm",
    };

    inline static const ImplLUT m_request_translations = LUT (
      m_requests, m_commands, {
        {"read", "RD"}, {"write", "WR"},
        {"all-bank-refresh", "REFab"}, {"per-bank-refresh", "REFpb"},
        {"all-bank-rfm", "RFMab"}, {"per-bank-rfm", "RFMpb"},
      }
    );


  /************************************************
   *                   Timing
   ***********************************************/
    inline static constexpr ImplDef m_timings = {
      "rate",
      "nBL", "nCL", "nRCDRD", "nRCDWR", "nRP", "nRAS", "nRC", "nWR", "nRTP", "nCWL",
      "nCCD", "nCCDSB",
      "nRRD",
      "nWTR", "nWTRSB",
      "nRTW",
      "nFAW",
      "nRFCab", "nRFCpb", "nRREFD", "nREFI",
      "tCK_ps"
    };


  /************************************************
   *                 Node States
   ***********************************************/
    inline static constexpr ImplDef m_states = {
       "Opened", "Closed", "PowerUp", "N/A", "Refreshing"
    };

    inline static const ImplLUT m_init_states = LUT (
      m_levels, m_states, {
        {"channel", "N/A"},
        {"bank",    "Closed"},
        {"row",     "Closed"},
        {"column",  "N/A"},
      }
    );

  public:
    struct Node : public DRAMNodeBase<GDDR7> {
      Node(GDDR7* dram, Node* parent, int level, int id) : DRAMNodeBase<GDDR7>(dram, parent, level, id) {};
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
      for (auto bank : node->m_child_nodes) {
        bank->m_state = m_states["Closed"];
        bank->m_row_state.clear();
      }
    };

    static int RequireAllBanksClosed(Node* node, int cmd, const AddrVec_t& addr_vec, Clk_t clk) {
      for (auto bank : node->m_child_nodes) {
        if (bank->m_state != m_states["Closed"]) {
          return m_commands["PREA"];
        }
      }
      return cmd;
    };

    void set_organization() {
      m_channel_width = param_group("org").param<int>("channel_width").default_val(8);

      m_organization.count.resize(m_levels.size(), -1);

      if (auto preset_name = param_group("org").param<std::string>("preset").optional()) {
        if (org_presets.count(*preset_name) > 0) {
          m_organization = org_presets.at(*preset_name);
        } else {
          throw ConfigurationError("Unrecognized organization preset \"{}\" in {}!", *preset_name, get_name());
        }
      }

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

      size_t _density = size_t(m_organization.count[m_levels["channel"]]) *
                        size_t(m_organization.count[m_levels["bank"]]) *
                        size_t(m_organization.count[m_levels["row"]]) *
                        size_t(m_organization.count[m_levels["column"]]) *
                        size_t(m_organization.dq);
      _density >>= 20;
      if (m_organization.density != _density) {
        throw ConfigurationError(
            "Calculated {} device density {} Mb does not equal the provided density {} Mb!",
            get_name(),
            _density,
            m_organization.density
        );
      }

      int tx_bytes = m_internal_prefetch_size * m_channel_width / 8;
      int row_bytes = m_organization.count[m_levels["column"]] * m_channel_width / 8;
      if (tx_bytes != 32) {
        throw ConfigurationError(
            "{} expects a 32B per-channel access atom, but internal_prefetch_size={} and channel_width={} produce {}B.",
            get_name(),
            m_internal_prefetch_size,
            m_channel_width,
            tx_bytes
        );
      }
      if (row_bytes != 2048) {
        throw ConfigurationError(
            "{} expects a 2KB per-channel page, but column={} and channel_width={} produce {}B.",
            get_name(),
            m_organization.count[m_levels["column"]],
            m_channel_width,
            row_bytes
        );
      }
    };

    void set_timing_vals() {
      m_timing_vals.resize(m_timings.size(), -1);

      bool preset_provided = false;
      if (auto preset_name = param_group("timing").param<std::string>("preset").optional()) {
        if (timing_presets.count(*preset_name) > 0) {
          m_timing_vals = timing_presets.at(*preset_name);
          preset_provided = true;
        } else {
          throw ConfigurationError("Unrecognized timing preset \"{}\" in {}!", *preset_name, get_name());
        }
      }

      if (auto rate = param_group("timing").param<int>("rate").optional()) {
        if (preset_provided) {
          throw ConfigurationError("Cannot change the transfer rate of {} when using a speed preset !", get_name());
        }
        m_timing_vals("rate") = *rate;
      }

      if (m_timing_vals("rate") == -1) {
        throw ConfigurationError("In \"{}\", timing rate is not specified!", get_name());
      }

      // GDDR7 PAM3 data_rate = 4 * fWCK and CK4 = fWCK / 4, so
      // fCK4 = data_rate / 16.
      int tCK_ps = (16000000 + m_timing_vals("rate") / 2) / m_timing_vals("rate");
      m_timing_vals("tCK_ps") = tCK_ps;

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
          {.level = "channel", .preceding = {"RD", "RDA"}, .following = {"RD", "RDA"}, .latency = V("nBL")},
          {.level = "channel", .preceding = {"WR", "WRA"}, .following = {"WR", "WRA"}, .latency = V("nBL")},

          {.level = "channel", .preceding = {"RD", "RDA"}, .following = {"RD", "RDA"}, .latency = V("nCCD")},
          {.level = "channel", .preceding = {"WR", "WRA"}, .following = {"WR", "WRA"}, .latency = V("nCCD")},
          {.level = "channel", .preceding = {"RD", "RDA"}, .following = {"WR", "WRA"}, .latency = V("nRTW")},
          {.level = "channel", .preceding = {"WR", "WRA"}, .following = {"RD", "RDA"}, .latency = V("nCWL") + V("nBL") + V("nWTR")},

          {.level = "channel", .preceding = {"ACT"}, .following = {"ACT", "REFpb", "RFMpb"}, .latency = V("nRRD")},
          {.level = "channel", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nFAW"), .window = 4},
          {.level = "channel", .preceding = {"ACT"}, .following = {"REFab", "RFMab"}, .latency = V("nRC")},
          {.level = "channel", .preceding = {"PRE"}, .following = {"REFab", "RFMab"}, .latency = V("nRP")},
          {.level = "channel", .preceding = {"RDA"}, .following = {"REFab", "RFMab"}, .latency = V("nRTP") + V("nRP")},
          {.level = "channel", .preceding = {"WRA"}, .following = {"REFab", "RFMab"}, .latency = V("nCWL") + V("nBL") + V("nWR") + V("nRP")},
          {.level = "channel", .preceding = {"REFab", "RFMab"}, .following = {"ACT", "REFpb", "RFMpb"}, .latency = V("nRFCab")},

          {.level = "channel", .preceding = {"REFpb", "RFMpb"}, .following = {"ACT", "REFpb", "RFMpb"}, .latency = V("nRREFD")},

          /*** Bank ***/
          {.level = "bank", .preceding = {"RD", "RDA"}, .following = {"RD", "RDA"}, .latency = V("nCCDSB")},
          {.level = "bank", .preceding = {"WR", "WRA"}, .following = {"WR", "WRA"}, .latency = V("nCCDSB")},
          {.level = "bank", .preceding = {"WR", "WRA"}, .following = {"RD", "RDA"}, .latency = V("nCWL") + V("nBL") + V("nWTRSB")},

          {.level = "bank", .preceding = {"ACT"}, .following = {"RD", "RDA"}, .latency = V("nRCDRD")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"WR", "WRA"}, .latency = V("nRCDWR")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"PRE", "PREA", "REFpb", "RFMpb"}, .latency = V("nRAS")},
          {.level = "bank", .preceding = {"ACT"}, .following = {"ACT"}, .latency = V("nRC")},
          {.level = "bank", .preceding = {"PRE"}, .following = {"ACT", "REFpb", "RFMpb"}, .latency = V("nRP")},
          {.level = "bank", .preceding = {"RD"},  .following = {"PRE", "PREA"}, .latency = V("nRTP")},
          {.level = "bank", .preceding = {"WR"},  .following = {"PRE", "PREA"}, .latency = V("nCWL") + V("nBL") + V("nWR")},
          {.level = "bank", .preceding = {"RDA"}, .following = {"ACT", "REFpb", "RFMpb"}, .latency = V("nRTP") + V("nRP")},
          {.level = "bank", .preceding = {"WRA"}, .following = {"ACT", "REFpb", "RFMpb"}, .latency = V("nCWL") + V("nBL") + V("nWR") + V("nRP")},
          {.level = "bank", .preceding = {"REFpb", "RFMpb"}, .following = {"ACT", "REFpb", "RFMpb"}, .latency = V("nRFCpb")},
        }
      );
      #undef V
    };

    void set_actions() {
      m_actions.resize(m_levels.size(), std::vector<ActionFunc_t<Node>>(m_commands.size()));

      m_actions[m_levels["channel"]][m_commands["PREA"]] = PREab;

      m_actions[m_levels["bank"]][m_commands["ACT"]] = Lambdas::Action::Bank::ACT<GDDR7>;
      m_actions[m_levels["bank"]][m_commands["PRE"]] = Lambdas::Action::Bank::PRE<GDDR7>;
      m_actions[m_levels["bank"]][m_commands["RDA"]] = Lambdas::Action::Bank::PRE<GDDR7>;
      m_actions[m_levels["bank"]][m_commands["WRA"]] = Lambdas::Action::Bank::PRE<GDDR7>;
    };

    void set_preqs() {
      m_preqs.resize(m_levels.size(), std::vector<PreqFunc_t<Node>>(m_commands.size()));

      m_preqs[m_levels["channel"]][m_commands["REFab"]] = RequireAllBanksClosed;
      m_preqs[m_levels["channel"]][m_commands["RFMab"]] = RequireAllBanksClosed;

      m_preqs[m_levels["bank"]][m_commands["RD"]] = Lambdas::Preq::Bank::RequireRowOpen<GDDR7>;
      m_preqs[m_levels["bank"]][m_commands["WR"]] = Lambdas::Preq::Bank::RequireRowOpen<GDDR7>;
      m_preqs[m_levels["bank"]][m_commands["REFpb"]] = Lambdas::Preq::Bank::RequireBankClosed<GDDR7>;
      m_preqs[m_levels["bank"]][m_commands["RFMpb"]] = Lambdas::Preq::Bank::RequireBankClosed<GDDR7>;
    };

    void set_rowhits() {
      m_rowhits.resize(m_levels.size(), std::vector<RowhitFunc_t<Node>>(m_commands.size()));

      m_rowhits[m_levels["bank"]][m_commands["RD"]] = Lambdas::RowHit::Bank::RDWR<GDDR7>;
      m_rowhits[m_levels["bank"]][m_commands["WR"]] = Lambdas::RowHit::Bank::RDWR<GDDR7>;
    }

    void set_rowopens() {
      m_rowopens.resize(m_levels.size(), std::vector<RowhitFunc_t<Node>>(m_commands.size()));

      m_rowopens[m_levels["bank"]][m_commands["RD"]] = Lambdas::RowOpen::Bank::RDWR<GDDR7>;
      m_rowopens[m_levels["bank"]][m_commands["WR"]] = Lambdas::RowOpen::Bank::RDWR<GDDR7>;
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

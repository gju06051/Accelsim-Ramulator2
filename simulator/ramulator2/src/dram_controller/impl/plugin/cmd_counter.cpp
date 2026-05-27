#include <vector>
#include <unordered_map>
#include <limits>
#include <random>
#include <filesystem>
#include <fstream>
#include <string>

#include "base/base.h"
#include "dram_controller/controller.h"
#include "dram_controller/plugin.h"

namespace Ramulator {

class CommandCounter : public IControllerPlugin, public Implementation {
  RAMULATOR_REGISTER_IMPLEMENTATION(IControllerPlugin, CommandCounter, "CommandCounter", "Counting the number of issued commands.")

  private:
    IDRAM* m_dram = nullptr;

    std::vector<std::string> m_commands_to_count;
    std::unordered_map<int, size_t> m_command_counters;

    std::string m_save_path_template;

    std::filesystem::path resolve_save_path() const {
      std::string path = m_save_path_template;
      const std::string channel = std::to_string(m_ctrl ? m_ctrl->m_channel_id : -1);
      size_t pos = 0;
      while ((pos = path.find("{channel}", pos)) != std::string::npos) {
        path.replace(pos, std::string("{channel}").size(), channel);
        pos += channel.size();
      }
      return std::filesystem::path(path);
    }


  public:
    void init() override { 
      m_commands_to_count = param<std::vector<std::string>>("commands_to_count").desc("A list of commands to be counted").required();

      m_save_path_template = param<std::string>("path")
        .desc("Path to the command-count file. Use {channel} for per-channel output.")
        .required();
    };

    void setup(IFrontEnd* frontend, IMemorySystem* memory_system) override {
      m_ctrl = cast_parent<IDRAMController>();
      m_dram = m_ctrl->m_dram;

      for (const auto& command_name : m_commands_to_count) {
        if (!m_dram->m_commands.contains(command_name)) {
          throw ConfigurationError("Command {} does not exist in the DRAM standard {}!", command_name, m_dram->get_name());
        }
        m_command_counters[m_dram->m_commands(command_name)] = 0;
      }
    };

    void update(bool request_found, ReqBuffer::iterator& req_it) override {
      if (request_found) {
        m_command_counters[req_it->command]++;
      }
    };

    void finalize() override {
      const auto save_path = resolve_save_path();
      auto parent_path = save_path.parent_path();
      if (!parent_path.empty()) {
        std::filesystem::create_directories(parent_path);
        if (!(std::filesystem::exists(parent_path) && std::filesystem::is_directory(parent_path))) {
          throw ConfigurationError("Invalid path to command-count file: {}", parent_path.string());
        }
      }

      std::ofstream output(save_path);
      for (const auto& [cmd_id, count] : m_command_counters) {
        output << fmt::format("{}, {}", m_dram->m_commands(cmd_id), count) << std::endl;
      }
      output.close();
    }

};

}       // namespace Ramulator

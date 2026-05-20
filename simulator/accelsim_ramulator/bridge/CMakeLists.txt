cmake_minimum_required(VERSION 3.16)

project(sgram_ramulator2_bridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT DEFINED RAMULATOR2_DIR)
  get_filename_component(RAMULATOR2_DIR
    "${CMAKE_CURRENT_LIST_DIR}/../../ramulator2" ABSOLUTE)
endif()

add_library(sgram_ramulator2_bridge SHARED ramulator2_c_api.cc)

target_include_directories(sgram_ramulator2_bridge
  PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}"
    "${RAMULATOR2_DIR}/src"
    "${RAMULATOR2_DIR}/ext/yaml-cpp/include"
    "${RAMULATOR2_DIR}/ext/spdlog/include"
)

find_library(RAMULATOR2_LIBRARY
  NAMES ramulator
  PATHS "${RAMULATOR2_DIR}"
  NO_DEFAULT_PATH
  REQUIRED
)

target_link_libraries(sgram_ramulator2_bridge PRIVATE "${RAMULATOR2_LIBRARY}")

set_target_properties(sgram_ramulator2_bridge PROPERTIES
  BUILD_RPATH "${RAMULATOR2_DIR}"
  INSTALL_RPATH "${RAMULATOR2_DIR}"
)

add_executable(sgram_ramulator2_bridge_smoke ramulator2_bridge_smoke.cc)
target_include_directories(sgram_ramulator2_bridge_smoke
  PRIVATE "${CMAKE_CURRENT_LIST_DIR}")
target_link_libraries(sgram_ramulator2_bridge_smoke PRIVATE sgram_ramulator2_bridge)

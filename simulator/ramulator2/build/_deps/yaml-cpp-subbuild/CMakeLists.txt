# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.18.2)

# We name the project and the target for the ExternalProject_Add() call
# to something that will highlight to the user what we are working on if
# something goes wrong and an error message is produced.

project(yaml-cpp-populate NONE)

include(ExternalProject)
ExternalProject_Add(yaml-cpp-populate
                     "UPDATE_DISCONNECTED" "False" "GIT_REPOSITORY" "https://github.com/jbeder/yaml-cpp.git" "GIT_TAG" "yaml-cpp-0.7.0"
                    SOURCE_DIR          "/home/gju06051/StackGanged/simulator/ramulator2/ext/yaml-cpp"
                    BINARY_DIR          "/home/gju06051/StackGanged/simulator/ramulator2/build/_deps/yaml-cpp-build"
                    CONFIGURE_COMMAND   ""
                    BUILD_COMMAND       ""
                    INSTALL_COMMAND     ""
                    TEST_COMMAND        ""
                    USES_TERMINAL_DOWNLOAD  YES
                    USES_TERMINAL_UPDATE    YES
)



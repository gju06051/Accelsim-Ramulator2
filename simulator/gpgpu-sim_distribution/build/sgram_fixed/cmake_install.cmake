# Install script for directory: /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set default install directory permissions.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/usr/bin/objdump")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/build/sgram_fixed/src/cmake_install.cmake")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/build/sgram_fixed/libcuda/cmake_install.cmake")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for the subdirectory.
  include("/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/build/sgram_fixed/libopencl/cmake_install.cmake")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so")
    file(RPATH_CHECK
         FILE "$ENV{DESTDIR}/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so"
         RPATH "")
  endif()
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
file(INSTALL DESTINATION "/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release" TYPE SHARED_LIBRARY FILES "/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/build/sgram_fixed/libcudart.so")
  if(EXISTS "$ENV{DESTDIR}/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so")
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND "/usr/bin/strip" "$ENV{DESTDIR}/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so")
    endif()
  endif()
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.2)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.3)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.4)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.5.0)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.5.5)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.6.0)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.6.5)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.7.0)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.7.5)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.8.0)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.9.0)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.9.1)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.9.2)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.10.0)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.10.1)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.11.0)
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(    COMMAND /usr/local/bin/cmake -E create_symlink     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so     /home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/lib/gcc-13.3.0/cuda-12030/release/libcudart.so.12)
endif()

if(CMAKE_INSTALL_COMPONENT)
  set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
file(WRITE "/home/gju06051/StackGanged/simulator/gpgpu-sim_distribution/build/sgram_fixed/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")

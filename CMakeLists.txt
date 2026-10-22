# SPDX-License-Identifier: GPL-2.0-or-later
cmake_minimum_required(VERSION 3.20)
project(paleblood C CXX)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)   # editors: ln -s build/compile_commands.json .
# Verification proves the code as it is built, so every build is an optimized one unless asked
# otherwise (CI builds Release too).
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)

# A Release build defines NDEBUG, so every assert() compiles to nothing -- a guard that cannot fail, in the
# configuration the test suite runs. The tree has 0 asserted invariants today (grep -rn '\bassert(' runtime/
# test/ game/ -> 0), so nothing was lost; this is here so the first one added is checked rather than silently
# removed. -UNDEBUG comes after the type's flags, and test/test_build_flags.py asserts that ordering, because
# a flag protected only by this comment is a flag someone later drops.
endif()
# Appended AFTER the if(): the block above runs only when no build type is cached, which is false for every
# configured tree -- inside it, this was two lines that never executed, and CMake reported success.
string(APPEND CMAKE_C_FLAGS_RELEASE " -UNDEBUG")
string(APPEND CMAKE_CXX_FLAGS_RELEASE " -UNDEBUG")
add_compile_options(-Wall -Wextra -Werror)

enable_testing()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_subdirectory(runtime)
add_subdirectory(game)

add_executable(test_hooks test/test_hooks.c)
target_link_libraries(test_hooks bbrt)
add_test(NAME hooks COMMAND test_hooks)
add_executable(test_plugin test/test_plugin.c runtime/plugin.c runtime/hooks.c runtime/process.c)
target_include_directories(test_plugin PRIVATE runtime/include)
add_test(NAME plugin COMMAND test_plugin)

add_executable(test_host_hooks test/test_host_hooks.c runtime/host_hooks.c runtime/boundary_stub.c)
target_include_directories(test_host_hooks PRIVATE runtime/include)
add_test(NAME host_hooks COMMAND test_host_hooks)

add_executable(test_snapshot_stub test/test_snapshot_stub.c runtime/boundary_stub.c)
target_include_directories(test_snapshot_stub PRIVATE runtime/include)
add_test(NAME snapshot_stub COMMAND test_snapshot_stub)

add_executable(test_guest_mem test/test_guest_mem.c runtime/guest_mem.c runtime/process.c)
target_include_directories(test_guest_mem PRIVATE runtime/include)
add_test(NAME guest_mem COMMAND test_guest_mem)
add_executable(test_capture test/test_capture.cpp)
target_link_libraries(test_capture bbrt)
add_test(NAME capture COMMAND test_capture)
add_executable(test_capture_poc test/test_capture_poc.cpp)
add_test(NAME capture_poc_fail_closed COMMAND test_capture_poc --self-test)
add_test(NAME capture_poc_replay
         COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/test/capture_poc_integration.py $<TARGET_FILE:test_capture_poc>)
set_tests_properties(capture_poc_replay PROPERTIES
    ENVIRONMENT "CC=${CMAKE_C_COMPILER};BB_LOADER=$<TARGET_FILE:pbloader>")
# The proof above replays a case from the PoC's own serializer; this one replays a case written by
# runtime/include/runtime/recorder.hpp, the serializer a replacement actually calls.
add_test(NAME capture_recorder_replay
         COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/test/capture_recorder_replay.py $<TARGET_FILE:test_capture>)
set_tests_properties(capture_recorder_replay PROPERTIES
    ENVIRONMENT "CC=${CMAKE_C_COMPILER};BB_LOADER=$<TARGET_FILE:pbloader>")
# System library implementations, compiled in directly so the linker keeps every RT_SYSLIB entry
file(GLOB PB_TEST_SYSLIB CONFIGURE_DEPENDS ${PROJECT_SOURCE_DIR}/runtime/syslib/*.c)
add_executable(test_syslib test/test_syslib.c runtime/guest_mem.c runtime/process.c ${PB_TEST_SYSLIB})
target_include_directories(test_syslib PRIVATE runtime/include)
add_test(NAME syslib COMMAND test_syslib)

add_test(NAME tools COMMAND ${Python3_EXECUTABLE} -m unittest discover -s ${PROJECT_SOURCE_DIR}/test -p "test_*.py" -v)
set_tests_properties(tools PROPERTIES ENVIRONMENT "BB_LOADER=$<TARGET_FILE:pbloader>;BB_PBBOOT=$<TARGET_FILE:pbboot>")
add_test(NAME verify_self_test COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/verify.py --self-test)
add_test(NAME validate_functions COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/validate_functions.py)
add_test(NAME check_agnostic COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/check_agnostic.py)
add_test(NAME float_flags COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/check_float_flags.py ${CMAKE_BINARY_DIR})
add_test(NAME progress_readme COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/progress.py --check)
# Every recorded row carries a source pin that nothing recomputed until check_pins.py existed, and
# 3,012 of 21,129 were stale when it first ran. 2.2 s: three content caches in verification.py, not
# the defining-file index alone, are what make auditing the whole ledger cheaper than one test run.
add_test(NAME check_pins COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tools/check_pins.py)
# A gate whose only failure mode is "never finishes" is a gate that cannot fail. Three checks in
# this tree have already grown a cost proportional to the population they read -- a 507 s resolver,
# a 44.6 ms walk, and 1.07e9 regex searches in check_agnostic, which stopped completing quietly on
# the way from a few hundred ledger rows to 21,130. A per-test timeout turns that regression into a
# red test on the day it happens, without an operator watching, and each gate arms faulthandler
# (tools/stacks.py) so the red prints the frame that caused it.
set_tests_properties(
  hooks plugin host_hooks capture capture_poc_fail_closed capture_poc_replay
  capture_recorder_replay syslib verify_self_test validate_functions check_agnostic
  float_flags progress_readme check_pins
  PROPERTIES TIMEOUT 120)
set_tests_properties(tools PROPERTIES TIMEOUT 300)

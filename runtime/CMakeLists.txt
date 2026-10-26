# SPDX-License-Identifier: GPL-2.0-or-later
add_library(bbrt STATIC hooks.c process.c plugin.c host_hooks.c boundary_stub.c capture.c probe.c loader.c nid.c plugin_load.c)
target_include_directories(bbrt PUBLIC include)
# The executable loader on its own, for the verification harness (tools/harness.py loads it).
add_library(pbloader SHARED loader.c nid.c identity.c)
target_include_directories(pbloader PUBLIC include)
# A shared library links with undefined symbols by default; the loader's identity call was added
# without identity.c and only dlopen noticed. Make that a link error, as bbgame already does.
target_link_options(pbloader PRIVATE -Wl,--no-undefined)
# The boot harness: runs the executable's entry on our runtime (runtime/boot.c). System library
# implementations are compiled in directly, so the linker keeps every RT_SYSLIB entry.
file(GLOB PB_SYSLIB CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/syslib/*.c)
# -rdynamic so dladdr can name pbboot's own symbols when it faults; a raw offset is a number
# without a subject.
# hooks.c/capture.c: the recorder path. They were in bbrt only, so pbboot could install hooks and
# never invoke/record one -- a missing definition in a static library is not a link error, it is an
# `nm` result. The rung line measures this: `recorder-linked no` must flip to `yes` here, and the
# only way to learn whether they compile against pbboot's translation set is to put them in it.
add_executable(pbboot boot.c boot_call.c loader.c nid.c identity.c guest_mem.c process.c tls.c syslib_flight.c
                        boundary_stub.c plugin_load.c host_hooks.c hooks.c capture.c ${PB_SYSLIB})
target_include_directories(pbboot PRIVATE include)

target_link_options(pbboot PRIVATE -rdynamic)
# dlopen/dlsym for the plugin path: bbrt already links it, and a missing -ldl fails at link time only
# once something calls dlopen -- which is exactly the file that must not be silently absent.
# m: libc.c models _FSin on the host's sinf, and a host math call needs libm named -- an unlisted
# library fails at LINK time only, which is the failure mode that deletes the artifact rather than
# leaving a stale one (rc=127, indistinguishable from a missing binary to an unwary reader).
target_link_libraries(pbboot PRIVATE dl m)

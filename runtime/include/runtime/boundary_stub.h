/* The one segment that crosses the ABI boundary, in one place.

   Every path that hands control from guest code to a C body needs the same four things in the same
   order: run on the host's %fs, park the guest's rsp somewhere callee-saved, give the C body the
   ABI's 16-byte alignment, and put the guest's %fs and rsp back before returning. There are two such
   paths -- the import trampolines in boot.c and the hook installer in host_hooks.c -- and the only
   allowed difference between them is how the target address is materialised, because a trampoline
   lives in the mapped image and a host replacement does not. Both use the 14-byte absolute form, so
   today there is no difference at all.

   This used to be a hand-written prologue in one file. A single wrong ModRM digit (/3 WRGSBASE for
   /2 WRFSBASE) lived there for days and was only found by disassembling the shipped bytes; a second
   hand-written prologue would get the same treatment with no reader. Hence one emitter. */
#ifndef RT_BOUNDARY_STUB_H
#define RT_BOUNDARY_STUB_H

#include <stddef.h>
#include <stdint.h>

/* Writes the boundary segment at dst and returns its length, or 0 if it would not fit in capacity.
   The capacity is the caller's, not a global: the import path emits into a slot of TRAMPOLINE_SIZE and
   the hook path into a page allocator, so a single maximum would be a lie for one of them. With the
   bookkeeping word the per-thread segment is 76 bytes, which is why the shared maximum is 96 and not
   64 -- the 64 it used to be was exceeded by the import path every time, and nothing compared them.
   `per_thread` selects the selector: 0 bakes host_fs/guest_fs into movabs immediates (the test and
   harness form), 1 reads the current thread's state through %gs at execution. A child executing a
   stub emitted by main must have the second shape; the first is retained only because the harness
   links no TLS and a test must be able to derive bytes without one.
   No bookkeeping of its own: anything a caller wants recorded goes before this segment, in the
   caller's file, where its own tests can see it. */
#define RT_BOUNDARY_STUB_MAX 96

/* in_flight_addr is the ONLY optional element, and it is not part of the boundary crossing: it is the
   import path's bookkeeping word (rt_syslib_in_flight), cleared to "none" after the ABI segment is
   complete and before the ret, because the import path owns it and the hook path has no such word
   (it lives in boot.c, not in the library both paths link). Pass 0 to omit it. The test compares the
   two emissions up to this point, not through it: the ABI segment is identical by construction, and
   the tail difference is stated rather than discovered. */
size_t rt_write_boundary_stub(unsigned char *dst, size_t capacity, uint64_t target, uint64_t host_fs,
                              uint64_t guest_fs, uint64_t in_flight_addr, int per_thread);

/* The length the emitter will produce, so a caller can refuse before it writes and so the maximum above
   can be checked against arithmetic rather than against a comment. */
size_t rt_boundary_stub_size(uint64_t in_flight_addr, int per_thread);

#endif

/* The hook-only snapshot wrapper: `e9 rel32` to an unmodified boundary stub, 5 bytes; the capture form
   adds the entry counter and the six-register save, 88 baked or 86 per-thread. */
/* Called from the capture form. Six uint64_t parameters because that is what rdi..r9 already hold: no argument
   setup in the emitted bytes. Identity comes from __builtin_return_address(0), inside the per-site wrapper. */
void rt_capture_snapshot(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4, uint64_t a5);

size_t rt_snapshot_stub_size(int capturing, int per_thread);
size_t rt_write_snapshot_stub(unsigned char *dst, size_t capacity, uint64_t self_addr, uint64_t stub_addr,
                              uint64_t host_fs, uint64_t guest_fs, uint64_t entered_addr, int capturing,
                              int per_thread);
/* 86 of 96 in the per-thread capture form: 73 + 13 for the entry counter. The slot arithmetic must move before the bytes do. */

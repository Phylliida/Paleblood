/* SPDX-License-Identifier: GPL-2.0-or-later */
/* pbboot: runs a PS4 executable's entry on Paleblood's runtime, as far as the runtime goes.

     pbboot EBOOT.elf [--module MODULE.elf]... [--nids NID_DB.xml] [--status OUT.json]
            [--timeout SECONDS] [--trace]
     pbboot EBOOT.elf [--module MODULE.elf]... --imports [--nids NID_DB.xml]
            (list every import: importer, library, symbol, kind, provider, provider offset, size)

   The executable and any modules it ships with (--module, in start order) are mapped with our
   loader, each at its own base. An import is bound to a module's export with the same NID and
   library when one of the modules exports it, else to the runtime's implementation
   (runtime/syslib.h), else to a trampoline that stops the run and names it. Each module's entry
   (its constructors, then its start function) runs before the executable's entry.

   Every import call is counted, so the run also reports the boot milestones reached: the first
   call to each milestone's system functions (threads, files, input, audio, video out, GPU
   submission, the first flip; the runtime roadmap's order). Faults and timeouts are caught and
   reported with the faulting instruction's object and offset.

   Names: an import is "NID#library#module"; library names come from the object, symbol names
   from a public NID database (--nids, default $BB_NID_DB), else the NID is shown. */
#define _GNU_SOURCE
#include "runtime/guest_mem.h"
#include "runtime/inflight.h"
#include "runtime/boundary_stub.h"
#include "runtime/plugin_load.h"
#include "runtime/loader.h"
#include "runtime/nid.h"
#include "runtime/process.h"
#include "runtime/identity.h"
#include "runtime/address_spaces.h"
#include "runtime/guest.h"
#include "runtime/tls.h"
#include "runtime/boot_call.h"
#include "runtime/syslib.h"

#include <asm/prctl.h>
#include <errno.h>
#include <sys/stat.h>
#include <setjmp.h>
#include <execinfo.h>
#include <signal.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/random.h>
#include <sys/syscall.h>
#include <ucontext.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>

#define GUEST_BASE 0x800000000ull
#define MODULE_BASE 0x880000000ull
#define MODULE_STRIDE 0x4000000ull
#define MAX_OBJECTS 16
#define STACK_SIZE (16u << 20)
/* 104 bytes of stub: prologue, mark, in-flight index and the three argument words, the target call between
   two %fs writes, and the clear before returning. */
#define TRAMPOLINE_SIZE 220

static const struct {
    const char *name;
    const char *symbols[3];
} milestones[] = {
    {"entry", {NULL}},   /* reached when the executable makes its first import call */
    {"threads", {"scePthreadCreate"}},
    {"files", {"sceKernelOpen", "open"}},
    {"input", {"scePadOpen"}},
    {"audio", {"sceAudioOutOpen"}},
    {"video out", {"sceVideoOutOpen"}},
    {"gpu", {"sceGnmSubmitCommandBuffers"}},
    {"first flip", {"sceGnmSubmitAndFlipCommandBuffers", "sceVideoOutSubmitFlip"}},
};
#define MILESTONES (sizeof milestones / sizeof milestones[0])

enum provider { NONE, MODULE, RUNTIME, RUNTIME_UNRESOLVED, DATA_PROVIDER };

typedef struct {
    const char *path, *label;
    rt_elf *elf;
    unsigned char *image, *tramp, *data;
    uint64_t size;
    size_t imports;
    void **bound;            /* per import: host address, or NULL */
    enum provider *provider;
    int *provider_object;    /* MODULE: which object */
    size_t *provider_export; /* MODULE: which export */
    unsigned char *called;   /* per import: called at least once */
    uint64_t tls_check;      /* the shared %gs checker, in the trampoline mapping's spare slot */
} object;

static object objects[MAX_OBJECTS];
static size_t object_count;

enum outcome { RUNNING, UNIMPLEMENTED, FAULT, TIMEOUT, EXITED, RETURNED };
static const char *const outcome_names[] = {"running", "unimplemented", "fault", "timeout", "exited", "returned"};

static sigjmp_buf back_to_host;
static volatile enum outcome outcome = RUNNING;
static volatile uint32_t stopped_at;            /* object << 20 | import index of the unimplemented call */
static volatile uint64_t stopped_from;          /* the guest's return address of that call */
static volatile uint64_t fault_rip, fault_address, fault_fs;
static volatile uint64_t fault_regs[16];
static volatile int fault_signal;
static volatile int exit_code;

/* The guest PC that entered the import currently in flight, in RUNTIME space, or 0 when not captured (an
   import of any object but eboot). Bodies print it instead of their own return address. */
uint64_t rt_guest_call_pc(void);

_Static_assert(kPs4ImageBase == RT_EBOOT_BASE, "the PS4-space bias and the guest.h spelling must be one value");
_Static_assert(kGuestExecBase == GUEST_BASE, "the execution base is the loader's GUEST_BASE, not a second opinion");

/* Defined below, after rt_import_pc and the loader's accessors: this file's unimplemented() is above them. */
static uint64_t import_guest_pc(uint32_t which);
uint64_t rt_guest_call_pc(void) { return import_guest_pc(rt_syslib_in_flight); }

static int guest_rx_contains(uint64_t guest);

/* Entered from an unimplemented import's trampoline (edi = object << 20 | import). Never returns. */
static __attribute__((noinline)) void unimplemented(uint32_t which)
{
    /* The trampoline captured the guest's [rsp] before the crossing; this function was jumped to, so its
       own return address is a host address inside the stub. */
    stopped_from = import_guest_pc(which);
    stopped_at = which;
    outcome = UNIMPLEMENTED;
    siglongjmp(back_to_host, 1);
}

static void guest_exit(int code)
{
    /* The guest calls this, so it arrives with the guest block in %fs. One line, no pair: the siglongjmp
       returns into host code, which must find the host base already restored. */
    rt_tls_enter_host();
    exit_code = code;
    outcome = EXITED;
    siglongjmp(back_to_host, 1);
}

/* The interrupted stack, captured INSIDE the handler: glibc's backtrace() follows .eh_frame and steps through
   the kernel's signal frame into the faulting frames, which a manual rbp walk cannot do on an -O2 build.
   Only addresses are kept here -- dladdr and printing happen after the siglongjmp, outside the handler.

   OPT-IN, because backtrace() is not async-signal-safe: it walks the link map and takes glibc's
   dl_load_lock, and a fault that lands while the main thread holds that lock deadlocks *inside* the
   handler. It presents as a subprocess timeout with no output on a loaded machine and as a 4 ms pass
   when run alone -- which is how ctest caught it once and a standalone suite run did not. Everything
   else in this handler is a register store, a ucontext read, rt_tls_enter_host (one wrfsbase) and the
   siglongjmp; the formatting below runs after it, on the normal stack. */
static void *fault_frames[6];
static int fault_frame_count;
static int fault_backtrace_enabled;

/* A siglongjmp is only meaningful while the frame that set back_to_host is still live. Once
   run_guest() returns, the buffer points into a dead frame; a fault after that used to jump there
   anyway, land back in the reporter, fault again, and spin with no output -- a live-lock that looks
   like a hang. Guard the window, and when a fault arrives outside it say so and die: a one-line
   diagnosis instead of a hundred seconds of silence. */
static volatile sig_atomic_t fault_jmp_live;
static volatile sig_atomic_t fault_in_handler;

static void __attribute__((noreturn)) fault_outside_the_window(uint64_t pc)
{
    /* Async-signal-safe only: no printf, no dladdr, no lock. */
    static const char hex[] = "0123456789abcdef";
    char buf[96];
    const char *head = "pbboot: fault inside the fault reporter at 0x";
    size_t n = 0;
    while (*head) buf[n++] = *head++;
    for (int shift = 60; shift >= 0; shift -= 4) buf[n++] = hex[(pc >> shift) & 0xf];
    buf[n++] = '\n';
    /* write(2) directly: stdio is one of the locks this path must not take. */
    extern long write(int, const void *, unsigned long);
    /* -Wunused-result: the return is checked, and its value cannot change what we do next -- this path
       writes its last bytes and exits. Ignoring it silently was a build error hiding a stale binary. */
    const long written = write(2, buf, n);
    if (written != (long)n) { _exit(134); }
    _exit(134);
}

static void on_signal(int sig, siginfo_t *info, void *context)
{
    if (fault_in_handler || !fault_jmp_live)
        fault_outside_the_window((uint64_t)(uintptr_t)((const ucontext_t *)context)->uc_mcontext.gregs[REG_RIP]);
    fault_in_handler = 1;
    /* First statement: this handler runs on whatever %fs was installed when control was lost, and
       everything below it -- dladdr, snprintf, printf -- is host code that needs the host base. */
    /* The %fs this fault happened on. It must be read BEFORE rt_tls_enter_host() below, which is the very
       act that would make every fault look like it happened on the host: the signal frame carries %fs's
       selector and not its base (REG_FSBASE is not in gregs), so a live ARCH_GET_FS here is the only
       record of it. A host body running on the guest TCB reads zeros for every glibc TLS slot, and the
       first dereference of what those zeros point at faults at exactly 0x0. */
    {
        uint64_t base = 0;
        if (syscall(158, 0x1003UL, &base) == 0) fault_fs = base;  /* ARCH_GET_FS */
    }
    rt_tls_enter_host();
    fault_frame_count = fault_backtrace_enabled ? backtrace(fault_frames, 6) : 0;
    const ucontext_t *uc = context;
    if (sig == SIGALRM) {
        outcome = TIMEOUT;
    } else {
        outcome = FAULT;
        fault_signal = sig;
        fault_address = (uint64_t)(uintptr_t)info->si_addr;
    }
    /* Registers, not reasoning about instructions "a few bytes before" the PC: si_addr plus RIP plus the
       operand registers answer, in one run, whether the deref used a null base, whether it was an indirect
       call through a null slot, or whether si_addr was never the operand. */
    for (int r = 0; r < 16; r++) fault_regs[r] = (uint64_t)uc->uc_mcontext.gregs[r];
    fault_rip = (uint64_t)uc->uc_mcontext.gregs[REG_RIP];
    siglongjmp(back_to_host, 1);
}



/* Runs fn until it returns, exits, faults, times out or reaches an unimplemented import. Kept
   apart from main so that no caller state is live across the jump back. */
/* Set only when run_guest() is actually reached; the atexit reporter reads it. Declared here because the
   reporter lives below and a refusal before the guest starts must not print a count of zero. */
static int guest_entered;

static __attribute__((noinline)) void run_guest(void *fn, void *a, void *b, void *c, void *stack_top, int timeout)
{
    guest_entered = 1;
    outcome = RUNNING;
    fault_in_handler = 0;
    fault_jmp_live = 1;
    if (!sigsetjmp(back_to_host, 1)) {
        alarm((unsigned)timeout);
        rt_boot_call(fn, a, stack_top, b, c);
        outcome = RETURNED;
    }
    /* Past this point the buffer is dead: every fault from here on is reported, not jumped from. */
    fault_jmp_live = 0;
    fault_in_handler = 0;
    alarm(0);
}

/* Each import's call goes through a trampoline: mark it called, then jump to the provider, or
   into unimplemented() with the object and import. r11 is scratch in the System V convention and
   carries no argument; rax is left alone (variadic calls pass a count in al). */
/* Which syslib body is executing, and the three argument words it received. Set by the shared prologue and
   CLEARED before the stub returns, so "the fault happened inside #39" and "the fault happened after #39
   returned" are different readings rather than the same one -- a stale index is a claim, not a measurement. */
/* Slots 0..2 are the guest's rdi/rsi/rdx. There is no slot 3: the guest return address is stored per
   import in rt_import_pc[which][0] below, where the index and the slot are the same word. A fourth
   slot was declared and never written (the emitter stores exactly three words), so a reader of
   rt_syslib_args[3] would have read a zero the trampoline never produced -- a name in a table with
   neither a writer nor a reader. ONE global, overwritten per call, read at the reporting site -- so
   re-entrancy is a known limit: the last call wins, and a nested import would overwrite its caller's
   record. */
volatile uint64_t rt_syslib_args[3];

/* One row per import, not a ring: a ring write needs a second scratch register, and here r11 holds &args while
   rcx/r8/r9 are live arguments -- a ring that eats arguments is worse than a slot that misses one. `which` is a
   compile-time literal in each trampoline, so the emitter bakes `movabs r11, &rt_import_pc[which]` and needs no
   index arithmetic at all. pc in [0], count in [8]: a nonzero count is an import the guest actually called,
   which is the `called` half of the called/served split this runtime has owed for many slices. */
#define RT_IMPORT_PC_MAX 4096
volatile uint64_t rt_import_pc[RT_IMPORT_PC_MAX][2];

/* The guest PC that entered this import, as captured by the trampoline from the guest's own [rsp] BEFORE the
   crossing. `__builtin_return_address(0)` here would be a host address inside the stub: a value reported in a
   space it does not live in, which is exactly the defect this replaces. The capture is keyed by
   (object << 20 | index) and is only stored when that key is < RT_IMPORT_PC_MAX, so an import of any object
   but eboot reports ABSENCE rather than a plausible neighbour. */
static uint64_t import_guest_pc(uint32_t which)
{
    if (which >= RT_IMPORT_PC_MAX) return 0;
    return (uint64_t)rt_import_pc[which][0];
}

/* Nonzero only if `guest` lands inside one of eboot's PF_X segments, read from the executable's own program
   headers -- not a constant. A captured address that fails this is printed as an error, never silently
   formatted as if it were a guest site. */
static int guest_rx_contains(uint64_t guest)
{
    if (!objects[0].elf) return 0;
    /* The RUNTIME base of object 0, not EBOOT_BASE: eboot executes at GUEST_BASE (0x800000000) and the
       captured return address lives in that space. Comparing it against EBOOT_BASE (0x400000) rejected a
       true guest address -- a value compared in a space other than the one it lived in, which is the same
       defect this field exists to remove, so the base is read from the object rather than typed. */
    const uint64_t base = (uint64_t)(uintptr_t)objects[0].image;
    const size_t n = rt_elf_load_count(objects[0].elf);
    const rt_elf_load *ls = rt_elf_loads(objects[0].elf);
    for (size_t i = 0; i < n; i++) {
        if (!(ls[i].flags & 1u)) continue;
        const uint64_t lo = base + ls[i].vaddr;
        const uint64_t hi = lo + rt_elf_load_filesz(objects[0].elf, i);
        if (guest >= lo && guest < hi) return 1;
    }
    return 0;
}

static void write_trampoline(unsigned char *t, unsigned char *mark, uint32_t which, uint64_t target,
                             uint64_t check_addr)
{
    unsigned char *p = t;
    const uint64_t m = (uint64_t)(uintptr_t)mark;
    *p++ = 0x49, *p++ = 0xbb, memcpy(p, &m, 8), p += 8;                /* movabs r11, mark */
    *p++ = 0x41, *p++ = 0xc6, *p++ = 0x03, *p++ = 0x01;               /* mov byte [r11], 1 */
    {
        const uint64_t inf = (uint64_t)(uintptr_t)&rt_syslib_in_flight;
        const uint64_t arg = (uint64_t)(uintptr_t)&rt_syslib_args;
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &inf, 8), p += 8;          /* movabs r11, &in_flight */
        *p++ = 0x41, *p++ = 0xc7, *p++ = 0x03, memcpy(p, &which, 4), p += 4; /* mov dword [r11], which */
        *p++ = 0x49, *p++ = 0xbb, memcpy(p, &arg, 8), p += 8;          /* movabs r11, &args */
        *p++ = 0x49, *p++ = 0x89, *p++ = 0x7b, *p++ = 0x00;            /* mov [r11+0], rdi */
        *p++ = 0x49, *p++ = 0x89, *p++ = 0x73, *p++ = 0x08;            /* mov [r11+8], rsi */
        *p++ = 0x49, *p++ = 0x89, *p++ = 0x53, *p++ = 0x10;            /* mov [r11+16], rdx */
        /* The guest return address, AFTER the in-flight index store: a fault in that store must not pair a
           stale index with a fresh PC. [rsp] is a return address only for a `call` -- a guest tail call
           (`jmp`) leaves the OUTER caller's return address here, which attributes the PC to the wrong
           function. That is why the join prints "PC outside every function extent: N" as its own line.
           rax is caller-saved and holds the return value anyway, so nothing live is clobbered. */
        if (which < RT_IMPORT_PC_MAX) {
            const uint64_t slot = (uint64_t)(uintptr_t)&rt_import_pc[which][0];
            *p++ = 0x48, *p++ = 0x8b, *p++ = 0x04, *p++ = 0x24;        /* mov rax, [rsp] */  /* 0x48 not 0x49: REX.B extends the SIB base, so 49 8b 04 24 is [r12] and only 48 8b 04 24 is [rsp] */
            *p++ = 0x49, *p++ = 0xbb, memcpy(p, &slot, 8), p += 8;     /* movabs r11, &pc[which] */
            *p++ = 0x49, *p++ = 0x89, *p++ = 0x03;                     /* mov [r11], rax  (this import's PC) */
            *p++ = 0x49, *p++ = 0xff, *p++ = 0x43, *p++ = 0x08;        /* incq [r11+8]    (and its count) */
        }
    }
    if (!target) {
        *p++ = 0xbf, memcpy(p, &which, 4), p += 4;                     /* mov edi, which */
        target = (uint64_t)(uintptr_t)unimplemented;
    }
    /* The crossing itself is emitted by runtime/boundary_stub.c, which host_hooks.c also calls: one
       emitter, so the /2-vs-/3 class cannot come back in a second hand-written prologue. The %fs
       readback dumps that used to sit here were an instrument for a question that is closed, and an
       instrument left in a report is an instrument nobody re-tests. */
    {
        /* The capacity is this slot's remaining budget, so the bound is checked before the first
           store instead of after it. An addition to the import path must displace something: the slot
           is TRAMPOLINE_SIZE bytes and the emitter returns 0 rather than overrun it. */
        if (getenv("BB_TLS_TRACE") && ((which & 0xfffffu) == 40 || (which & 0xfffffu) < 2)) {
            /* The stub no longer bakes a base: it reads the executing thread's state through %gs. The
               accessor values still print as main's record, which is what a child must not inherit. */
            unsigned long long fs = 0;
            syscall(158, 0x1003UL, &fs);
            fprintf(stderr, "tls trace trampoline %u: selector gs, main record host_fs %#llx guest_fs %#llx "
                    "current fs %#llx\n",
                    which, (unsigned long long)rt_tls_host_base(), (unsigned long long)rt_tls_guest_base(), fs);
        }
        const size_t room = TRAMPOLINE_SIZE - (size_t)(p - t);
        const size_t stub = rt_write_boundary_stub(p, room, target, rt_tls_host_base(),
                                                   rt_tls_guest_base(),
                                                   (uint64_t)(uintptr_t)&rt_syslib_in_flight, 1,
                                                   check_addr);
        if (stub == 0 || stub > room) {
            /* A fatal that omits its operands cannot be diagnosed from the log: the next reader needs
               the slot, the prefix already emitted, the room left and what the emitter returned. */
            char msg[256];
            snprintf(msg, sizeof msg,
                     "boundary stub does not fit trampoline slot (which=%u prefix=%zu room=%zu "
                     "TRAMPOLINE_SIZE=%d stub=%zu)",
                     which, (size_t)(p - t), room, TRAMPOLINE_SIZE, stub);
            rt_fatal("trampoline", msg);
        }
        p += stub;
        if (getenv("BB_RECORD_ADDR")) {
            /* One declaration in the tree is not one copy at runtime: the emitted store carries a LITERAL address,
               so if a trampoline were emitted by another object the store would land in that object's array and
               read exactly like a genuine zero. Print the reporter's address; the dump prints the literal. */
            fprintf(stderr, "record: &rt_syslib_args=%p &in_flight=%p\n",
                    (void *)(uintptr_t)rt_syslib_args, (void *)(uintptr_t)&rt_syslib_in_flight);
        }
        if (getenv("BB_TRAMPOLINE_VERBOSE")) {
            fprintf(stderr, "trampoline %u: %zu of %d bytes, %zu left\n", which,
                    (size_t)(p - t), TRAMPOLINE_SIZE, (size_t)(TRAMPOLINE_SIZE - (p - t)));
            /* A byte question deserves a dump, not a chain of reasoning about what the emitter does. */
            fprintf(stderr, "trampoline %u bytes:", which);
            for (size_t i = 0; i < (size_t)(p - t) && i < 72; i++) fprintf(stderr, " %02x", t[i]);
            fprintf(stderr, "\n");
        }
    }
}

static void rt_import_pc_report(void)
{
    unsigned long long nz = 0, total = 0;
    for (unsigned i = 0; i < RT_IMPORT_PC_MAX; i++) {
        if (rt_import_pc[i][1]) { nz++; total += rt_import_pc[i][1]; }
    }
    /* Sum over EVERY object: object_count is 2 here (eboot, libc), and summing only the first would print a
       number that looks right and is half the population. If the loader data is unreachable, print n/a -- an
       unreachable subject must not print as a number. */
    unsigned long long boot_called = 0;
    /* No subject is not "a subject with zero imports": with object_count == 0 the loop never ran, boot_known
       stayed 1, and the reporter printed boot called=0 for a run that had nothing to count. Same rule as the
       NULL-elf guard below, one branch over -- an unreachable subject must not print as a number. */
    int boot_known = guest_entered && object_count > 0;
    int not_entered = !guest_entered;
    for (size_t k = 0; k < object_count; k++) {
        /* An ELF that never opened is NULL, not "zero imports": this reporter runs from atexit, so a failed
           load reached here with objects[0].elf == NULL and dereferenced it -- the refusal printed and then
           the process died of SIGSEGV (rc=139), which is a crash wearing a refusal's clothes. */
        if (!objects[k].elf) { boot_known = 0; break; }
        const size_t n = rt_elf_import_count(objects[k].elf);
        /* Zero imports is a known zero, not an unreachable subject: a module that exports but does not
           import makes n == 0 and leaves `called` NULL, and the old guard printed boot called=n/a for a
           run whose eboot imports were all counted. Only a missing array with n > 0 is unknown. */
        if (!n) continue;
        if (!objects[k].called) { boot_known = 0; break; }
        for (size_t i = 0; i < n; i++) boot_called += objects[k].called[i] ? 1u : 0u;
    }
    if (boot_known)
        fprintf(stderr, "imports called: %llu rows, %llu calls total, boot called=%llu\n", nz, total, boot_called);
    else if (not_entered)
        fprintf(stderr, "imports called: %llu rows, %llu calls total, boot called=n/a (guest not entered)\n", nz, total);
    else
        fprintf(stderr, "imports called: %llu rows, %llu calls total, boot called=n/a\n", nz, total);
    for (unsigned pass = 0; pass < 20; pass++) {
        unsigned best = RT_IMPORT_PC_MAX;
        for (unsigned i = 0; i < RT_IMPORT_PC_MAX; i++) {
            if (!rt_import_pc[i][1]) continue;
            if (best == RT_IMPORT_PC_MAX || rt_import_pc[i][1] > rt_import_pc[best][1]) best = i;
        }
        if (best == RT_IMPORT_PC_MAX) break;
        fprintf(stderr, "  #%u pc %#llx count %llu\n", best,
                (unsigned long long)rt_import_pc[best][0], (unsigned long long)rt_import_pc[best][1]);
        rt_import_pc[best][1] = 0;   /* consume, so the next pass finds the next-largest; nz/total already taken */
    }
}


typedef struct {
    char nid[RT_NID_SIZE];
    const char *symbol;
} nid_name;

static int by_nid(const void *a, const void *b) { return strcmp(((const nid_name *)a)->nid, ((const nid_name *)b)->nid); }

/* The NID database: <Entry obf="NID" sym="name"/> lines. *out sorted by NID.
   Three states, signed because they must be: 0 = no path was supplied (absent is legitimate; the boot runs
   with unresolved imports as usual and says nothing), -1 = a path WAS supplied and could not be read whole,
   >0 = that many names. -1 cannot be stored in size_t: SIZE_MAX is truthy, so the caller would bsearch() a
   NULL table. Allocation failure is -1 for the same family of reason -- a partial table returned as a count
   is a table the boot believes is complete. */
static ssize_t read_nid_db(const char *path, nid_name **out, char **text, size_t *skipped_out)
{
    *skipped_out = 0;
    *out = NULL;
    *text = NULL;
    if (!path) return 0;
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    struct stat st;
    if (fstat(fileno(f), &st) == 0 && S_ISDIR(st.st_mode)) {
        /* A directory opens and fseek/ftell may then report a nonsensical length, which surfaces as ENOMEM
           from the malloc -- the wrong name for the refusal. Name the state directly. */
        fclose(f);
        errno = EISDIR;
        return -1;
    }
    int saved;
    if (fseek(f, 0, SEEK_END) != 0) { saved = errno ? errno : EIO; fclose(f); errno = saved; return -1; }
    const long size = ftell(f);
    if (size < 0) { saved = errno ? errno : EIO; fclose(f); errno = saved; return -1; }
    if (fseek(f, 0, SEEK_SET) != 0) { saved = errno ? errno : EIO; fclose(f); errno = saved; return -1; }
    char *t = malloc((size_t)size + 1);
    if (!t) { fclose(f); errno = ENOMEM; return -1; }
    if (fread(t, 1, (size_t)size, f) != (size_t)size) {
        /* A short read is not a count of the names that happened to parse: an I/O error and a file shorter
           than its own length both leave an incomplete table, and a partial table quoted as complete is the
           defect this function exists to stop. */
        saved = ferror(f) ? (errno ? errno : EIO) : EIO;
        fclose(f);
        free(t);
        errno = saved;
        return -1;
    }
    fclose(f);
    t[size] = 0;
    size_t n = 0, cap = 0, skipped = 0;
    nid_name *names = NULL;
    for (char *p = strstr(t, "obf=\""); p; p = strstr(p, "obf=\"")) {
        char *nid = p + 5, *end = strchr(nid, '"');
        /* Both searches are bounded by the NEXT entry: an unmatched obf=" with no sym of its own must not
           pair with the following entry's symbol, take p past it, and swallow a valid name. The skip count
           would then say "one malformed, no valid lost", which is the partial-table class again. */
        char *next = end ? strstr(end, "obf=\"") : NULL;
        char *sym = end ? strstr(end, "sym=\"") : NULL;
        if (next && (!sym || sym >= next)) sym = NULL;
        char *send = sym && (!next || strchr(sym + 5, '"') < next) ? strchr(sym + 5, '"') : NULL;
        if (!send) {
            /* A malformed entry must not truncate the table: skip it, keep every valid entry after it, and
               COUNT it, so the caller cannot quote the result as complete. `!end` means the file ends inside
               the attribute, after which nothing can parse. A `break` here was the realloc/short-read class
               one branch over: a partial table returned as the whole one. */
            skipped++;
            if (!end) break;
            p = end + 1;
            continue;
        }
        p = send + 1;
        if (end - nid != RT_NID_SIZE - 1) { skipped++; continue; }
        if (n == cap) {
            cap = cap ? 2 * cap : 4096;
            nid_name *grown = realloc(names, cap * sizeof *names);
            if (!grown) { free(names); free(t); errno = ENOMEM; return -1; }
            names = grown;
        }
        memcpy(names[n].nid, nid, RT_NID_SIZE - 1);
        names[n].nid[RT_NID_SIZE - 1] = 0;
        *send = 0;
        names[n].symbol = sym + 5;
        n++;
    }
    if (n) qsort(names, n, sizeof *names, by_nid);
    *out = names;
    *text = t;
    *skipped_out = skipped;
    return (ssize_t)n;
}

static nid_name *db;
static ssize_t db_count;   /* signed: -1 unreadable, 0 absent, >0 names; SIZE_MAX would be truthy */

static const char *symbol_of(const char *import)
{
    nid_name key = {{0}, NULL};
    memcpy(key.nid, import, RT_NID_SIZE - 1);
    const nid_name *hit = (db && db_count > 0) ? bsearch(&key, db, (size_t)db_count, sizeof *db, by_nid) : NULL;
    return hit ? hit->symbol : NULL;
}

static int same_nid(const char *a, const char *b)
{
    return !strncmp(a, b, RT_NID_SIZE - 1) && a[RT_NID_SIZE - 1] == '#' && b[RT_NID_SIZE - 1] == '#';
}

static void json_string(FILE *f, const char *s)
{
    fputc('"', f);
    for (; s && *s; s++) {
        if (*s == '"' || *s == '\\') fputc('\\', f);
        if ((unsigned char)*s < 0x20) fprintf(f, "\\u%04x", *s);
        else fputc(*s, f);
    }
    fputc('"', f);
}

static const char *base_name(const char *path)
{
    const char *slash = strrchr(path, '/');
    return slash ? slash + 1 : path;
}

/* An export whose value lands past a load's p_filesz but inside its p_memsz names a .bss object:
   the image reserves it and nothing in the file or in the relocation table initialises it. */
static int export_unfilled(const rt_elf *e, size_t index)
{
    const uint64_t v = rt_elf_export_value(e, index);
    const rt_elf_load *loads = rt_elf_loads(e);
    for (size_t i = 0; i < rt_elf_load_count(e); i++) {
        const uint64_t base = loads[i].vaddr, filesz = rt_elf_load_filesz(e, i);
        if (v >= base && v < base + filesz) return 0;
        if (v >= base + filesz && v < base + loads[i].memsz) return 1;
    }
    return 0;
}

/* Binding: modules' exports first, then the runtime's implementations. */
/* A DATA import needs an ADDRESS, not code, so the syslib table -- which supplies function pointers --
   cannot serve one, and boot's module lookup only finds data in objects that are loaded. That gap is
   why every unbound object import used to be a private zero page: readable, plausibly shaped, and a
   silent lie. A data provider is a row here, with the kind spelled out, for the same reason the syslib
   table spells out real/modelled/noop/refused.

   `__stack_chk_guard` (libkernel, NID f7uOxY9mM1U) is the FIRST data import this guest reads: measured
   at eboot+0x2083ff7, with BB_DATA_GUARD on. Served as zeroes, the value stored in a prologue and the
   value compared in an epilogue are both zero, so every stack-protector check in the guest passes --
   the protector is a DETECTOR, so nothing breaks; smashes simply stop being reportable, and a boot that
   reaches a wall is thereafter evidence about control flow and no evidence about memory.

   Modelled, not real: a host CSPRNG value with the ABI's zero terminator byte (a string overflow hits
   that byte first), one value per process. The guest gets a canary that FIRES, which is what the ground
   truth requires; what it does not get is the value the real kernel would have chosen, and that is the
   whole of the difference. The value is deliberately not printed: a canary in a log protects nothing. */
static unsigned char stack_chk_guard[8] __attribute__((aligned(8)));
static int stack_chk_guard_ready;

static void init_stack_chk_guard(void)
{
    uint64_t v = 0;
    if (getrandom(&v, sizeof v, 0) != (ssize_t)sizeof v)
        rt_fatal("imports", "f7uOxY9mM1U (__stack_chk_guard): no entropy source. Refusing to install a "
                            "predictable canary; a zero canary is the defect this provider exists for");
    v &= ~0xffull;
    if (!v) v = 0x0101010101010100ull;
    memcpy(stack_chk_guard, &v, sizeof v);
    stack_chk_guard_ready = 1;
    fprintf(stderr, "pbboot: data provider __stack_chk_guard -> %p (modelled: host CSPRNG, ABI "
                    "terminator byte 0, one value per process; not printed)\n", (void *)stack_chk_guard);
}

struct data_provider { const char *library, *nid, *what; void *address; size_t size; };
static const struct data_provider data_providers[] = {
    {"libkernel", "f7uOxY9mM1U", "__stack_chk_guard", stack_chk_guard, sizeof stack_chk_guard},
};

static void resolve(object *o)
{
    for (size_t i = 0; i < o->imports; i++) {
        const char *name = rt_elf_import_name(o->elf, i), *library = rt_elf_import_library(o->elf, i);
        if (getenv("BB_BIND_DUMP"))
            fprintf(stderr, "bind %zu %s %s\n", i, name, library ? library : "(none)");
        for (size_t m = 1; m < object_count && !o->bound[i]; m++) {
            if (&objects[m] == o) continue;
            for (size_t e = 0; e < rt_elf_export_count(objects[m].elf); e++) {
                const char *lib = rt_elf_export_library(objects[m].elf, e);
                if (same_nid(name, rt_elf_export_name(objects[m].elf, e)) && library && lib && !strcmp(library, lib)) {
                    if (rt_elf_import_kind(o->elf, i) == RT_ELF_IMPORT_DATA && export_unfilled(objects[m].elf, e)) {
                        fprintf(stderr,
                                "pbboot: %s imports %s from %s: provider=data-unfilled "
                                "(export outside p_filesz, inside p_memsz)\n",
                                o->label, name, objects[m].label);
                        break; /* fail closed: leave it unbound rather than hand over a zeroed object */
                    }
                    o->bound[i] = objects[m].image + rt_elf_export_value(objects[m].elf, e);
                    o->provider[i] = MODULE;
                    o->provider_object[i] = (int)m;
                    o->provider_export[i] = e;
                    break;
                }
            }
        }
        for (const rt_syslib_entry *s = rt_syslib_begin(); !o->bound[i] && s && s != rt_syslib_end(); s++) {
            char nid[RT_NID_SIZE + 1];
            rt_nid(s->symbol, nid);
            nid[RT_NID_SIZE - 1] = '#', nid[RT_NID_SIZE] = 0;
            if (!strncmp(name, nid, RT_NID_SIZE) && library && !strcmp(library, s->library)) {
                o->bound[i] = s->fn;
                o->provider[i] = s->capability == RT_SYSLIB_CAPABILITY_IMPLEMENTED
                                     ? RUNTIME
                                     : RUNTIME_UNRESOLVED;
            }
        }
        /* A data provider is consulted only for a DATA import: handing an object's address to a function
           import would be a different lie of the same family. */
        for (size_t d = 0; !o->bound[i] && library && d < sizeof data_providers / sizeof *data_providers; d++) {
            char nid[RT_NID_SIZE + 1];
            snprintf(nid, sizeof nid, "%s#", data_providers[d].nid);
            if (strcmp(library, data_providers[d].library) || strncmp(name, nid, RT_NID_SIZE)) continue;
            if (rt_elf_import_kind(o->elf, i) != RT_ELF_IMPORT_DATA) continue;
            if (!stack_chk_guard_ready) init_stack_chk_guard();
            o->bound[i] = data_providers[d].address;
            o->provider[i] = DATA_PROVIDER;
        }
        /* The partition, not the total: a resolved slot is bundled, syslib, or a third provider nobody has
           named, and only printing it per (object, nid) can tell those apart. A total that does not equal
           the sum of its named parts is a total about nothing. */
        /* The predicate behind each class, written where it is computed, because a residual cannot be
           interpreted until the classes and the trampoline form are defined against the same predicate:
             bundled            MODULE             -- a NID+library match in another mapped object, and not
                                                     the data-unfilled case that deliberately leaves it unbound
             syslib             RUNTIME            -- a NID+library match in rt_syslib, capability IMPLEMENTED
             syslib-unresolved  RUNTIME_UNRESOLVED -- matched in rt_syslib, capability NOT implemented; it is
                                                     still bound to `s->fn`, which is what the trampoline sees
             none               NONE               -- matched in neither table, so bound[] stays 0
           The trampoline's own predicate is `target != 0`, i.e. `bound[i] != 0`, and it is emitted only for
           FUNCTION imports. Therefore: 126 B <=> bound != 0, and 131 B <=> bound == 0, over functions only.
           The kind is printed beside the class so that the two populations can be intersected rather than
           compared in aggregate. */
        if (getenv("BB_IMPORT_PROVIDER_VERBOSE"))
            fprintf(stderr, "provider %s %s %s %s bound=%s\n", o->label, name,
                    o->provider[i] == MODULE            ? "bundled"
                    : o->provider[i] == RUNTIME         ? "syslib"
                    : o->provider[i] == RUNTIME_UNRESOLVED ? "syslib-unresolved"
                    : o->provider[i] == DATA_PROVIDER       ? "data-provider"
                                                          : "none",
                    rt_elf_import_kind(o->elf, i) == RT_ELF_IMPORT_DATA ? "data" : "function",
                    (o->bound[i] || name[0] == 0) ? "" : (o->bound[i] ? "set" : "null"));
    }
}


static uint64_t bind_import(void *user, size_t index, int kind)
{
    const object *o = user;
    if (kind == RT_ELF_IMPORT_DATA)
        return o->bound[index] ? (uint64_t)(uintptr_t)o->bound[index] : (uint64_t)(uintptr_t)(o->data + 4096 * index);
    return (uint64_t)(uintptr_t)(o->tramp + TRAMPOLINE_SIZE * index);
}

/* Where an address is: "label+0xoffset", or "host+0x..." */
static void where(uint64_t address, char *out, size_t size)
{
    for (size_t k = 0; k < object_count; k++) {
        const uint64_t base = (uint64_t)(uintptr_t)objects[k].image;
        if (address >= base && address < base + objects[k].size) {
            const uint64_t v = address - base;
            /* BOTH coordinates, because they differ by kPs4ImageBase and a reader quoting one against a
               catalogue written in the other is the mistake this campaign made twice in one hour. */
            snprintf(out, size, "%s+0x%llx (catalogue 0x%llx)", objects[k].label, (unsigned long long)v,
                     (unsigned long long)rt_vaddr_to_catalogue(v));
            return;
        }
    }
    snprintf(out, size, "host+0x%llx", (unsigned long long)address);
}

static const char *usage =
    "usage: pbboot EBOOT.elf [--module MODULE.elf]... [--nids NID_DB.xml] [--status OUT.json] [--timeout S] [--trace]\n"
    "       pbboot EBOOT.elf [--module MODULE.elf]... --imports [--nids NID_DB.xml]\n";

/* The syslib bodies' self-tests, in libc.c; declared here so the linker, not a header, is what proves
   the symbol exists in the target that runs (runtime/syslib/libc.c). */
extern int rt_libc_guard_selftest(void *guard);

int main(int argc, char **argv)
{
    {
        /* A duplicate resolves by link order, so the policy that runs is one nobody chose. Refuse rather
           than pick: this is the one place where the second registration is always the honest one. */
        unsigned dup = rt_syslib_check_unique(rt_syslib_begin(), rt_syslib_end());
        if (dup)
            rt_fatal("syslib", "duplicate (library, symbol) registrations (pairs listed above): the first "
                               "entry wins on section order and the second never runs");
    }
    rt_announce_identity();
    /* TLS is laid out after the loading loop below: it needs the executable open. A layout placed here
       (where it lived until now) runs with objects[0].elf == NULL on every boot, so its scan never fired
       and the hardcoded default 0x4a0 was the only layout the runtime ever had. */
    {
        void *p = malloc(48);
        fprintf(stderr, "pbboot: heap probe at init (before any guest code): malloc(48) = %p\n", p);
        free(p);
    }
    atexit(rt_import_pc_report);
    fault_backtrace_enabled = getenv("BB_FAULT_BACKTRACE") != NULL;
    const char *nid_path = getenv("BB_NID_DB"), *status_path = NULL;
    const char *nid_source = nid_path ? "BB_NID_DB" : NULL;
    int timeout = 30, trace = 0, list = 0, selftest_guard = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--nids") && i + 1 < argc) { nid_path = argv[++i]; nid_source = "--nids"; }
        else if (!strcmp(argv[i], "--status") && i + 1 < argc) status_path = argv[++i];
        else if (!strcmp(argv[i], "--timeout") && i + 1 < argc) timeout = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--module") && i + 1 < argc && object_count && object_count < MAX_OBJECTS)
            objects[object_count++].path = argv[++i];
        else if (!strcmp(argv[i], "--trace")) trace = 1;
        else if (!strcmp(argv[i], "--selftest-guard")) selftest_guard = 1;
        else if (!strcmp(argv[i], "--imports")) list = 1;
        else if (argv[i][0] != '-' && !object_count) objects[object_count++].path = argv[i];
        else {
            fputs(usage, stderr);
            return 3;   /* 3 = precondition (usage), never 2: 2 is the timeout word and a bad invocation is not
                           a run that ran out of time. The wrapper vocabulary and this binary now agree. */
        }
    }
    if (!object_count) {
        fputs(usage, stderr);
        return 3;
    }
    /* The subject, from the binary: a direct pbboot invocation attributed only the runtime before this, while
       tools/boot.sh hashed the ELF. Printed for every object, before any of them is opened, so a refusal still
       names the file it refused. Two mechanisms (sha256sum in the wrapper, this hash) agreeing on eboot is the
       only agreement worth quoting; either alone is one instrument. */
    char error[512];
    for (size_t k = 0; k < object_count; k++) {
        object *o = &objects[k];
        o->label = k ? base_name(o->path) : "eboot";
        error[0] = '\0';
        FILE *stream = fopen(o->path, "rb");
        if (!stream) {
            fprintf(stderr, "pbboot: %s: cannot open: %s\n", o->path, strerror(errno));
            return 3;
        }
        /* The hash comes back from the SAME read the loader parses. Printed before the parse verdict, so a
           refused image still names the bytes that were refused. The loader's reason is printed on EVERY
           refusal: an empty hash says "no bytes were read", never why, and returning at the hash branch
           swallowed the truncated:/read error: sentences this seam exists to expose. */
        char gh[13];
        o->elf = rt_elf_open_stream(stream, o->path, gh, error, sizeof error);
        if (gh[0])
            fprintf(stderr, "guest sha256 %s  (%s)\n", gh, o->path);
        else
            fprintf(stderr, "pbboot: guest sha256 unreadable for %s (no hash computed; the loader refused before hashing)\n", o->path);
        if (!o->elf) {
            fprintf(stderr, "pbboot: %s\n", error);
            return 3;
        }
        o->size = rt_elf_image_size(o->elf);
        if (k && o->size > MODULE_STRIDE) {
            fprintf(stderr, "pbboot: %s: image larger than a module slot\n", o->path);
            return 3;
        }
        /* the address the object will have, known before mapping so exports can be bound */
        o->image = (unsigned char *)(uintptr_t)(k ? MODULE_BASE + (k - 1) * MODULE_STRIDE : GUEST_BASE);
        /* The executable's segments and its mapping are what a syslib body consults before writing
           guest memory. Object 0 is the executable the guest runs in; a module is not the segment
           authority for a pointer the guest computed. Noted before any guest code runs, so the note is
           live for the first import call. The address comes from here because plugin.c owns rt_image
           and pbboot does not link it -- the linker named that, which is why this is not a global. */
        if (k == 0) rt_map_note(o->elf, o->image);
        o->imports = rt_elf_import_count(o->elf);
        const size_t n = o->imports ? o->imports : 1;
        o->bound = calloc(n, sizeof *o->bound);
        o->provider = calloc(n, sizeof *o->provider);
        o->provider_object = calloc(n, sizeof *o->provider_object);
        o->provider_export = calloc(n, sizeof *o->provider_export);
        o->called = calloc(n, 1);
        rt_elf_set_tls_module_id(o->elf, k + 1);
    }

    /* The guest's TLS layout, derived from the executable that declares it, now that it is open. It has to
       land before the trampolines because a child must find a TCB through %gs at execution; the stub no
       longer bakes a base as a literal.
       The main executable is the module whose @tpoff constants the guest's own code uses, so its memsz is
       the one a variant-II layout must satisfy: image sits exactly memsz below the TCB, because any padding
       there shifts every TLS variable to a different address. */
    {
        const rt_elf_tls *t = rt_elf_tls_segment(objects[0].elf);
        const unsigned char *img = t->filesz ? objects[0].image + (t->vaddr - RT_EBOOT_BASE) : NULL;
        rt_tls_layout(img, (unsigned)t->filesz, (unsigned)t->memsz);
        if (t->memsz)
            fprintf(stderr, "pbboot: tls: modelled from %s: filesz 0x%x memsz 0x%x\n", objects[0].label,
                    (unsigned)t->filesz, (unsigned)t->memsz);
        else
            fprintf(stderr, "pbboot: tls: %s declares PT_TLS filesz 0x%x memsz 0x%x; "
                            "a placeholder block follows\n", objects[0].label, (unsigned)t->filesz,
                    (unsigned)t->memsz);
        /* One module of however many declare PT_TLS. Say so at every boot rather than let a reader assume
           the block covers everything: which module's @tpoff constants are in play is a measurement this
           runtime has not made, and a modelled block that is a default is a silent truncation. */
        for (size_t m = 1; m < object_count; m++) {
            const rt_elf_tls *o = rt_elf_tls_segment(objects[m].elf);
            if (o->memsz)
                fprintf(stderr, "pbboot: tls: %s declares PT_TLS filesz 0x%x memsz 0x%x -- not modelled\n",
                        objects[m].label, (unsigned)o->filesz, (unsigned)o->memsz);
        }
    }
    rt_tls_init();
    char *db_text;
    size_t nid_skipped = 0;
    const ssize_t names = read_nid_db(nid_path, &db, &db_text, &nid_skipped);
    if (names < 0) {
        /* Name the source, not a flag the caller may not have passed: BB_NID_DB and --nids are different
           doors and a refusal that reports the wrong one sends the reader to the wrong place. */
        fprintf(stderr, "pbboot: %s %s: unreadable: %s\n", nid_source, nid_path, strerror(errno));
        return 3;
    }
    db_count = names;
    if (nid_path && nid_skipped)
        fprintf(stderr, "pbboot: %s %s: %zd name(s), %zu malformed entr%s skipped\n", nid_source, nid_path,
                names, nid_skipped, nid_skipped == 1 ? "y" : "ies");
    else if (nid_path)
        fprintf(stderr, "pbboot: %s %s: %zd name(s)\n", nid_source, nid_path, names);
    for (size_t k = 0; k < object_count; k++) resolve(&objects[k]);

    if (list) {
        for (size_t k = 0; k < object_count; k++) {
            const object *o = &objects[k];
            for (size_t i = 0; i < o->imports; i++) {
                const char *name = rt_elf_import_name(o->elf, i), *sym = symbol_of(name);
                const char *lib = rt_elf_import_library(o->elf, i);
                const char *provider = o->provider[i] == MODULE    ? objects[o->provider_object[i]].label
                                       : o->provider[i] == RUNTIME ? "runtime"
                                       : o->provider[i] == RUNTIME_UNRESOLVED ? "runtime-unresolved"
                                                                             : "";
                unsigned long long offset = 0, size = 0;
                if (o->provider[i] == MODULE) {
                    const rt_elf *pe = objects[o->provider_object[i]].elf;
                    offset = rt_elf_export_value(pe, o->provider_export[i]);
                    size = rt_elf_export_size(pe, o->provider_export[i]);
                }
                printf("%s\t%s\t%s\t%s\t%s\t0x%08llx\t%llu\n", o->label, lib ? lib : "?", sym ? sym : name,
                       rt_elf_import_kind(o->elf, i) == RT_ELF_IMPORT_DATA ? "data" : "function", provider, offset, size);
            }
        }
        return 0;
    }

    /* Memory: each object's image, its trampolines and data imports; the guest stack and TLS. */
    for (size_t k = 0; k < object_count; k++) {
        object *o = &objects[k];
        void *want = o->image;
        o->image = mmap(want, o->size, PROT_READ | PROT_WRITE | PROT_EXEC,
                        MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
        o->tramp = mmap(NULL, (o->imports + 1) * TRAMPOLINE_SIZE, PROT_READ | PROT_WRITE | PROT_EXEC,
                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        o->data = mmap(NULL, (o->imports + 1) * 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        /* BB_DATA_GUARD turns the private pages that back UNBOUND data imports into guard pages, so a
           guest that dereferences one faults AT THE OBJECT'S OWN ADDRESS instead of reading zeroes and
           failing later at 0. It is an experiment, not a default: the pages exist to give an unbound
           object import a unique address, and this asks the harder question of whether anything reads it. */
        /* GUARDED IS THE DEFAULT, because the alternative is a read that returns zeroes and reports
           nothing: an unbound object import silently claiming to be shaped like the real object is the
           "safety off by default" shape. BB_DATA_PERMISSIVE=1 restores the zero pages and says so out
           loud -- a permissive run is a run with the detector removed, and must announce itself. */
        int guard_pages = !getenv("BB_DATA_PERMISSIVE");
        if (guard_pages && mprotect(o->data, (o->imports + 1) * 4096, PROT_NONE))
            rt_fatal("imports", "could not protect the unbound-data pages (BB_DATA_PERMISSIVE=1 to opt out)");
        else if (!guard_pages)
            fprintf(stderr, "pbboot: %s: unbound-data pages are PERMISSIVE (BB_DATA_PERMISSIVE=1): an "
                            "unbound object import reads zeroes here, and nothing reports it\n", o->label);
        else {
            fprintf(stderr, "pbboot: %s: %zu unbound-data page(s) guarded -- a dereference of an unbound "
                            "object import faults at its own address\n", o->label, o->imports + 1);
            /* Every data import gets slot `data + 4096*index`; a bound one is pointed elsewhere, so the
               table below is the whole candidate set and the fault address selects one row of it. Printing
               it is what turns "fault at 0x...000" into a name. */
            for (size_t i = 0; i < o->imports; i++)
                if (rt_elf_import_kind(o->elf, i) == RT_ELF_IMPORT_DATA)
                    fprintf(stderr, "pbboot: guard slot %p %s %s\n", (void *)(o->data + 4096 * i),
                            rt_elf_import_library(o->elf, i), rt_elf_import_name(o->elf, i));
        }
        if (o->image != want || o->tramp == MAP_FAILED || o->data == MAP_FAILED) {
            fprintf(stderr, "pbboot: cannot map memory for %s: %s\n", o->path, strerror(errno));
            return 3;
        }
        /* One %gs checker per object's trampoline mapping, in the spare slot after every import. It is
           emitted before any stub that can call it: a trampoline patched to a call into unwritten bytes
           is a crash with no owner. */
        {
            unsigned char *check = o->tramp + o->imports * TRAMPOLINE_SIZE;
            const size_t check_size = rt_tls_check_size();
            const size_t check_n = rt_write_tls_check(check, TRAMPOLINE_SIZE,
                                                       (uint64_t)(uintptr_t)rt_tls_check_fail);
            if (check_n == 0 || check_n > TRAMPOLINE_SIZE || check_n != check_size) {
                char msg[160];
                snprintf(msg, sizeof msg,
                         "%%gs checker does not fit the spare trampoline slot (imports=%zu size=%zu TRAMPOLINE_SIZE=%d)",
                         o->imports, check_size, TRAMPOLINE_SIZE);
                rt_fatal("trampoline", msg);
            }
            __builtin___clear_cache((char *)check, (char *)check + check_n);
            o->tls_check = (uint64_t)(uintptr_t)check;
            if (getenv("BB_TRAMPOLINE_VERBOSE"))
                fprintf(stderr, "trampoline %s: %%gs checker %zu bytes at %p (spare slot %zu)\n",
                        o->label, check_n, (void *)check, o->imports);
        }
        if (getenv("BB_DUMP_IMPORT"))
            for (size_t i = 0; i < o->imports; i++)
                if (rt_elf_import_kind(o->elf, i) == RT_ELF_IMPORT_FUNCTION &&
                    (size_t)strtoul(getenv("BB_DUMP_IMPORT"), NULL, 0) == i)
                    fprintf(stderr, "pbboot: import %zu of %s = %s:%s\n", i, o->label,
                            rt_elf_import_library(o->elf, i), rt_elf_import_name(o->elf, i));
        for (size_t i = 0; i < o->imports; i++)
            if (rt_elf_import_kind(o->elf, i) == RT_ELF_IMPORT_FUNCTION)
                write_trampoline(o->tramp + i * TRAMPOLINE_SIZE, &o->called[i], (uint32_t)(k << 20 | i),
                                 (uint64_t)(uintptr_t)o->bound[i], o->tls_check);
        if (rt_elf_map(o->elf, o->image, bind_import, o, error, sizeof error)) {
            fprintf(stderr, "pbboot: %s\n", error);
            return 3;
        }
        if (getenv("BB_DUMP_SLOT")) {
            const uint64_t va = strtoull(getenv("BB_DUMP_SLOT"), NULL, 0);
            if (va < o->size) {
                const uint64_t v = *(const uint64_t *)(o->image + va);
                int hit = -1;
                for (size_t i = 0; i < o->imports; i++)
                    if ((uint64_t)(uintptr_t)(o->tramp + i * TRAMPOLINE_SIZE) == v) { hit = (int)i; break; }
                if (hit >= 0)
                    fprintf(stderr, "pbboot: slot %#llx -> import %d of %s = %s:%s\n", (unsigned long long)va,
                            hit, o->label, rt_elf_import_library(o->elf, hit),
                            rt_elf_import_name(o->elf, hit));
                else
                    fprintf(stderr, "pbboot: slot %#llx -> %#llx, no trampoline match\n",
                            (unsigned long long)va, (unsigned long long)v);
            }
        }
        /* No thread-pointer rewrite here. The guest's %fs is its own TCB; %gs is this runtime's
           per-thread state (rt_tls_thread), whose first word is &main_state, not a guest TCB.
           rt_elf_thread_pointer_to_gs() rewrote every "mov rax, fs:[0]" to gs:[0] and made the guest
           treat &main_state as its TCB, so fs:[0] + a valid -0x720 TLS offset landed in pbboot's
           .data. The function is deleted rather than left as a callable trap; restoring this defect
           requires writing the scanner again. */
    }
    uint64_t proc_param_size;
    const uint64_t proc_param = rt_elf_proc_param(objects[0].elf, &proc_param_size);
    rt_process.image = objects[0].image;
    rt_process.image_size = objects[0].size;
    rt_process.proc_param = proc_param_size ? objects[0].image + proc_param : NULL;

    /* Guest start is the image delta from GUEST_BASE -- the same base the host/guest translation in guest.h
       uses -- so a module lands where the catalog would put it. Subtracting each object's own mapping base
       instead printed libc.elf at eboot's address, which is what overlapping() exists to refuse. */
    /* The object table is written HERE, at load time, not where the run ends: a boot that stops at a wall
       is still a boot that mapped every object, and a table written after run_guest() returns would be
       absent on exactly the runs that need it first. The print stays for the operator; the file is for the
       tool, because an emitter parsing a log line breaks silently when the line is reworded. */
    {
        /* Gated on an environment variable, fail-closed: the test suite boots a mock eboot of 8192 bytes,
           and an unconditional write let the suite overwrite this repository artifact within the same slice
           that created it. A guard on the output protects the state; only a real boot opts in. */
        const char *table_path = getenv("BB_OBJECTS_CSV");
        FILE *t = (table_path && *table_path) ? fopen(table_path, "w") : NULL;
        if (!t) {
            /* Unset is not an error -- most runs are tests and captures, not artifact generation. Set but
               unwritable is an error, because that is a request that failed. `else fclose(NULL)` was the
               version that segfaulted every boot in the suite. */
            if (table_path && *table_path) fprintf(stderr, "pbboot: cannot write %s: %s\n", table_path, strerror(errno));
        } else {
            fprintf(t, "name,guest_start,size,kind\n");
            for (size_t m = 0; m < object_count; m++)
                fprintf(t, "%s,0x%08llx,%llu,%s\n", objects[m].label ? objects[m].label : "?",
                        (unsigned long long)(((uintptr_t)objects[m].image - GUEST_BASE) + RT_EBOOT_BASE),
                        (unsigned long long)objects[m].size, m == 0 ? "eboot" : "module");
            fclose(t);
        }
    }

    unsigned char *stack = mmap(NULL, STACK_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_STACK, -1, 0);
    if (stack == MAP_FAILED) {
        fprintf(stderr, "pbboot: cannot map the stack: %s\n", strerror(errno));
        return 3;
    }
    /* The guest stack is a runtime mapping, so it is guest memory like the image and the allocators. The
       registry was taught about flexible memory and direct memory first; a wcscmp on a guest stack buffer
       then refused a pointer the guest itself had pushed. Register it where it is mapped, once. */
    if (!rt_guest_register_mapping((uintptr_t)stack, STACK_SIZE)) {
        fprintf(stderr, "pbboot: cannot register the guest stack as guest memory\n");
        return 3;
    }

    /* The executable's TLS block and its %fs install are owned by runtime/tls.c: rt_tls_layout/rt_tls_init.
       The legacy variant-II block that used to live here set %gs to the guest thread pointer, which is the
       register the per-thread runtime state now lives in: it overwrote main_state after init, so every
       rt_tls_enter_host() read an rt_tls_thread out of the guest TLS block and restored %fs to zero. The two
       TLS implementations cannot both own the thread pointer; the per-thread one is the product's. */

    static unsigned char alt[1 << 16];
    stack_t ss = {.ss_sp = alt, .ss_size = sizeof alt};
    sigaltstack(&ss, NULL);
    struct sigaction sa = {0};
    sa.sa_sigaction = on_signal;
    sa.sa_flags = SA_SIGINFO | SA_ONSTACK | SA_NODEFER;
    static const int signals[] = {SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGTRAP, SIGALRM};
    for (size_t i = 0; i < sizeof signals / sizeof signals[0]; i++) sigaction(signals[i], &sa, NULL);

    /* The plugin endpoint: ONE call and one entry, because the loader was proved in a test binary first.
       BB_PLUGIN names the library; the RESOLVED path is printed because dlopen resolves a relative path against
       cwd and this binary is launched from more than one directory, so a bare path in a log is not reproducible. */
    {
        const char *plugin = getenv("BB_PLUGIN");
        unsigned plugin_hooks = 0;
        if (!plugin || !*plugin) {
            fprintf(stderr, "pbboot: BB_PLUGIN=absent: no hooks will be installed and every import returns the "
                            "unimplemented stub; a guest run under this state is not evidence about the game\n");
        } else {
            char resolved[PATH_MAX];
            if (!realpath(plugin, resolved)) {
                fprintf(stderr, "pbboot: BB_PLUGIN=%s does not resolve: %s\n", plugin, strerror(errno));
                return 3;
            }
            fprintf(stderr, "plugin: path=%s resolved=%s\n", plugin, resolved);
            /* The refusal is deliberate: a plugin whose identity cannot be printed makes the run
               unattributable, and an unattributable run is a number without a subject. */
            char phex[13];
            if (rt_identity_file_sha(resolved, phex) != 0) {
                fprintf(stderr, "pbboot: plugin sha256 unreadable for %s -- refusing to run with an "
                                "unattributable plugin\n", resolved);
                return 3;
            }
            fprintf(stderr, "plugin sha256 %s\n", phex);
            if (rt_boot_load_plugin(objects[0].image, objects[0].size, resolved, &plugin_hooks) != 0) {
                fprintf(stderr, "pbboot: the plugin refused: hooks_installed=%u\n", plugin_hooks);
                return 3;
            }
        }
    }

    unsigned char *stack_top = stack + STACK_SIZE - 64;
    rt_thread_register_main(stack, STACK_SIZE);
    /* Modules first, in the order given: entry(argument size 0, no arguments, no start override)
       runs the module's constructors and then its start function. */
    const char *phase = "eboot";
    for (size_t k = 1; k < object_count; k++) {
        phase = objects[k].label;
        /* ENTRY-STATE / LOCATION TEST, opt-in only. The failing case is a hand-emitted wrfsbase executed
           while %fs already holds the guest block. Reproduce exactly that with a HOST caller: install the
           guest base with arch_prctl, run the same six bytes from a malloc'd RWX buffer, then restore.
           Compiler-emitted asm in the same entry state separates "hand-emitted" from "entry state".
           The emitted bytes are WRGSBASE (/3), deliberately: the experiment's whole point is that a
           legal encoding wrote the OTHER register, so the buffer corrupts %gs. This used to run on every
           module boot and leave that corruption in place, which is why the sole module-binding test
           faulted after BB_PLUGIN=absent. Gate it, and restore the GS base even when it runs. */
        if (getenv("BB_ENTRY_STATE_TEST")) {
            unsigned long gs_before = 0;
            __asm__ volatile("rdgsbase %0" : "=r"(gs_before));
            const uint64_t hostbase = rt_tls_host_base(), guestbase = rt_tls_guest_base();
            unsigned char *buf = mmap(NULL, 4096, PROT_READ | PROT_WRITE | PROT_EXEC,
                                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
            unsigned char *q = buf;
            *q++ = 0x49, *q++ = 0xbb, memcpy(q, &hostbase, 8), q += 8;
            *q++ = 0xf3, *q++ = 0x49, *q++ = 0x0f, *q++ = 0xae, *q++ = 0xdb;
            *q++ = 0xf3, *q++ = 0x48, *q++ = 0x0f, *q++ = 0xae, *q++ = 0xc0;
            *q++ = 0xc3;
            syscall(158, 0x1002UL, (unsigned long)guestbase); /* %fs := guest block; arch_prctl takes the ADDRESS */
            uint64_t seen = ((uint64_t(*)(void))buf)();
            uint64_t asm_seen = 0;
            asm volatile("wrfsbase %0" ::"r"(hostbase));
            asm volatile("rdfsbase %0" : "=r"(asm_seen));
            syscall(158, 0x1002UL, (unsigned long)hostbase);  /* restore the host TCB */
            printf("pbboot: entry-state test: hand-emitted %#llx  compiler-emitted %#llx  host base %#llx\n",
                   (unsigned long long)seen, (unsigned long long)asm_seen, (unsigned long long)hostbase);
            __asm__ volatile("wrgsbase %0" ::"r"(gs_before));
        }
        run_guest(objects[k].image + rt_elf_entry(objects[k].elf), NULL, NULL, NULL, stack_top, timeout);
        if (outcome != RETURNED) break;
    }
    if (object_count == 1 || outcome == RETURNED) {
        /* The process entry receives a parameter block (argc, then argv) and an exit function. */
        static struct {
            int32_t argc;
            uint32_t pad;
            const char *argv[3];
        } params = {1, 0, {"eboot.bin", NULL, NULL}};
        phase = "eboot";
        /* The fixture runs here, not in the loop above: that loop is `for (k = 1; ...)` -- the MODULES --
           and eboot's entry is called on this path. A block keyed on k == 0 inside the modules loop is
           dead code, and a dead flag reads exactly like a flag that was never passed: the run proceeds,
           the guest faults as usual, and the failure is attributed to the guest. */
        if (selftest_guard) {
            const rt_elf_load *loads = rt_elf_loads(objects[0].elf);
            const size_t n = rt_elf_load_count(objects[0].elf);
            uint64_t at = 0;
            for (size_t j = 0; j < n; j++)
                if ((loads[j].flags & 2) && loads[j].memsz >= 0x100) at = loads[j].vaddr + 0x40;
            if (!at) {
                fprintf(stderr, "pbboot: no writable load segment with room for a guard word\n");
                return 3;
            }
            return rt_libc_guard_selftest(objects[0].image + at);
        }
        run_guest(objects[0].image + rt_elf_entry(objects[0].elf), &params, (void *)guest_exit, NULL, stack_top, timeout);
    }

    /* Which imports were entered: an index against the symbol table puts the guest's position within a few
       instructions, instead of inferring it from a displacement. */
    for (int k = 0; k < (int)(sizeof objects / sizeof objects[0]); k++) {
        if (!objects[k].elf) continue;
        fprintf(stderr, "pbboot: image %d at host %p\n", k, (void *)objects[k].image);
        for (int i = 0; i < (int)objects[k].imports; i++)
            if (objects[k].called[i]) fprintf(stderr, "pbboot: entered #%d %s:%s\n", i, rt_elf_import_library(objects[k].elf, i) ? rt_elf_import_library(objects[k].elf, i) : "?", rt_elf_import_name(objects[k].elf, i) ? rt_elf_import_name(objects[k].elf, i) : "?");
    }

    /* Results */
    size_t called_total = 0;
    for (size_t k = 0; k < object_count; k++)
        for (size_t i = 0; i < objects[k].imports; i++) called_total += objects[k].called[i];
    int reached = -1;
    for (size_t m = 0; m < MILESTONES; m++) {
        int hit = 0;
        if (m == 0) {
            for (size_t i = 0; i < objects[0].imports && !hit; i++) hit = objects[0].called[i];
        }
        for (int s = 0; !hit && s < 3 && milestones[m].symbols[s]; s++) {
            char nid[RT_NID_SIZE];
            rt_nid(milestones[m].symbols[s], nid);
            for (size_t k = 0; k < object_count && !hit; k++)
                for (size_t i = 0; i < objects[k].imports && !hit; i++)
                    hit = objects[k].called[i] && !strncmp(rt_elf_import_name(objects[k].elf, i), nid, RT_NID_SIZE - 1);
        }
        if (hit) reached = (int)m;
    }
    size_t from_modules = 0, from_runtime = 0, from_unresolved = 0;
    for (size_t i = 0; i < objects[0].imports; i++) {
        from_modules += objects[0].provider[i] == MODULE;
        from_runtime += objects[0].provider[i] == RUNTIME;
        from_unresolved += objects[0].provider[i] == RUNTIME_UNRESOLVED;
    }

    const char *stop_name = NULL, *stop_library = NULL, *stop_caller = NULL;
    char stop_nid[RT_NID_SIZE] = "";
    if (outcome == UNIMPLEMENTED) {
        const object *o = &objects[stopped_at >> 20];
        const size_t i = stopped_at & 0xfffff;
        const char *name = rt_elf_import_name(o->elf, i);
        memcpy(stop_nid, name, RT_NID_SIZE - 1);
        stop_name = symbol_of(name);
        stop_library = rt_elf_import_library(o->elf, i);
        stop_caller = o->label;
    }
    char at[128] = "", from[128] = "";
    if (outcome == FAULT || outcome == TIMEOUT) where(fault_rip, at, sizeof at);
    if (outcome == UNIMPLEMENTED) {
        if (stopped_from && guest_rx_contains(stopped_from)) where(stopped_from, from, sizeof from);
        else if (stopped_from)
            snprintf(from, sizeof from, "n/a (0x%llx is not inside the guest's PF_X segments)",
                     (unsigned long long)stopped_from);
        else
            snprintf(from, sizeof from, "n/a (guest return address not captured for this object)");
    }

    printf("pbboot: %s: %s", phase, outcome_names[outcome]);
    if (outcome == UNIMPLEMENTED)
        printf(": %s calls %s %s (NID %s), returning to %s (args rdi %#llx rsi %#llx rdx %#llx)", stop_caller,
               stop_library ? stop_library : "?", stop_name ? stop_name : stop_nid, stop_nid, from,
               (unsigned long long)rt_syslib_args[0], (unsigned long long)rt_syslib_args[1],
               (unsigned long long)rt_syslib_args[2]);
    if (outcome == FAULT) printf(": signal %d at %s, address 0x%llx", fault_signal, at, (unsigned long long)fault_address);
    if (outcome == FAULT) {
        /* A raw host pointer is unreadable to every reader, including me. Every artifact names its own
           subject: resolve the faulting PC to module + offset, and to the symbol when the build has one. */
        Dl_info di = {0};
        if (dladdr((void *)(uintptr_t)fault_rip, &di) && di.dli_fname) {
            const char *base = strrchr(di.dli_fname, '/');
            printf("pbboot: fault pc %s+0x%llx", base ? base + 1 : di.dli_fname,
                   (unsigned long long)(fault_rip - (uint64_t)(uintptr_t)di.dli_fbase));
            if (di.dli_sname)
                printf(" (%s+0x%llx)", di.dli_sname,
                       (unsigned long long)(fault_rip - (uint64_t)(uintptr_t)di.dli_saddr));
            printf("\n");
        } else {
            printf("pbboot: fault pc 0x%llx (no module resolved)\n", (unsigned long long)fault_rip);
        }
        printf("pbboot: fault on pbboot sha256 %s (the artifact that is running, not a rebuild)\n",
               rt_identity_sha());
        /* The %fs/stub dump below is an instrument, not a report: it proved the WRGSBASE fix and the stub
           layout, and that question is closed. Ungated, it ran on every fault, read objects[1] on a
           single-object image, and faults itself -- re-entering this path forever while stdout stayed
           buffered, which reads as a hang (12 of 12 on a synthetic ELF, and ctest's 60 s timeout).
           An instrument left in a report is a defect the report cannot show. */
        if (getenv("BB_FAULT_STUB_DUMP")) {
            uint64_t live_fs = 0;
            __asm__ volatile("rdfsbase %0" : "=r"(live_fs));
            printf("pbboot: fs host %#llx guest %#llx live %#llx%s\n",
                   (unsigned long long)rt_tls_host_base(), (unsigned long long)rt_tls_guest_base(),
                   (unsigned long long)live_fs,
                   rt_tls_host_base() == rt_tls_guest_base() ? "  <-- HOST FS IS THE GUEST BLOCK" : "");
        }
        /* Absence must be explained where it is observed: an empty frame list here means the
           backtrace was not captured, not that the fault had no stack. */
        if (fault_frame_count == 0)
            printf("pbboot: no frames captured (backtrace() is off by default: it takes dl_load_lock "
                   "inside a signal handler and deadlocks under load; set BB_FAULT_BACKTRACE=1 when "
                   "the frames are worth that hazard)\n");
        for (int f = 0; f < fault_frame_count; f++) {
            Dl_info di;
            if (dladdr(fault_frames[f], &di) && di.dli_fname)
                printf("pbboot: frame %d %s+%#llx (%s)\n", f, di.dli_fname,
                       (unsigned long long)((char *)fault_frames[f] - (char *)di.dli_fbase),
                       di.dli_sname ? di.dli_sname : "?");
            else
                printf("pbboot: frame %d %p (unresolved)\n", f, fault_frames[f]);
        }
        if (rt_syslib_in_flight == 0xffffffffu)
            printf("pbboot: in flight: none (not inside a syslib body)\n");
        else
            printf("pbboot: in flight: #%u args %#llx %#llx %#llx guest_pc %#llx\n", rt_syslib_in_flight,
                   (unsigned long long)rt_syslib_args[0], (unsigned long long)rt_syslib_args[1],
                   (unsigned long long)rt_syslib_args[2],
                   (unsigned long long)import_guest_pc(rt_syslib_in_flight));
        /* Which TLS the fault happened on. A host body running with %fs on the guest TCB reads zeros
           for every glibc TLS slot -- errno, the stack protector's fs:0x28 -- and the first dereference
           of anything those zeros point at faults at exactly 0x0 with a host pc and guest arguments,
           which is indistinguishable from a null argument unless this is printed. */
        {
            const uint64_t guest = rt_tls_guest_base(), host = rt_tls_host_base();
            printf("pbboot: fault tls fs 0x%llx guest 0x%llx host 0x%llx -- %s; a fault inside a trampoline "
                   "slot happens BEFORE the crossing, so guest %%fs there is the prologue's own state "
                   "and says nothing about a body. Read this beside the pc-space lines, never alone.\n",
                   (unsigned long long)fault_fs, (unsigned long long)guest, (unsigned long long)host,
                   fault_fs == guest ? "fs == guest tcb" : fault_fs == host ? "fs == host tcb" : "fs == neither");
        }
        /* "no module resolved" is the resolver's opinion, not a fact about the pc: the guest image is an
           mmap too, so a pc inside guest code is a host address by construction. Print the arithmetic
           that decides it instead of the verdict that assumed it. */
        {
            /* The trampolines are an mmap of their own: a pc in there is MY emitted bytes, and the slot
               index names which import's stub it is. Outside every region, the pc is the guest's. */
            const uint64_t tr = (uint64_t)(uintptr_t)objects[0].tramp;
            const uint64_t pc = fault_rip;
            if (tr && pc >= tr && pc < tr + (uint64_t)TRAMPOLINE_SIZE * objects[0].imports) {
                const uint64_t slot = (pc - tr) / TRAMPOLINE_SIZE;
                printf("pbboot: fault pc is inside trampoline slot %llu of %zu (offset %llu in the slot)\n",
                       (unsigned long long)slot, (size_t)objects[0].imports,
                       (unsigned long long)((pc - tr) % TRAMPOLINE_SIZE));
            } else {
                printf("pbboot: fault pc is outside the trampoline region (0x%llx + %llu slots)\n",
                       (unsigned long long)tr, (unsigned long long)objects[0].imports);
            }
        }
        {
            const uint64_t img = (uint64_t)(uintptr_t)objects[0].image, ext = rt_map_extent();
            const uint64_t pc = fault_rip;
            printf("pbboot: fault pc space image 0x%llx extent 0x%llx pc 0x%llx -- %s\n",
                   (unsigned long long)img, (unsigned long long)ext, (unsigned long long)pc,
                   (pc >= img && pc < img + ext) ? "INSIDE the guest image (guest code, guest %fs is correct)"
                                                 : "outside the guest image (host code)");
        }
        /* WHICH import, chronologically, and no print per entry: the trampoline stores `which` into
           rt_syslib_in_flight BEFORE the crossing and nothing clears it on a fault, so at the fault this
           is the import whose body was running. -1 means the fault happened outside every import body --
           and then it was guest code, which is entitled to run on the guest %fs and the tls line above is
           a statement about correct behaviour, not a defect. The entered#N list is index-ordered and can
           never answer this. */
        if ((int32_t)rt_syslib_in_flight < 0) {
            printf("pbboot: fault import none in flight (the fault is not inside an import body)\n");
        } else {
            const uint32_t v = rt_syslib_in_flight;
            const unsigned k = v >> 20, i = v & 0xfffffu;
            const char *lib = "?", *sym = "?";
            if (k < object_count && objects[k].elf && i < objects[k].imports) {
                lib = rt_elf_import_library(objects[k].elf, i);
                sym = rt_elf_import_name(objects[k].elf, i);
            }
            printf("pbboot: fault import in flight #%u %s:%s (object %u import %u)\n", v, lib ? lib : "?",
                   sym ? sym : "?", k, i);
            /* THREE captured words, because rt_syslib_args is [3] and the trampoline stores exactly rdi,
               rsi, rdx. The old line printed indices 4 and 5 -- out of bounds -- under the labels r8/r9, and
               index 3 (never written) under rcx: three "registers" that were not registers. Slot 3 is
               retired rather than filled: the guest return address lives in rt_import_pc[which][0]. */
            {
                const uint64_t gpc = import_guest_pc(v);
                char g[128];
                if (gpc && guest_rx_contains(gpc)) where(gpc, g, sizeof g);
                else snprintf(g, sizeof g, "n/a (not captured for this object)");
                printf("pbboot: fault import args rdi %llx rsi %llx rdx %llx guest_pc %s\n",
                       (unsigned long long)rt_syslib_args[0], (unsigned long long)rt_syslib_args[1],
                       (unsigned long long)rt_syslib_args[2], g);
            }
        }
        printf("pbboot: fault regs rax %llx rbx %llx rcx %llx rdx %llx\n"
               "pbboot: fault regs rsi %llx rdi %llx rbp %llx rsp %llx\n"
               "pbboot: fault regs r8 %llx r9 %llx r10 %llx r11 %llx r12 %llx r13 %llx r14 %llx r15 %llx\n",
               (unsigned long long)fault_regs[REG_RAX], (unsigned long long)fault_regs[REG_RBX],
               (unsigned long long)fault_regs[REG_RCX], (unsigned long long)fault_regs[REG_RDX],
               (unsigned long long)fault_regs[REG_RSI], (unsigned long long)fault_regs[REG_RDI],
               (unsigned long long)fault_regs[REG_RBP], (unsigned long long)fault_regs[REG_RSP],
               (unsigned long long)fault_regs[REG_R8], (unsigned long long)fault_regs[REG_R9],
               (unsigned long long)fault_regs[REG_R10], (unsigned long long)fault_regs[REG_R11],
               (unsigned long long)fault_regs[REG_R12], (unsigned long long)fault_regs[REG_R13],
               (unsigned long long)fault_regs[REG_R14], (unsigned long long)fault_regs[REG_R15]);
        /* The faulting instruction did not push; [rsp] is its return address. The guest stack is
           registered, so ask the registry rather than dereferencing a raw address in a signal handler. */
        {
            const uintptr_t sp = (uintptr_t)fault_regs[REG_RSP];
            const uintptr_t bp = (uintptr_t)fault_regs[REG_RBP];
            uint64_t r0 = 0, r1 = 0, r2 = 0;
            if (rt_guest_span(sp) >= sizeof r0) memcpy(&r0, (const void *)sp, sizeof r0);
            if (rt_guest_span(bp) >= 2 * sizeof r1) {
                memcpy(&r1, (const void *)bp, sizeof r1);
                memcpy(&r2, (const void *)(bp + 8), sizeof r2);
            }
            printf("pbboot: fault stack [rsp] 0x%llx [rbp] 0x%llx [rbp+8] 0x%llx\n",
                   (unsigned long long)r0, (unsigned long long)r1, (unsigned long long)r2);
            /* The guest compiles with frame pointers in this image, and the guest stack is the host
               stack, so the rbp chain is readable through the registry. Five frames is enough to leave
               the accessor wrapper and reach the object owner; stop on a non-monotonic or unmapped
               link rather than trusting a chain that has already been corrupted. */
            {
                uintptr_t fp = bp;
                for (int k = 0; k < 5 && rt_guest_span(fp) >= 2 * sizeof(uint64_t); k++) {
                    uint64_t saved = 0, ret = 0;
                    memcpy(&saved, (const void *)fp, sizeof saved);
                    memcpy(&ret, (const void *)(fp + 8), sizeof ret);
                    printf("pbboot: fault guest frame %d rbp 0x%llx ret 0x%llx\n", k,
                           (unsigned long long)fp, (unsigned long long)ret);
                    if (saved <= fp || rt_guest_span(saved) < 2 * sizeof(uint64_t)) break;
                    fp = (uintptr_t)saved;
                }
            }
        }
    }
    if (outcome == TIMEOUT) printf(" after %d s, at %s", timeout, at);
    if (outcome == EXITED) printf(" with code %d", exit_code);
        {
            int n_real = 0, n_modelled = 0, n_noop = 0, n_refused = 0, n_all = 0;
            for (const rt_syslib_entry *e = rt_syslib_begin(); e < rt_syslib_end(); e++) {
                n_all++;
                switch (e->kind) {
                case RT_SYSLIB_KIND_REAL: n_real++; break;
                case RT_SYSLIB_KIND_MODELLED: n_modelled++; break;
                case RT_SYSLIB_KIND_NOOP: n_noop++; break;
                default: n_refused++; break;
                }
            }
            printf("\npbboot: syslib registered %d = %d real + %d modelled + %d noop + %d refused\n", n_all,
                   n_real, n_modelled, n_noop, n_refused);
        }
    printf("\npbboot: milestone %s; executable imports %zu: %zu from bundled modules, %zu implemented by the runtime, "
           "%zu unresolved diagnostics, %zu unbound; imports called %zu\n",
           reached >= 0 ? milestones[reached].name : "loaded", objects[0].imports, from_modules, from_runtime,
           from_unresolved, objects[0].imports - from_modules - from_runtime - from_unresolved, called_total);
    if (trace)
        for (size_t k = 0; k < object_count; k++)
            for (size_t i = 0; i < objects[k].imports; i++)
                if (objects[k].called[i]) {
                    const char *name = rt_elf_import_name(objects[k].elf, i), *sym = symbol_of(name);
                    const char *lib = rt_elf_import_library(objects[k].elf, i);
                    printf("  %s called %s %s\n", objects[k].label, lib ? lib : "?", sym ? sym : name);
                }

    if (status_path) {
        FILE *f = fopen(status_path, "w");
        if (!f) {
            fprintf(stderr, "pbboot: cannot write %s\n", status_path);
            return 3;
        }
        fprintf(f, "{\n  \"schema\": 2,\n  \"phase\": ");
        json_string(f, phase);
        fprintf(f, ",\n  \"outcome\": \"%s\",\n  \"milestone\": ", outcome_names[outcome]);
        json_string(f, reached >= 0 ? milestones[reached].name : "loaded");
        fprintf(f, ",\n  \"milestone_index\": %d,\n  \"milestones\": [\"loaded\"", reached + 1);
        for (size_t m = 0; m < MILESTONES; m++) fprintf(f, ", \"%s\"", milestones[m].name);
        fprintf(f,
                "],\n  \"imports_total\": %zu,\n  \"imports_implemented\": %zu,\n  \"imports_bundled\": %zu,\n"
                "  \"imports_unresolved\": %zu,\n  \"imports_remaining\": %zu,\n  \"imports_called\": %zu,\n",
                objects[0].imports, from_runtime, from_modules, from_unresolved,
                objects[0].imports - from_modules - from_runtime, called_total);
        fprintf(f, "  \"modules\": [");
        for (size_t k = 1; k < object_count; k++) {
            size_t remaining = 0;
            for (size_t i = 0; i < objects[k].imports; i++)
                remaining += objects[k].provider[i] == NONE || objects[k].provider[i] == RUNTIME_UNRESOLVED;
            fprintf(f, "%s{\"name\": ", k > 1 ? ", " : "");
            json_string(f, objects[k].label);
            fprintf(f, ", \"imports\": %zu, \"imports_remaining\": %zu, \"exports\": %zu}", objects[k].imports, remaining,
                    rt_elf_export_count(objects[k].elf));
        }
        fprintf(f, "],\n  \"first_unimplemented\": ");
        if (outcome == UNIMPLEMENTED) {
            fprintf(f, "{\"caller\": ");
            json_string(f, stop_caller);
            fprintf(f, ", \"library\": ");
            json_string(f, stop_library ? stop_library : "");
            fprintf(f, ", \"symbol\": ");
            json_string(f, stop_name ? stop_name : "");
            fprintf(f, ", \"nid\": ");
            json_string(f, stop_nid);
            fprintf(f, ", \"returns_to\": ");
            json_string(f, from);
            fprintf(f, "}");
        } else {
            fprintf(f, "null");
        }
        fprintf(f, ",\n  \"fault\": ");
        if (outcome == FAULT || outcome == TIMEOUT) {
            fprintf(f, "{\"signal\": %d, \"at\": ", fault_signal);
            json_string(f, at);
            fprintf(f, ", \"address\": \"0x%llx\"}", (unsigned long long)fault_address);
        } else {
            fprintf(f, "null");
        }
        fprintf(f, "\n}\n");
        fclose(f);
    }
    free(db);
    free(db_text);
    /* A stopped boot and a finished boot must not share a return code: `unimplemented` used to leave
       rc=0, which every downstream reader -- and I have been one -- takes as success. The guest's own
       exit code is passed through unchanged, so a guest that exits 4 is indistinguishable from this
       program's "stopped at an unbound import"; the printed line is the discriminator, and a caller
       that needs certainty reads stdout. */
    /* An accepted registration that never runs is a gap; a gap that is not printed is a silence.
       One line, in host context, with the count -- and it does not depend on the outcome, because a
       fault can happen with handlers registered just as an exit can. */
    if (rt_libc_atexit_registered())
        printf("pbboot: atexit: %u handler(s) registered, 0 run -- the runtime leaves through the "
               "guest's exit import and does not re-enter guest code (modelled)\n",
               rt_libc_atexit_registered());
    if (rt_libc_atexit_refused())
        printf("pbboot: atexit: %u registration(s) REFUSED (table full at %u) -- a refused handler is not "
               "a registered one\n", rt_libc_atexit_refused(), rt_libc_atexit_capacity());

    /* Exit vocabulary, one fact per code: 0 returned/exited · 1 fault · 2 timeout · 3 precondition (a plugin
       or file the run needs is absent or unusable -- returned from the setup paths above, never a guest
       outcome) · 4 unimplemented import. 78 and 124 belong to wrappers and never to pbboot: 78 = build failed,
       nothing ran (tools/boot.sh, tools/test.sh); 124 = cost exceeded (timeout(1), tools/restamp.py).
       A new code is a new word in the vocabulary -- add it here when you add it, because rc=127 was read as a
       verdict twice while it had no line. */
    switch (outcome) {
    case UNIMPLEMENTED: return 4;   /* the guest reached an import this runtime cannot serve */
    case FAULT: return 1;           /* the guest faulted (signal) */
    case TIMEOUT: return 2;         /* the guest did not finish within --timeout */
    default: return outcome == EXITED ? exit_code : 0;
    }
}

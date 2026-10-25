/* Swap the thread's %fs base between the host's TCB and a guest block. See runtime/tls.c for the
   measurements that scope this: fs:[0] only, and wrfsbase available here. */
#include <stdint.h>

/* The two fields an emitted boundary stub may read from the state at %gs. They are constants because
   the stub's instruction stream needs a displacement, and they are asserted against offsetof() in
   tls.c: a struct edit must stop the build rather than silently read a neighbouring field. */
#define RT_TLS_GS_GUEST_BLOCK_OFF 0x8
#define RT_TLS_GS_HOST_FSBASE_OFF 0x28

void rt_tls_init(void);
/* 1 when guest_memsz is the 0x4a0 placeholder, not a size the ELF declared. */
int rt_tls_guest_memsz_is_default(void);
void rt_tls_thread_begin(void);
void rt_tls_thread_end(void);
void rt_tls_layout(const void *image, unsigned filesz, unsigned memsz);
int rt_tls_have_wrfsbase(void);
void rt_tls_enter_guest(void);
void rt_tls_enter_host(void);
extern uint64_t rt_tls_guest_base_v;
int rt_tls_uses_wrfsbase(void);
uint64_t rt_tls_host_base(void);
uint64_t rt_tls_guest_base(void);
/* 1 only when %gs names this runtime's own state. A fixture that defines neither this nor
   runtime/tls.c leaves it unresolved (0), and emitters must then bake the bases instead of reading %gs:
   glibc's TCB also points at itself at offset 0, so a self-pointer check cannot tell the two apart. */
int rt_tls_thread_ready(void);
/* Called from rt_boot_call's asm with %fs already the guest block. Raw write+exit_group; no libc.
   reason 0: the thread's host base is zero. reason 1: guest returned with a zero %gs selector, so this
   thread's host base is unknown and main's published base must not be substituted. */
void rt_tls_host_base_refuse(int reason);

/* Four views of the thread pointer, each carrying the mechanism that produced it. A bare set of four
   numbers that agree proves nothing; `gs` and `state.self` are the runtime's state, `fs[0]` is what the
   guest's own instruction would read, `installer` is this thread's record, `published` is main's global
   (rt_boot_call's fallback only, never the emitted stubs' selector), and `enter_guest` is what
   rt_tls_enter_guest would install.
   Printing the sources is what makes a disagreement a question rather than a coincidence. */
typedef struct rt_tls_view {
    uint64_t gs;            /* rdgsbase */
    uint64_t state;         /* tls_state(), derived from %gs */
    uint64_t state_self;    /* state->self */
    uint64_t fsbase;        /* rdfsbase */
    uint64_t fs0;           /* mov %fs:0, read through the register */
    uint64_t installer;     /* state->guest_block */
    uint64_t published;     /* rt_tls_guest_base_v, main's record only; not the selector */
    uint64_t enter_guest;   /* rt_tls_guest_base(), what enter_guest would install */
    unsigned memsz;         /* state->guest_memsz */
} rt_tls_view;

void rt_tls_view_read(rt_tls_view *out);
void rt_tls_trace(const char *where);          /* call with the host %fs installed */
void rt_tls_trace_view(const char *where, const rt_tls_view *view);  /* ditto; prints a captured view */

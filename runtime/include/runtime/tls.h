/* Swap the thread's %fs base between the host's TCB and a guest block. See runtime/tls.c for the
   measurements that scope this: fs:[0] only, and wrfsbase available here. */
#include <stdint.h>

void rt_tls_init(void);
void rt_tls_thread_begin(void);
void rt_tls_thread_end(void);
void rt_tls_layout(const void *image, unsigned filesz, unsigned memsz);
int rt_tls_have_wrfsbase(void);
void rt_tls_enter_guest(void);
void rt_tls_enter_host(void);
extern uint64_t rt_tls_guest_base_v;
extern uint64_t rt_tls_host_base_v;
int rt_tls_uses_wrfsbase(void);
uint64_t rt_tls_host_base(void);
uint64_t rt_tls_guest_base(void);

/* Four views of the thread pointer, each carrying the mechanism that produced it. A bare set of four
   numbers that agree proves nothing; `gs` and `state.self` are the runtime's state, `fs[0]` is what the
   guest's own instruction would read, `installer` is this thread's record, `published` is the global the
   assembly helper uses (main-thread only), and `enter_guest` is what rt_tls_enter_guest would install.
   Printing the sources is what makes a disagreement a question rather than a coincidence. */
typedef struct rt_tls_view {
    uint64_t gs;            /* rdgsbase */
    uint64_t state;         /* tls_state(), derived from %gs */
    uint64_t state_self;    /* state->self */
    uint64_t fsbase;        /* rdfsbase */
    uint64_t fs0;           /* mov %fs:0, read through the register */
    uint64_t installer;     /* state->guest_block */
    uint64_t published;     /* rt_tls_guest_base_v, main's value only */
    uint64_t enter_guest;   /* rt_tls_guest_base(), what enter_guest would install */
    unsigned memsz;         /* state->guest_memsz */
} rt_tls_view;

void rt_tls_view_read(rt_tls_view *out);
void rt_tls_trace(const char *where);          /* call with the host %fs installed */
void rt_tls_trace_view(const char *where, const rt_tls_view *view);  /* ditto; prints a captured view */

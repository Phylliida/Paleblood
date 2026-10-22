/* Swap the thread's %fs base between the host's TCB and a guest block. See runtime/tls.c for the
   measurements that scope this: fs:[0] only, and wrfsbase available here. */
#include <stdint.h>

void rt_tls_init(void);
void rt_tls_layout(const void *image, unsigned filesz, unsigned memsz);
int rt_tls_have_wrfsbase(void);
void rt_tls_enter_guest(void);
void rt_tls_enter_host(void);
uint64_t rt_tls_host_base(void);
uint64_t rt_tls_guest_base(void);

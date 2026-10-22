/* Swap the thread's %fs base between the host's TCB and a guest block. See runtime/tls.c for the
   measurements that scope this: fs:[0] only, and wrfsbase available here. */
void rt_tls_init(void);
int rt_tls_have_wrfsbase(void);
void rt_tls_enter_guest(void);
void rt_tls_enter_host(void);

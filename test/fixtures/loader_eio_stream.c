/* A stream that reports a length and then FAILS the read, for the loader's `read error after N of M` arm.
   No plain path can do it: a pre-truncated file makes ftell equal the file (so fread is whole), a directory
   reports LONG_MAX and dies in malloc, /proc reports 0 and dies in size<64. LD_PRELOAD this, and every fopen
   after the first on a path containing "eio_eboot" returns a cookie stream: seek reports 4096, read returns
   -1 with errno=EIO. The first open is real, because rt_identity_file_sha must hash a regular file before the
   loader runs -- the shim refuses to witness the loader by breaking the instrument above it.
   Build: cc -shared -fPIC -o eio.so test/fixtures/loader_eio_stream.c -ldl */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

static FILE *(*real_fopen)(const char *, const char *);
static int opens;

static ssize_t cookie_read(void *c, char *buf, size_t n)
{
    (void)c; (void)buf; (void)n;
    errno = EIO;
    return -1;
}
static int cookie_seek(void *c, off64_t *off, int whence)
{
    (void)c; (void)whence;
    *off = 4096;
    return 0;
}
static int cookie_close(void *c) { (void)c; return 0; }

FILE *fopen(const char *path, const char *mode)
{
    if (!real_fopen) real_fopen = dlsym(RTLD_NEXT, "fopen");
    if (path && strstr(path, "eio_eboot") && opens++ > 0) {
        cookie_io_functions_t io = {cookie_read, 0, cookie_seek, cookie_close};
        return fopencookie(0, "rb", io);
    }
    return real_fopen(path, mode);
}

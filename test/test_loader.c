/* The loader's short-read sentences are witnessed at the LAYER THEY LIVE IN. Through pbboot they are shadowed:
   rt_identity_file_sha requires a regular file and refuses anything else first, so /sys/kernel/uevent_seqnum --
   ftell 4096, fread 6, ferror 0 -- is now a hash refusal at the product layer and the loader never runs. A
   sentence that cannot be reached through the product still owes a witness where it exists; otherwise the next
   reader cannot tell "unreachable" from "never true". */
#define _GNU_SOURCE
#include "runtime/loader.h"
#include "runtime/identity.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int failures;
#define CHECK(cond) do { if (!(cond)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

typedef struct {
    const unsigned char *data;
    size_t len;
    size_t *pos;
    int *read_calls;
} cookie_read_ctx;

static ssize_t cookie_read_fn(void *c, char *buf, size_t n)
{
    cookie_read_ctx *x = c;
    (*x->read_calls)++;
    if (*x->pos >= x->len) return 0;
    if (n > x->len - *x->pos) n = x->len - *x->pos;
    memcpy(buf, x->data + *x->pos, n);
    *x->pos += n;
    return (ssize_t)n;
}

static int cookie_seek_fn(void *c, off64_t *off, int whence)
{
    cookie_read_ctx *x = c;
    off64_t base = whence == SEEK_SET ? 0 : whence == SEEK_END ? (off64_t)x->len : (off64_t)*x->pos;
    if (base + *off < 0 || base + *off > (off64_t)x->len) { errno = EINVAL; return -1; }
    *x->pos = (size_t)(base + *off);
    *off = (off64_t)*x->pos;
    return 0;
}

int main(void)
{
    char err[256];
    /* A sysfs attribute reports 4096 and supplies a handful of bytes without setting ferror: the truncated
       arm, and the assertion that no strerror suffix leaks into the sentence when nothing failed. */
    rt_elf *e = rt_elf_open("/sys/kernel/uevent_seqnum", err, sizeof err);
    CHECK(e == NULL);
    if (!strstr(err, "truncated: read ")) fprintf(stderr, "sysfs error: %s\n", err);
    CHECK(strstr(err, "truncated: read ") != NULL);
    CHECK(strstr(err, "(nothing failed") != NULL);
    CHECK(strstr(err, "Input/output error") == NULL);

    /* Absent: cannot open, and the path is named. */
    e = rt_elf_open("/tmp/test_loader_does_not_exist", err, sizeof err);
    CHECK(e == NULL && strstr(err, "cannot open") != NULL);

    /* Zero-length: cannot read (size below the ELF header), NOT truncated. */
    char zero[] = "/tmp/test_loader_zero_XXXXXX";
    const int fd = mkstemp(zero);
    CHECK(fd >= 0);
    if (fd >= 0) close(fd);
    e = rt_elf_open(zero, err, sizeof err);
    CHECK(e == NULL && strstr(err, "cannot read") != NULL);
    unlink(zero);

    /* 64 bytes is a header and nothing else: validation, not a short read. */
    FILE *src = fopen("/home/bepis/modding/decomp/data/bb/elf/eboot.elf", "rb");
    if (src) {
        char hdr[] = "/tmp/test_loader_hdr64_XXXXXX";
        const int hfd = mkstemp(hdr);
        CHECK(hfd >= 0);
        if (hfd >= 0) {
            unsigned char b[64];
            const size_t got = fread(b, 1, sizeof b, src);
            CHECK(got == sizeof b);
            if (got == sizeof b) {
                FILE *d = fdopen(hfd, "wb");
                CHECK(d && fwrite(b, 1, sizeof b, d) == sizeof b);
                if (d) fclose(d); else close(hfd);
                e = rt_elf_open(hdr, err, sizeof err);
                CHECK(e == NULL && strstr(err, "truncated") == NULL);
            } else close(hfd);
            unlink(hdr);
        }
        fclose(src);
    }

    /* ONE READ. A stream that WOULD serve different bytes on a second read: the hash must describe the
       bytes the loader parsed, and a counter must show the second read never happened. This is the defect
       a same-fd hash-then-load design has -- one open, two reads. Pattern bytes i%256 for 100 bytes; the
       expected prefix was computed by sha256sum, not by the function under test. */
    {
        static unsigned char content[100];
        for (size_t i = 0; i < sizeof content; i++) content[i] = (unsigned char)(i % 256);
        static size_t pos;
        static int read_calls;
        pos = 0; read_calls = 0;
        cookie_read_ctx ctx = {content, sizeof content, &pos, &read_calls};
        cookie_io_functions_t io = {cookie_read_fn, 0, cookie_seek_fn, 0};
        FILE *cookie = fopencookie(&ctx, "rb", io);
        CHECK(cookie != NULL);
        if (cookie) {
            char sha[13];
            e = rt_elf_open_stream(cookie, "<cookie>", sha, err, sizeof err);
            CHECK(e == NULL);                                  /* 100 bytes, not an ELF: refused */
            if (strcmp(sha, "bce0aff19cf5") != 0)
                fprintf(stderr, "cookie sha: got %s want bce0aff19cf5\n", sha);
            CHECK(strcmp(sha, "bce0aff19cf5") == 0);           /* sha256sum of bytes i%256, 100 */
            CHECK(read_calls == 1);                            /* one read, one subject */
        }
    }

    /* A parse refusal still names its bytes: 64 bytes of the real header fail validation, but the hash of
       exactly those 64 bytes (sha256sum: 4afe5a6943b6) comes back before the verdict. */
    {
        FILE *src2 = fopen("/home/bepis/modding/decomp/data/bb/elf/eboot.elf", "rb");
        if (src2) {
            unsigned char b[64];
            CHECK(fread(b, 1, sizeof b, src2) == sizeof b);
            fclose(src2);
            static size_t pos2;
            static int reads2;
            cookie_read_ctx hctx = {b, sizeof b, &pos2, &reads2};
            pos2 = 0; reads2 = 0;
            cookie_io_functions_t io = {cookie_read_fn, 0, cookie_seek_fn, 0};
            FILE *hc = fopencookie(&hctx, "rb", io);
            char sha[13];
            e = rt_elf_open_stream(hc, "<hdr64>", sha, err, sizeof err);
            CHECK(e == NULL && strcmp(sha, "4afe5a6943b6") == 0);
        }
    }

    /* A directory is EISDIR, not "cannot read": the old path named the failed check, not the state. */
    {
        e = rt_elf_open("/tmp", err, sizeof err);
        CHECK(e == NULL);
        CHECK(strstr(err, "is a directory (EISDIR)") != NULL);
        if (!strstr(err, "is a directory (EISDIR)"))
            fprintf(stderr, "directory sentence: %s\n", err);
    }

    if (failures) { fprintf(stderr, "loader: %d failure(s)\n", failures); return 1; }
    fprintf(stderr, "loader: ok\n");
    return 0;
}

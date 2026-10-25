/* The loader's short-read sentences are witnessed at the LAYER THEY LIVE IN. Through pbboot they are shadowed:
   rt_identity_file_sha requires a regular file and refuses anything else first, so /sys/kernel/uevent_seqnum --
   ftell 4096, fread 6, ferror 0 -- is now a hash refusal at the product layer and the loader never runs. A
   sentence that cannot be reached through the product still owes a witness where it exists; otherwise the next
   reader cannot tell "unreachable" from "never true". */
#include "runtime/loader.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int failures;
#define CHECK(cond) do { if (!(cond)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

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

    if (failures) { fprintf(stderr, "loader: %d failure(s)\n", failures); return 1; }
    fprintf(stderr, "loader: ok\n");
    return 0;
}

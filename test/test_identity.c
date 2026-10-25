/* The identity hash is the campaign's attribution instrument, so its ORACLE is external: the expected
   digests below were computed by sha256sum over the same byte patterns. The defect this pins was found by
   exactly that comparison -- a partial final block was hashed with stale bytes, and the binary disagreed
   with sha256sum on a 100000-byte file while agreeing on 4096. A fixture whose expected values came from the
   function under test would have been a formatter. */
#include "runtime/identity.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int failures;
#define CHECK(cond) do { if (!(cond)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

static int write_pattern(const char *path, size_t n)
{
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    for (size_t i = 0; i < n; i++) {
        const unsigned char b = (unsigned char)(i % 256);
        if (fwrite(&b, 1, 1, f) != 1) { fclose(f); return -1; }
    }
    return fclose(f);
}

int main(void)
{
    static const struct { size_t n; const char *sha; } cases[] = {
        {0, "e3b0c44298fc"}, {63, "29af2686fd53"}, {65, "4bfd2c8b6f1e"},
        {100, "bce0aff19cf5"}, {4096, "c8f5d0341d54"},
    };
    char path[] = "/tmp/test_identity_XXXXXX";
    const int fd = mkstemp(path);
    if (fd < 0) { perror("mkstemp"); return 1; }
    close(fd);
    char out[13];
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; i++) {
        CHECK(write_pattern(path, cases[i].n) == 0);
        CHECK(rt_identity_file_sha(path, out) == 0);
        if (strcmp(out, cases[i].sha) != 0)
            fprintf(stderr, "%zu bytes: got %s want %s\n", cases[i].n, out, cases[i].sha);
        CHECK(strcmp(out, cases[i].sha) == 0);
    }
    /* Not a regular file, and absent: both unreadable, never the hash of nothing. */
    CHECK(rt_identity_file_sha("/tmp", out) == -1 && out[0] == '\0');
    CHECK(rt_identity_file_sha("/tmp/test_identity_does_not_exist", out) == -1 && out[0] == '\0');
    unlink(path);
    if (failures) { fprintf(stderr, "identity: %d failure(s)\n", failures); return 1; }
    fprintf(stderr, "identity: ok\n");
    return 0;
}

/* SPDX-License-Identifier: GPL-2.0-or-later */
/* What ran, printed before anything else.

   Three times in this campaign a "identical on every number" claim turned out to compare two different
   artifacts, because the harness was rebuilt and the run under comparison was not. A number without the
   identity of the thing it measured has no subject, so every run states its own sha256 on line one; then
   two builds that disagree announce it themselves instead of being discovered a slice later. */
#include "runtime/identity.h"

#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <string.h>

static uint32_t ror(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

static void block(uint32_t h[8], const unsigned char *p)
{
    static const uint32_t k[64] = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
    uint32_t w[64];
    for (int i = 0; i < 16; i++)
        w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 | (uint32_t)p[4 * i + 2] << 8 |
               (uint32_t)p[4 * i + 3];
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ror(w[i - 15], 7) ^ ror(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ror(w[i - 2], 17) ^ ror(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], i2 = h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t s1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);
        uint32_t t1 = i2 + s1 + ch + k[i] + w[i];
        uint32_t s0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        uint32_t t2 = s0 + maj;
        i2 = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += i2;
}

static int sha256_file(const char *path, unsigned char out[32])
{
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    uint32_t h[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                     0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    /* The size is the subject: hash exactly the bytes fstat reports, and refuse if the file does not supply
       them. A short fread on a regular file is not EOF -- it is a file that changed under the hash, and
       treating it as EOF prints a confident hash of a prefix that matches no file that ever existed. Only a
       regular file can be a guest image; a directory or /proc entry reports a size it will not supply. */
    struct stat st;
    if (fstat(fileno(f), &st) < 0 || !S_ISREG(st.st_mode) || st.st_size < 0) { fclose(f); return -1; }
    const uint64_t size = (uint64_t)st.st_size;
    unsigned char buf[64];
    uint64_t total = 0;
    size_t n = 0;
    while (size - total >= sizeof buf) {
        if (fread(buf, 1, sizeof buf, f) != sizeof buf) { fclose(f); return -1; }
        block(h, buf);
        total += sizeof buf;
    }
    /* The remainder stays in buf UNHASHED: SHA-256's final block is the remainder, then 0x80, then the
       length. Hashing the remainder here and padding in a fresh block is a different digest -- the control
       is sha256sum of the same bytes, which disagreed on a 100000-byte file while agreeing on 4096. */
    n = (size_t)(size - total);
    if (n && fread(buf, 1, n, f) != n) { fclose(f); return -1; }
    /* One byte past the reported size: the file grew under the hash, so no complete byte set was hashed. */
    {
        unsigned char extra;
        if (fread(&extra, 1, 1, f) == 1) { fclose(f); return -1; }
    }
    if (ferror(f)) { fclose(f); return -1; }
    uint64_t bits = (total + n) * 8;
    buf[n++] = 0x80;
    if (n > 56) {
        while (n < 64) buf[n++] = 0;
        block(h, buf);
        n = 0;
    }
    while (n < 56) buf[n++] = 0;
    for (int i = 7; i >= 0; i--) buf[n++] = (unsigned char)(bits >> (8 * i));
    block(h, buf);
    fclose(f);
    for (int i = 0; i < 8; i++) {
        out[4 * i] = (unsigned char)(h[i] >> 24);
        out[4 * i + 1] = (unsigned char)(h[i] >> 16);
        out[4 * i + 2] = (unsigned char)(h[i] >> 8);
        out[4 * i + 3] = (unsigned char)h[i];
    }
    return 0;
}

static char identity_hex[13];

const char *rt_identity_sha(void)
{
    /* Computed once and kept, so any later report -- including a signal handler -- can name the artifact
       that is running instead of a rebuild of it. */
    if (identity_hex[0]) return identity_hex;
    unsigned char d[32];
    if (sha256_file("/proc/self/exe", d) != 0) {
        snprintf(identity_hex, sizeof identity_hex, "unreadable");
        return identity_hex;
    }
    for (int i = 0; i < 6; i++) snprintf(identity_hex + i * 2, 3, "%02x", d[i]);
    return identity_hex;
}

int rt_identity_file_sha(const char *path, char out[13])
{
    unsigned char d[32];
    if (sha256_file(path, d) != 0) { out[0] = '\0'; return -1; }
    for (int i = 0; i < 6; i++) snprintf(out + i * 2, 3, "%02x", d[i]);
    return 0;
}

void rt_announce_identity(void)
{
    /* stderr, not stdout: this is a banner, and `--imports` and `--status` write data on stdout.
       On stdout it became the first field of every machine-read listing, which is how
       test_tools.Boot.test_imports_bind_to_a_bundled_module went red reading
       'pbboot sha256 84815fd20b2c\neboot' where it expected 'eboot'. */
    fprintf(stderr, "pbboot sha256 %s\n", rt_identity_sha());
    fflush(stdout);
}

/* SPDX-License-Identifier: GPL-2.0-or-later */
/* _write: the guest's file descriptor write, delegated to the host syscall.

   Per the delegation split in docs/decisions-owed.md this is the least risky case on the list: no
   structs cross the boundary, no ownership changes hands, and the host's write() is the actual
   thing rather than a model of it. It sits below the guest's own stdio buffer, so a flush here
   reaches a real descriptor instead of a pretend one.

   Three details that decide whether it is honest:
     - the count returned is the count the host wrote. A short write is legal and is reported as
       short; nothing here returns n optimistically.
     - guest output is arbitrary octets, so the bytes go out raw. Formatting them would make a
       NUL-truncated line indistinguishable from a correct one in the log.
     - only descriptors 1 and 2 are served. Anything else is refused rather than pretended, because
       the runtime has no file table and a success would be a lie the guest would build on.
   Host output is tagged so the guest's own printing stays distinguishable from harness lines. */
#include "runtime/syslib.h"

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <unistd.h>

enum { k_stdout = 1, k_stderr = 2, k_error_badfd = 9, k_error_inval = 22 };

static int64_t libc_write(int fd, const void *buf, size_t len)
{
    if (fd != k_stdout && fd != k_stderr) return -k_error_badfd;
    if (!buf && len) return -k_error_inval;
    const unsigned char *p = buf;
    size_t done = 0;
    while (done < len) {
        ssize_t n = write(fd, p + done, len - done);
        if (n < 0) {
            if (errno == EINTR) continue;
            return done ? (int64_t)done : -(int64_t)errno;
        }
        if (n == 0) break;
        done += (size_t)n;
    }
    return (int64_t)done;
}
/* The bind dump names this NID against libkernel (docs/bind-order-eboot.txt, bind 47), so the
   entry matches on that library; the name is libc's because the function is. */
RT_SYSLIB("libkernel", _write, libc_write);

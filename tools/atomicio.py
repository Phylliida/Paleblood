"""One write helper, because a rule about ordering loses to a shape that truncates.

`open(path, 'w').write(text)` truncates at the OPEN, not at the write. So a producer that raises --
a refusal, a KeyboardInterrupt, a MemoryError while building a body -- has already destroyed the
artifact it was about to replace. I fixed that once by reordering one call site; the next author, or
the next call site, gets the same shape back. Write beside the target, fsync, then os.replace: the
artifact is either the old bytes or the new ones, never a half-written file, and nobody has to
remember the order.
"""
import os
import tempfile


def atomic_write(path, text, encoding='utf-8'):
    """Replace `path` with `text` atomically. Any failure leaves the old file exactly as it was."""
    data = text.encode(encoding) if isinstance(text, str) else text
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp = tempfile.mkstemp(dir=directory, prefix='.' + os.path.basename(path) + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
    dfd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dfd)          # the rename itself, durable
    finally:
        os.close(dfd)

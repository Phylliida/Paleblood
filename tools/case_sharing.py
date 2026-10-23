"""The sharing is the claim, so it is the thing pre-registered.

78 case directories hold 62 distinct behavioural keys: sixteen keys are shared by pairs of rows, and a case
file per row means sixteen pairs of directories carry identical contents. After the 77 land, three
outcomes and only three:

  78 directories, 62 distinct contents  ->  sharing happened as designed.
  78 directories, 78 distinct contents  ->  sharing did NOT happen: every address got its own copy. That is
                                            harmless on disk and the sentence says so, but the case_key
                                            column is then carrying no information and must not be cited.
  < 62 distinct                         ->  two behavioural keys collided in one case file. That is a
                                            wrong-body hazard: the differential would compare a body
                                            against a case authored for a different slot, and it stops the
                                            record. Refuse.

Corollary that `evidence_hash` must state: a hash pinned by two directories is not an identifier. The
ledger is queried by `address`, never by hash.
"""

import hashlib
import os

EXPECT_DIRS = 78
EXPECT_DISTINCT = 62


def _digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def audit_sharing(cases_dir, expect_dirs=EXPECT_DIRS, expect_distinct=EXPECT_DISTINCT):
    """(rc, detail). rc=1 only for the collision class, because that one can produce a wrong body."""
    if not os.path.isdir(cases_dir):
        return 1, f'case sharing: unread ({cases_dir} is not a directory) -- unread is not zero'
    dirs = sorted(d for d in os.listdir(cases_dir) if os.path.isdir(os.path.join(cases_dir, d)))
    digests = {}
    for d in dirs:
        p = os.path.join(cases_dir, d, 'case.json')
        if not os.path.exists(p):
            return 1, f'case sharing: {d} has no case.json -- a directory is not a case'
        digests.setdefault(_digest(p), []).append(d)
    n, k = len(dirs), len(digests)
    if k < expect_distinct:
        shared = ['+'.join(v) for v in digests.values() if len(v) > 1]
        return 1, (f'case sharing: REFUSED -- {n} directories hold only {k} distinct contents, expected '
                   f'{expect_distinct}: two behavioural keys collided in one case file, which is a '
                   f'wrong-body hazard. Shared: {", ".join(sorted(shared)[:6])}'
                   + (' ...' if len(shared) > 6 else ''))
    if k > expect_distinct:
        return 0, (f'case sharing: {n} directories / {k} distinct contents -- sharing did NOT happen: every '
                   f'address got its own copy, which is harmless on disk but leaves case_key carrying no '
                   f'information; do not cite it')
    return 0, (f'case sharing: ok ({n} directories / {k} distinct contents; {n - k} duplicate(s) by design)')

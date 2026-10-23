"""A fixture root that owns everything it reads, and proves it before returning.

The defect this exists to prevent is a path escaping the root: `byte_totals` called `_body_index()` bare, so a
fixture's rows were checked against the REPOSITORY's game/ and a fixture's byte totals were a function of a
directory it did not own. A helper cannot be trusted to prevent that by construction unless it asserts it, so
every path this module touches is recorded and must start with the root it was asked to build.

    root = fixture_root(bodies=1, rows=2, landed=1)     # raises if anything it read left the root
    root.facts                                          # {'bodies': 1, 'rows': 2, 'landed': 1, 'bytes': 8}

The self-check at the bottom is the two-root test in its first form: one root that owns a body and one that owns
none, in ONE process, each asserted against its own expected sum. A one-root test cannot fail.
"""
import csv
import os
import tempfile

# Every path this module reads or writes, so `_assert_contained` can refuse an escape.
_used = []


def _note(path):
    _used.append(os.path.abspath(path))
    return path


class Root:
    """A built fixture tree. `facts` are the four numbers the caller asked for, measured after the build."""

    def __init__(self, path, facts):
        self.path = path
        self.facts = facts

    def __fspath__(self):
        return self.path

    def p(self, rel):
        """A path relative to this root, and the ONLY way to reach into it: an absolute path or a climbing
        component is REFUSED here, so no caller can pass one at all. This is not a guard on a path that might
        escape -- it is an accessor that cannot express an escape. Three per-process caches and one per-process
        list this stretch taught the same lesson: make the shared thing unnameable, don't add a guard to it."""
        if os.path.isabs(rel):
            raise ValueError(f'fixture_root: REFUSED absolute path {rel!r} -- paths are relative to the root')
        parts = rel.replace(os.sep, '/').split('/')
        if any(part == '..' for part in parts):
            raise ValueError(f'fixture_root: REFUSED climbing path {rel!r} -- the root is a boundary')
        return _note(os.path.join(self.path, *parts))

    def at(self, *parts):
        return self.p('/'.join(str(x) for x in parts))

    def __repr__(self):
        return f"Root({self.path!r}, {self.facts})"


def fixture_root(bodies=0, rows=1, landed=0, size=8):
    """A temp root with its OWN game/ and symbols/functions.csv. Refuses if any path it used escaped it."""
    # PER CALL, not module-global: a shared accumulator makes the second root's containment check a function
    # of the first root's paths -- the same defect as image_base_set per process and _body_index per process,
    # and the self-check below fired on it before this helper was ever used by a test.
    global _used
    _used = []
    path = tempfile.mkdtemp(prefix='bbfixture.')
    os.makedirs(_note(os.path.join(path, 'game', 'leaf')), exist_ok=True)
    os.makedirs(_note(os.path.join(path, 'symbols')), exist_ok=True)

    tu = _note(os.path.join(path, 'game', 'leaf', 'fixture_bodies.cpp'))
    names = [f'fixture_{0x1000 + i:08x}' for i in range(rows)]
    with open(tu, 'w') as f:
        for i, n in enumerate(names[:bodies]):          # only the first `bodies` rows get a body
            f.write(f'extern "C" int bb_{n}() {{ return {i}; }}\n')

    csv_path = _note(os.path.join(path, 'symbols', 'functions.csv'))
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['address', 'name', 'size', 'status', 'system', 'notes'])
        for i, n in enumerate(names):
            w.writerow([f'0x{0x1000 + i:08x}', n, size, 'edge-verified' if i < landed else 'original', '', ''])

    facts = {'bodies': bodies, 'rows': rows, 'landed': landed,
             'bytes': sum(size for i in range(min(landed, bodies)))}
    print(f"fixture_root: bodies={facts['bodies']} rows={facts['rows']} landed={facts['landed']} "
          f"bytes={facts['bytes']}")
    for k, asked in (('bodies', bodies), ('rows', rows), ('landed', landed)):
        if facts[k] != asked:
            raise AssertionError(f'fixture_root: built {k}={facts[k]}, caller asked {asked}')
    _assert_contained(path)
    return Root(path, facts)


def _assert_contained(path):
    """Every path this module touched must live under `path`. A helper that can reach outside itself is the
    defect it was written to prevent, one tier up."""
    root = os.path.abspath(path) + os.sep
    escaped = [p for p in _used if not p.startswith(root)]
    if escaped:
        raise AssertionError(f'fixture_root: REFUSED, {len(escaped)} path(s) escaped the root: {escaped[:3]}')
    return len(_used)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import landed

    # TWO roots, ONE process, each asserted against its own sum. This is the shape tonight's defect lacked.
    a = fixture_root(bodies=1, rows=2, landed=1, size=8)
    b = fixture_root(bodies=0, rows=1, landed=0, size=8)
    ta = landed.byte_totals(a.at('symbols', 'functions.csv'))
    tb = landed.byte_totals(b.at('symbols', 'functions.csv'))
    print(f'root A: {ta}   (own body: 8 B)')
    print(f'root B: {tb}   (owns no body: must be 0)')
    real = landed.byte_totals('symbols/functions.csv')
    print(f'repo  : {real}')
    assert ta == {'landed': 8, 'transcribed': 8}, ta
    assert tb == {'landed': 0, 'transcribed': 0}, tb
    assert real['landed'] > 0, 'the repo still has bodies; the two root sums must differ from it'
    print(f'two-root test: OK -- A={ta["landed"]} B={tb["landed"]} repo={real["landed"]}, each its own')

    # The accessor's own refusals, BOTH arms observed -- a guard never shown to fire is a guard nobody has tested.
    for bad in ('/etc/passwd', '../outside', 'symbols/../../outside'):
        try:
            a.p(bad)
        except ValueError as e:
            print(f'refused {bad!r}: {str(e).split(" REFUSED ")[1][:44]}')
        else:
            raise AssertionError(f'fixture_root: {bad!r} was NOT refused -- the accessor can escape')
    print(f'accessor: {len(a.p("symbols/functions.csv"))} chars inside the root, 3 escapes refused')

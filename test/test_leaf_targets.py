"""Both directions for tools/check_leaf_targets.py.

A gate whose only observed run is green is a gate nobody has tested -- and after the 161
zero-fill members were retracted, the clean tree is green with zero refusals, so the refusal
half must be a fixture. Fixtures are written to a temporary directory and removed; a planted
violation is NEVER placed in game/leaf, because a body there is a body in the shipping library
(the bytes_family.cpp ghost-bodies lesson).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
GATE = os.path.join(TOOLS, 'check_leaf_targets.py')
# The gate lives in tools/, and the documented suite invocation is PYTHONPATH=. with no tools/ on
# the path. A test that only passes under the author's environment is not a test, so the sibling
# tool's directory is added here rather than assumed of the caller.
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
LEAF = os.path.join(ROOT, 'game', 'leaf')


def run_gate(leaf_dir):
    env = dict(os.environ, LEAF_TARGETS_DIR=leaf_dir, PYTHONPATH=os.path.join(ROOT, 'tools'))
    return subprocess.run([sys.executable, '-P', GATE], capture_output=True, text=True, env=env)


class LeafTargets(unittest.TestCase):
    def test_clean_tree_passes(self):
        r = run_gate(LEAF)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])

    def test_planted_zero_fill_load_is_refused(self):
        tmp = tempfile.mkdtemp(prefix='leaf-targets-')
        self.addCleanup(shutil.rmtree, tmp, True)
        # a load family whose single target sits in RW zero-fill: past filesz, inside memsz
        with open(os.path.join(tmp, 'rip_load_family.cpp'), 'w') as fh:
            fh.write('constexpr std::uint64_t v = 0x5820e88u;\n'
                     'extern "C" unsigned bb_leaf_rip_load_x(void) { return 0; }\n')
        r = run_gate(tmp)
        self.assertEqual(r.returncode, 1, 'a zero-fill load target must be refused')
        self.assertIn('rip_load', r.stderr)
        self.assertIn('filesz', r.stderr)

    def test_malformed_table_is_a_refusal_not_a_traceback(self):
        tmp = tempfile.mkdtemp(prefix='leaf-targets-')
        self.addCleanup(shutil.rmtree, tmp, True)
        with open(os.path.join(tmp, 'undeclared_family.cpp'), 'w') as fh:
            fh.write('extern "C" unsigned f(void) { return 0; }\n')
        r = run_gate(tmp)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('Traceback', r.stderr, 'a crash is not a refusal')
        self.assertIn('declares no access kind', r.stderr)


if __name__ == '__main__':
    unittest.main()

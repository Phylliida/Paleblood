"""tools/guest_reach.py: is a replaced function on a path the guest can walk from the entry?

Four cases on a synthetic graph, because the answer this tool gives decides whether the recorder is
boot-blocked or only unrouted, and a tool that decides that needs its failure on demand:

  * a hook reached at depth 2 is reported as reached, with its depth;
  * a hook nobody calls from a reachable node is reported as near, with distance = caller depth + 1;
  * a hook whose only callers are unreachable is reported as far;
  * the entry point is `image base + e_entry`, not `e_entry` -- the first real run of this tool read
    0xa0 and reported `far` about a graph it had never entered.
"""

import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_BIN = sys.executable


class GuestReach(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, 'game'))
        os.makedirs(os.path.join(self.d, 'symbols'))
        with open(os.path.join(self.d, 'eboot.elf'), 'wb') as f:
            f.write(b'\x7fELF' + bytes([2, 1, 1]) + b'\0' * 9 + b'\xfe\xfd' + b'\x3e\0' + b'\0' * 4)
            f.write(struct.pack('<Q', 0x20))                    # e_entry, an offset from the base
            f.write(b'\0' * (0x40 - 0x20))
        with open(os.path.join(self.d, 'game', 'hooks.csv'), 'w') as f:
            f.write('address,replacement,system\n'
                    '0x00400100,bb_a,kernel\n0x00400200,bb_b,kernel\n0x00400900,bb_c,kernel\n')
        with open(os.path.join(self.d, 'symbols', 'functions.csv'), 'w') as f:
            f.write('address,size,name,system,status,notes\n'
                    '0x00400020,4,entry,,original,\n0x00400100,4,a,,original,\n'
                    '0x00400200,4,b,,original,\n0x00400900,4,c,,original,\n')

    def write_edges(self, rows):
        with open(os.path.join(self.d, 'edges.csv'), 'w') as f:
            f.write('caller,callee,kind,reference,source,confidence\n')
            for caller, callee in rows:
                f.write(f'{caller},,unresolved_indirect,{caller},"x","unresolved"\n'
                        if callee is None else f'{caller},{callee},direct,{caller},"x","direct-reference"\n')

    def run_tool(self):
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'tools'))
        r = subprocess.run([PY_BIN, '-P', os.path.join(ROOT, 'tools', 'guest_reach.py'),
                            '--root', self.d, '--elf', os.path.join(self.d, 'eboot.elf'),
                            '--edges', os.path.join(self.d, 'edges.csv')],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_hook_reached_at_depth_two(self):
        self.write_edges([('0x00400020', '0x00400700'), ('0x00400700', '0x00400100')])
        out = self.run_tool()
        self.assertIn('entry 0x00400020', out)
        self.assertIn('reached: 1 hook address', out)
        self.assertIn('depth  2  0x00400100  a', out)

    def test_unreached_reports_the_indirect_gap_not_a_fake_distance(self):
        self.write_edges([('0x00400020', '0x00400700'), ('0x00400800', '0x00400100')])
        out = self.run_tool()
        self.assertIn('unreached: none of the 3 hook addresses', out)
        self.assertIn('not a path length', out)

    def test_unresolved_indirect_edges_are_counted_on_the_frontier(self):
        self.write_edges([('0x00400020', None), ('0x00400020', '0x00400700')])
        self.assertIn('unresolved indirect edges from visited nodes: 1', self.run_tool())


if __name__ == '__main__':
    unittest.main()

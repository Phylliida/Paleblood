"""The mov_rax generator's merge must dedupe within its batch, not only against the file."""
import os
import tempfile
import unittest

import catalogue
import leaf_mov_rax_gen as L


class Merge(unittest.TestCase):
    def test_two_additions_that_collide_with_each_other_enter_once(self):
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, newline='') as f:
            f.write('address,size\n0x00000010,1\n')
            path = f.name
        try:
            text = L.merged(path, [
                {'address': '0x00000020', 'size': '2'},
                {'address': '0x00000020', 'size': '2'},
            ], ['address', 'size'])
            with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, newline='') as g:
                g.write(text)
                out = g.name
            try:
                rows = list(catalogue.read_rows(out))
            finally:
                os.unlink(out)
            self.assertEqual([r['address'] for r in rows], [0x10, 0x20])
        finally:
            os.unlink(path)

    def test_an_addition_that_collides_with_the_file_is_skipped(self):
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, newline='') as f:
            f.write('address,size\n0x00000010,1\n')
            path = f.name
        try:
            text = L.merged(path, [{'address': '0x00000010', 'size': '9'}],
                            ['address', 'size'])
            with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, newline='') as g:
                g.write(text)
                out = g.name
            try:
                rows = list(catalogue.read_rows(out))
            finally:
                os.unlink(out)
            self.assertEqual(rows, [{'address': 0x10, 'size': 1}])
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()

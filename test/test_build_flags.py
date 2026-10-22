"""The verification build must not define NDEBUG.

A Release configuration passes -DNDEBUG, so every `assert()` compiles away -- in exactly the build ctest runs.
The tree currently carries no asserts, so nothing was lost; the hazard is the next one added. `-UNDEBUG` is
applied project-wide, and this test asserts that it lands *after* the type's flags in every compile line, so the
guard cannot be dropped by an edit that looks unrelated.
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAPH = ROOT / "build-release" / "build.ninja"


class VerificationBuildKeepsAssertions(unittest.TestCase):
    def test_undebug_follows_ndebug_on_every_line(self):
        self.assertTrue(GRAPH.exists(), f"no build graph at {GRAPH}: configure before running the suite")
        lines = [line for line in GRAPH.read_text(errors="replace").splitlines() if "-DNDEBUG" in line]
        self.assertGreater(len(lines), 50, f"only {len(lines)} compile lines carry -DNDEBUG: a zero sweep is not agreement")
        missing = [line for line in lines if "-UNDEBUG" not in line or line.index("-UNDEBUG") < line.index("-DNDEBUG")]
        self.assertEqual([], missing[:3], f"{len(missing)} of {len(lines)} lines define NDEBUG with no -UNDEBUG after it")


if __name__ == "__main__":
    unittest.main()

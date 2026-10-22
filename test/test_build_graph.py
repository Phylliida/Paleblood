"""Every runtime source must appear in the build graph.

runtime/CMakeLists.txt names its sources explicitly, and it has silently omitted a new file twice (tls.c,
which therefore was never compiled while I believed it was). An explicit list is the right thing to have;
the failure mode is that adding a file is a two-place edit and I keep making it in one place.
"""
import pathlib, re, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CMAKE = ROOT / "runtime/CMakeLists.txt"


class BuildGraphTest(unittest.TestCase):
    def test_pbboot_links_what_its_plugin_path_needs(self):
        """The build-graph class, fourth appearance: a file that must be in a list, and a run that silently does
        nothing when it is not. `dlopen`/`dlsym` live in libdl, and `bbrt` already links it."""
        text = CMAKE.read_text()
        self.assertRegex(text, r"target_link_libraries\(pbboot PRIVATE[^)]*\bdl\b",
                         "pbboot must link dl: the plugin path calls dlopen/dlsym")
        self.assertIn("boundary_stub.c", text, "the emitter must be in pbboot's source list")
        self.assertIn("plugin.c", text, "the plugin must be in the build graph, or the capture path installs nothing")

    def test_every_source_is_named_or_globbed(self):
        text = CMAKE.read_text()
        named = set(re.findall(r"[\w./-]+\.c\b", text))
        globbed = {p.name for p in (ROOT / "runtime/syslib").glob("*.c")}
        missing = []
        for path in list((ROOT / "runtime").glob("*.c")) + list((ROOT / "runtime/syslib").glob("*.c")):
            if path.name in named or (str(path.parent.name) == "syslib" and path.name in globbed):
                continue
            missing.append(str(path.relative_to(ROOT)))
        self.assertEqual(missing, [], "runtime sources absent from runtime/CMakeLists.txt")


if __name__ == "__main__":
    unittest.main()

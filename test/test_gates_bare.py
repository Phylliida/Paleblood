"""Gates must resolve their own imports with NO environment help.

`PYTHONPATH=tools` masked a real defect for dozens of turns: a tool that forgets to put its own directory
on sys.path imports fine under the suite and dies in the hook, where no PYTHONPATH is set. Two mechanisms
for one resolution is the one-home rule wearing a shell.

So this test runs each gate as the hook would -- cwd=/tmp so no relative import of tools/ can work, and
PYTHONPATH DELETED from the environment -- and requires rc=0 from each. If a gate needs help to start,
this is where it is told, not in a commit that happens to run under the right shell.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATES = ("check_externs.py", "check_catalogue.py")


class BareGates(unittest.TestCase):
    def run_bare(self, tool, *args, env_extra=None):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, "-P", str(ROOT / "tools" / tool), *args],
                              cwd="/tmp", capture_output=True, text=True, timeout=300, env=env)

    def test_each_gate_starts_and_passes_with_no_environment_help(self):
        for tool in GATES:
            with self.subTest(tool=tool):
                p = self.run_bare(tool)
                self.assertEqual(p.returncode, 0, f"{tool}: " + p.stdout + p.stderr)

    def test_every_tool_that_prints_nothing_did_nothing(self):
        # I deleted three `if __name__` guards and read rc=0 three times before I looked. A loader whose
        # main was deleted still exits 0 and still prints nothing, so non-empty stdout is the assertion.
        # --help is enough to catch a missing guard or a missing main: neither can print usage.
        # the roster is DERIVED from the tree, never a list of names I remember: a check that hardcodes the
        # population it enforces asserts a roster no artifact owns
        tools = sorted(p.name for p in (ROOT / "tools").glob("*.py")
                       if "__main__" in p.read_text())
        self.assertGreaterEqual(len(tools), 8, f"roster looks wrong: {tools}")
        for tool in tools:
            with self.subTest(tool=tool):
                # FIRE ON THE SIGNATURE, not on a refusal: many tools legitimately need an argument or a
                # compile_commands.json and say so. The defect I shipped was rc=0 with BOTH streams empty --
                # a tool that printed nothing because it did nothing. That is what this asserts against.
                try:
                    p = self.run_bare(tool, "--help")
                except subprocess.TimeoutExpired:
                    continue          # a tool that runs for 60s with --help is doing work, not nothing
                said_something = bool((p.stdout + p.stderr).strip())
                self.assertTrue(said_something or p.returncode != 0,
                                f"{tool}: rc=0 and both streams empty -- a tool that did nothing")

    def test_every_generator_can_still_re_emit_its_artifacts(self):
        # A committed artifact its generator cannot re-emit is a hand repair the next re-run silently
        # reverts -- it happened here, to slot_copy_cases.py. So: regenerate-and-diff, bare, and the
        # failure names the generator. A generator that does not implement --check cannot be held to this
        # at all, so it is named in a baseline that may only SHRINK: a new generator without --check is red.
        UNCHECKABLE = {"leaf_mov_rax_gen.py", "static_guard_gen.py"}   # owe: --check in both
        gens = sorted(p.name for p in (ROOT / "tools").glob("*_gen.py"))
        self.assertGreaterEqual(len(gens), 1, f"no generators found: {gens}")
        checkable = [g for g in gens if "--check" in (ROOT / "tools" / g).read_text()]
        self.assertEqual(sorted(set(gens) - set(checkable)), sorted(UNCHECKABLE),
                         "a generator without --check appeared or the baseline was not pruned")
        # a generator that needs the image says which variable to set; supply the artifact it names, and
        # when the untracked sibling is absent SAY SO rather than let a skip read as a pass
        image = ROOT.parent / "data" / "bb" / "elf" / "eboot.elf"
        extra = {"BB_IMAGE": str(image)} if image.exists() else {}
        if not extra:
            print(f"note: {image} absent -- generators needing BB_IMAGE cannot be held to regenerate-and-diff")
        for tool in checkable:
            with self.subTest(tool=tool):
                p = self.run_bare(tool, "--check", env_extra=extra)
                self.assertEqual(p.returncode, 0, f"{tool} cannot reproduce its committed artifact:\n" + p.stdout + p.stderr)

    def test_the_store_check_starts_bare_too(self):
        # injected payload: import resolution is the subject here, not the figures -- and the real build is
        # 290 s, which a bare-start guard must not cost.
        import json, tempfile
        st = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"values": {"a.b": 1}, "pending_provisional": []}, st); st.close()
        pl = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"values": {"a.b": 1}, "pending_provisional": []}, pl); pl.close()
        p = self.run_bare("derive.py", "--check", "--store", st.name, "--payload", pl.name)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("derive: ok", p.stdout)


if __name__ == "__main__":
    unittest.main()

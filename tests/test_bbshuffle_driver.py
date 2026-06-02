import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from bbshuffle_driver import UsageError, build_command


class BBShuffleDriverTests(unittest.TestCase):
    def command(self, args, env=None, mode="clang"):
        merged_env = {} if env is None else dict(env)
        return build_command(args, merged_env, mode).argv

    def test_default_on_compile_and_link(self):
        argv = self.command(["demo.c", "-o", "demo"])
        self.assertEqual(argv[0], "clang")
        self.assertIn("-fbasic-block-sections=all", argv)
        self.assertIn("-funique-basic-block-section-names", argv)
        self.assertIn("-fuse-ld=lld", argv)
        self.assertIn("-Wl,--shuffle-sections=.text*=1", argv)

    def test_no_bbshuffle_passes_through_clean_args(self):
        argv = self.command(["--no-bbshuffle", "demo.c", "-o", "demo"])
        self.assertEqual(argv, ["clang", "demo.c", "-o", "demo"])

    def test_seed_cli_override(self):
        argv = self.command(["--bbshuffle-seed=1234", "demo.c", "-o", "demo"])
        self.assertIn("-Wl,--shuffle-sections=.text*=1234", argv)

    def test_env_override_and_cli_precedence(self):
        argv = self.command(
            ["--bbshuffle-seed=2222", "demo.c", "-o", "demo"],
            {"BBSHUFFLE_SEED": "1111", "BBSHUFFLE_SECTION_GLOB": ".text.hot*"},
        )
        self.assertIn("-Wl,--shuffle-sections=.text.hot*=2222", argv)

    def test_env_can_disable_and_cli_can_reenable(self):
        disabled = self.command(["demo.c", "-o", "demo"], {"BBSHUFFLE": "0"})
        self.assertEqual(disabled, ["clang", "demo.c", "-o", "demo"])

        enabled = self.command(["--bbshuffle", "demo.c", "-o", "demo"], {"BBSHUFFLE": "0"})
        self.assertIn("-fbasic-block-sections=all", enabled)

    def test_compile_only_has_no_link_flags(self):
        argv = self.command(["-c", "demo.c", "-o", "demo.o"])
        self.assertIn("-fbasic-block-sections=all", argv)
        self.assertNotIn("-fuse-ld=lld", argv)
        self.assertFalse(any("--shuffle-sections" in arg for arg in argv))

    def test_object_only_link_has_no_compile_flags(self):
        argv = self.command(["demo.o", "-o", "demo"])
        self.assertNotIn("-fbasic-block-sections=all", argv)
        self.assertNotIn("-funique-basic-block-section-names", argv)
        self.assertIn("-fuse-ld=lld", argv)
        self.assertIn("-Wl,--shuffle-sections=.text*=1", argv)

    def test_existing_user_flags_are_not_duplicated(self):
        argv = self.command(
            [
                "-fbasic-block-sections=list=bb.txt",
                "-fno-unique-basic-block-section-names",
                "-fuse-ld=lld",
                "-Wl,--shuffle-sections=.text*=9",
                "demo.c",
                "-o",
                "demo",
            ]
        )
        self.assertEqual(argv.count("-fbasic-block-sections=all"), 0)
        self.assertEqual(argv.count("-fno-unique-basic-block-section-names"), 1)
        self.assertEqual(argv.count("-fuse-ld=lld"), 1)
        self.assertEqual(
            sum(1 for arg in argv if "--shuffle-sections" in arg),
            1,
        )

    def test_non_lld_linker_fails(self):
        with self.assertRaises(UsageError):
            build_command(["-fuse-ld=gold", "demo.c", "-o", "demo"], {}, "clang")

    def test_passthrough_version(self):
        argv = self.command(["--version"])
        self.assertEqual(argv, ["clang", "--version"])

    def test_clangxx_mode(self):
        argv = self.command(["demo.cc", "-o", "demo"], mode="clang++")
        self.assertEqual(argv[0], "clang++")
        self.assertIn("-fbasic-block-sections=all", argv)

    def test_real_compiler_env(self):
        argv = self.command(["demo.c"], {"BBSHUFFLE_REAL_CLANG": "/opt/clang"})
        self.assertEqual(argv[0], "/opt/clang")


if __name__ == "__main__":
    unittest.main()

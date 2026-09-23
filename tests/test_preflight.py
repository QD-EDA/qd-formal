import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
PIN = "7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19"
NAMES = (
    "MaxTwoErrors_M", "SingleErrorDetect_A", "SingleErrorDetectReverse_A",
    "DoubleErrorDetect_A", "DoubleErrorDetectReverse_A", "SingleErrorCorrect_A",
    "SyndromeCheck_A", "SyndromeCheckReverse_A",
)


def stub(names):
    return "\n".join(
        "Call $ivl_register_assertion(6 parameters); /* vip.sv:1 */\n"
        "  <number=0>\n  <string=\"%s\", width=1, type=bool>" % name
        for name in names
    ) + "\n"


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "opentitan"
        self.root.mkdir()
        sources = (
            "hw/ip/prim/rtl/prim_assert.sv",
            "hw/ip/prim/rtl/prim_secded_22_16_enc.sv",
            "hw/ip/prim/rtl/prim_secded_22_16_dec.sv",
            "hw/ip/prim/fpv/vip/prim_secded_22_16_assert_fpv.sv",
            "hw/ip/prim/fpv/tb/prim_secded_22_16_tb.sv",
            "hw/ip/prim/fpv/tb/prim_secded_22_16_bind_fpv.sv",
            "hw/ip/prim/rtl/prim_assert_standard_macros.svh",
            "hw/ip/prim/rtl/prim_assert_sec_cm.svh",
            "hw/ip/prim/rtl/prim_flop_macros.sv",
        )
        for rel in sources:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// test source " + rel + "\n")
        bindir = self.base / "bin"
        bindir.mkdir()
        git = bindir / "git"
        git.write_text("#!/bin/sh\ncase \"$1\" in\n rev-parse) echo \"${FAKE_REV:-" + PIN + "}\";;\n status) echo \"${FAKE_DIRTY:-}\";;\n *) exit 9;;\nesac\n")
        compiler = bindir / "iverilog"
        compiler.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys\n"
            "a=sys.argv[1:]\n"
            "if a == ['-V']:\n sys.stdout.write(os.environ.get('FAKE_VERSION','Icarus Verilog version 13.0 devel\\n'))\n sys.stderr.write(os.environ.get('FAKE_VERSION_STDERR',''))\n sys.exit(int(os.environ.get('FAKE_VERSION_EXIT','0')))\n"
            "out=pathlib.Path(a[a.index('-o')+1])\n"
            "out.write_text(pathlib.Path(os.environ['FAKE_STUB']).read_text())\n"
            "sys.stdout.write(os.environ.get('FAKE_STDOUT',''))\n"
            "sys.stderr.write(os.environ.get('FAKE_STDERR',''))\n"
            "sys.exit(int(os.environ.get('FAKE_EXIT','0')))\n"
        )
        git.chmod(0o755)
        compiler.chmod(0o755)
        self.compiler = compiler
        self.bin = bindir
        self.stubfile = self.base / "stub.txt"
        self.stubfile.write_text(stub(NAMES))

    def tearDown(self):
        self.temp.cleanup()

    def run_case(self, name, **env):
        output = self.base / name
        child_env = os.environ.copy()
        child_env.update({"PATH": str(self.bin) + os.pathsep + child_env["PATH"],
                          "FAKE_STUB": str(self.stubfile)})
        child_env.update(env)
        result = subprocess.run(
            ["python3", str(HERE / "qd_formal.py"), "preflight", str(self.root),
             str(output), "--iverilog", str(self.compiler)],
            capture_output=True, text=True, env=child_env,
        )
        return result, json.loads((output / "result.json").read_text()), output

    def test_positive_records_command_hashes_and_complete_inventory(self):
        result, report, output = self.run_case("positive")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["result"], "frontend_inventory_ok")
        self.assertFalse(report["proof"])
        self.assertEqual(report["checker_identities"], list(NAMES))
        self.assertEqual(len(report["source_sha256"]), 9)
        self.assertEqual(len(report["tool"]["sha256"]), 64)
        self.assertEqual(report["argv"][1:4], ["-g2012", "-gassertions", "-DFPV_ON"])
        self.assertEqual((output / "stdout.raw").read_bytes(), b"")
        self.assertEqual((output / "stderr.raw").read_bytes(), b"")

    def test_missing_extra_and_duplicate_checker_are_unknown(self):
        for case, names in (("missing", NAMES[:-1]),
                            ("extra", NAMES + ("DummyMacro_A",)),
                            ("duplicate", NAMES + (NAMES[0],))):
            with self.subTest(case=case):
                self.stubfile.write_text(stub(names))
                result, report, _ = self.run_case(case)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(report["result"], "UNKNOWN")
                self.assertTrue(any("inventory" in item for item in report["failure_reasons"]))

    def test_diagnostics_are_unknown_even_when_inventory_matches(self):
        result, report, output = self.run_case("diagnostic", FAKE_STDERR="warning: hidden property\n")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["result"], "UNKNOWN")
        self.assertEqual((output / "stderr.raw").read_text(), "warning: hidden property\n")

    def test_nonzero_frontend_exit_is_unknown(self):
        result, report, _ = self.run_case("nonzero", FAKE_EXIT="1")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["result"], "UNKNOWN")
        self.assertIn("Icarus frontend returned nonzero status", report["failure_reasons"])

    def test_failed_or_empty_version_query_is_unknown(self):
        for case, env in (("version-exit", {"FAKE_VERSION_EXIT": "1"}),
                          ("version-empty", {"FAKE_VERSION": ""}),
                          ("version-diagnostic", {"FAKE_VERSION_STDERR": "warning\\n"})):
            with self.subTest(case=case):
                result, report, output = self.run_case(case, **env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(report["result"], "UNKNOWN")
                self.assertIsNone(report["exit_status"])
                self.assertIn("Icarus version query failed, emitted diagnostics, or returned no version",
                              report["failure_reasons"])
                self.assertFalse((output / "opentitan-secded.stub").exists())

    def test_stale_stub_is_removed_before_frontend_runs(self):
        output = self.base / "stale"
        output.mkdir()
        (output / "opentitan-secded.stub").write_text(stub(NAMES))
        self.stubfile.unlink()
        _, report, _ = self.run_case("stale")
        self.assertEqual(report["result"], "UNKNOWN")
        self.assertFalse((output / "opentitan-secded.stub").exists())

    def test_output_inside_source_tree_is_rejected_before_creation(self):
        output = self.root / "evidence"
        result = subprocess.run(
            ["python3", str(HERE / "qd_formal.py"), "preflight", str(self.root),
             str(output), "--iverilog", str(self.compiler)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["result"], "UNKNOWN")
        self.assertFalse(output.exists())

    def test_dirty_or_wrong_pin_does_not_run_compiler(self):
        for case, env in (("dirty", {"FAKE_DIRTY": "M tracked.sv"}),
                          ("wrong-pin", {"FAKE_REV": "deadbeef"})):
            with self.subTest(case=case):
                result, report, output = self.run_case(case, **env)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(report["result"], "UNKNOWN")
                self.assertIsNone(report["exit_status"])
                self.assertFalse((output / "opentitan-secded.stub").exists())


if __name__ == "__main__":
    unittest.main()

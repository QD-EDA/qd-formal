import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from secded_one_sample import ASSUME, PROPERTY, check, expr, faulty_decoder, harness, query, replay_witness
from qd_formal import EXPECTED
from slang_inventory import EXPECTED_EXPR_SHA256


def named(name, type_):
    return {"kind": "NamedValue", "type": type_, "symbol": "1 " + name}


def count(op, value):
    return {"kind": "BinaryOp", "type": "bit", "op": op,
            "left": {"kind": "Call", "type": "int", "subroutine": "$countones",
                     "arguments": [named("error_inject_i", "logic[21:0]")]},
            "right": {"kind": "IntegerLiteral", "type": "int", "value": value}}


class OneSampleTests(unittest.TestCase):
    def setUp(self):
        self.records = {name: {"name": name, "role": role, "source_line": line,
                               "source_column": 3, "expression_sha256": EXPECTED_EXPR_SHA256[name],
                               "clock": {"edge": "PosEdge", "signal": "clk_i"},
                               "disable_iff": {"op": "CaseInequality", "left": {"op": "LogicalNot", "signal": "rst_ni"}, "right": "1'b0"}}
                        for name, role, line in ((ASSUME, "Assume", 19), (PROPERTY, "Assert", 30))}
        self.members = []
        for name, body in ((ASSUME, {"kind": "Simple", "expr": count("LessThanEqual", "2")}),
                           (PROPERTY, {"kind": "Binary", "op": "OverlappedImplication",
                                       "left": {"kind": "Simple", "expr": count("GreaterThan", "0")},
                                       "right": {"kind": "Simple", "expr": {"kind": "UnaryOp", "type": "logic",
                                                                                 "op": "BitwiseOr", "operand": named("syndrome_o", "logic[5:0]")}}})):
            record = self.records[name]
            self.members.append({"kind": "ProceduralBlock", "source_line": record["source_line"],
                                 "body": {"body": {"kind": "ConcurrentAssertion", "assertionKind": record["role"],
                                                   "source_column_start": 3,
                                                   "propertySpec": {"expr": {"expr": body}}}}})
        self.ast = {"design": {"kind": "Instance", "name": "ignored", "body": {"members": self.members}}}

    def generate(self):
        with patch("secded_one_sample.inventory", return_value=list(self.records.values())), \
             patch("secded_one_sample.instances", return_value=[(self.ast["design"],
                                                                  "prim_secded_22_16_tb.prim_secded_22_16_assert_fpv")]):
            return harness(self.ast)

    def test_positive_and_scratch_fault_equations(self):
        source, mapping = self.generate()
        self.assertIn("!(|syndrome_o)", source)
        self.assertEqual(mapping["assumption"], "($countones(error_inject_i) <= 2)")
        self.assertEqual(mapping["antecedent"], "($countones(error_inject_i) > 0)")
        self.assertIn("$countones(error_inject_i) == 2", source)

    def test_fault_changes_only_pinned_decoder_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            decoder = base / "hw/ip/prim/rtl/prim_secded_22_16_dec.sv"
            decoder.parent.mkdir(parents=True)
            decoder.write_text("22'h01496E 22'h10ACA5 unchanged")
            altered = faulty_decoder(base, base).read_text()
            self.assertEqual(altered, "22'h01496C 22'h10ACA7 unchanged")

    def test_evidence_dir_must_be_empty_and_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "chip"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "outside"):
                check(root, base, "slang", "yosys", "z3")
            out = base / "evidence"
            out.mkdir()
            (out / "old-model.smt2").write_text("stale")
            with self.assertRaisesRegex(ValueError, "empty"):
                check(root, out, "slang", "yosys", "z3")


    def test_unsupported_shape_and_clock_fail_closed(self):
        with self.assertRaises(ValueError):
            expr({"kind": "Call", "type": "int", "subroutine": "$random", "arguments": []})
        self.records[PROPERTY]["clock"]["edge"] = "NegEdge"
        with self.assertRaisesRegex(ValueError, "clock"):
            self.generate()

    def test_solver_output_must_match_expected_sat_result(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            solver = out / "solver"
            solver.write_text("#!/bin/sh\nprintf 'unknown\\n'\n")
            solver.chmod(0o755)
            model = "(define-fun |secded_sample_n bad| ((state |secded_sample_s|)) Bool true)\n"
            with self.assertRaisesRegex(ValueError, "solver output"):
                query(model, out, solver, "bad", "bad", "unsat", 5)
            self.assertEqual((out / "bad.stdout.raw").read_text(), "unknown\n")
            self.assertEqual(json.loads((out / "bad.exit.json").read_text()), {"status": 0})

    def test_bound_replay_rejects_false_green(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            tool = base / "iverilog"
            tool.write_text("fake compiler")
            tool.with_name("vvp").write_text("fake runtime")
            calls = []

            def captured(argv, cwd, out, name, timeout, allow_stderr=False):
                calls.append((name, argv))
                if name == "vvp-version":
                    (out / "vvp-version.stdout.raw").write_text("Icarus Verilog runtime version 13\n")
                    (out / "vvp-version.stderr.raw").write_text("")
                if name == "replay-stub":
                    (out / "replay.stub").write_text("registered")
                return {"vvp-version": b"Icarus runtime 13\n",
                        "replay-good-run": b"SAMPLE syndrome=11\n[ASSERT FAILED] Other_A\n",
                        "replay-fault-run": b"[ASSERT FAILED] SyndromeCheckReverse_A\nSAMPLE syndrome=00\n"}.get(name, b"")

            with patch("secded_one_sample.capture", side_effect=captured), \
                 patch("secded_one_sample.registered_identities", return_value=EXPECTED):
                with self.assertRaisesRegex(ValueError, "bound Icarus"):
                    replay_witness(base, base, tool, {"data_i": 0x09f4, "error_inject_i": 3}, 5)
            for name, argv in calls:
                if (name.startswith("replay-") and name.endswith("build")) or name == "replay-stub":
                    self.assertIn("replay", argv)
                    self.assertIn("prim_secded_22_16_bind_fpv", argv)
            with patch("secded_one_sample.capture", side_effect=captured), \
                 patch("secded_one_sample.registered_identities", return_value=EXPECTED[:-1]):
                with self.assertRaisesRegex(ValueError, "roster"):
                    replay_witness(base, base, tool, {"data_i": 0x09f4, "error_inject_i": 3}, 5)


if __name__ == "__main__":
    unittest.main()

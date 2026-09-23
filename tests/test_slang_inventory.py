import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qd_formal import EXPECTED, INCLUDES, PIN, SOURCES
from slang_inventory import (EXPECTED_EXPR_SHA256, EXPECTED_INSTANCE, SUCCESS_STDOUT,
                             VIP_SOURCE, expression_sha256, inventory, run)

FAKE_HASHES = dict.fromkeys(EXPECTED, expression_sha256(
    {"kind": "Simple", "expr": {"kind": "NamedValue", "symbol": "1 signal_i"}}))


def ast():
    members = []
    for number, name in enumerate(EXPECTED, 1):
        symbol = lambda value: {"kind": "NamedValue", "symbol": f"{1000 + number} {value}"}
        assertion = {
            "kind": "ConcurrentAssertion", "assertionKind": "Assume" if number == 1 else "Assert",
            "source_file_start": VIP_SOURCE, "source_file_end": VIP_SOURCE,
            "source_line_start": number, "source_line_end": number,
            "source_column_start": 3,
            "propertySpec": {"kind": "Clocking",
                             "clocking": {"kind": "SignalEvent", "edge": "PosEdge", "expr": symbol("clk_i")},
                             "expr": {"kind": "DisableIff", "expr": {"kind": "Simple", "expr": symbol("signal_i")},
                                      "condition": {"kind": "BinaryOp", "op": "CaseInequality",
                                                    "left": {"kind": "UnaryOp", "op": "LogicalNot",
                                                             "operand": symbol("rst_ni")},
                                                    "right": {"kind": "UnbasedUnsizedIntegerLiteral", "value": "1'b0"}}}}}
        members.extend(({"kind": "StatementBlock", "addr": number, "name": name,
                         "source_file": VIP_SOURCE, "source_line": number},
                        {"kind": "ProceduralBlock", "procedureKind": "Always",
                         "source_file": VIP_SOURCE, "source_line": number,
                         "body": {"kind": "Block", "block": f"{number} {name}", "body": assertion}}))
    return {"design": {"kind": "Root", "members": [
        {"kind": "Instance", "name": "prim_secded_22_16_tb", "body": {"members": [
            {"kind": "Instance", "name": "prim_secded_22_16_assert_fpv",
             "body": {"members": members}}]}}]}, "definitions": []}


class SlangInventoryTests(unittest.TestCase):
    def test_exact_roster_role_scope_clock_and_disable(self):
        properties = inventory(ast(), FAKE_HASHES)
        self.assertEqual([p["name"] for p in properties], list(EXPECTED))
        self.assertEqual([p["role"] for p in properties], ["Assume"] + ["Assert"] * 7)
        self.assertTrue(all(p["instance"] == EXPECTED_INSTANCE for p in properties))
        self.assertTrue(all(p["clock"] == {"edge": "PosEdge", "signal": "clk_i"} for p in properties))
        self.assertTrue(all(p["disable_iff"]["left"]["signal"] == "rst_ni" for p in properties))
        self.assertNotIn("addr", json.dumps(properties))

    def test_unresolved_or_ambiguous_label_is_unknown(self):
        for change in ("missing", "ambiguous", "wrong_ref"):
            with self.subTest(change=change):
                data = ast()
                members = data["design"]["members"][0]["body"]["members"][0]["body"]["members"]
                if change == "missing":
                    members.pop(0)
                elif change == "ambiguous":
                    members.insert(0, copy.deepcopy(members[0]))
                else:
                    members[1]["body"]["block"] = "999 MaxTwoErrors_M"
                with self.assertRaises(ValueError):
                    inventory(data, FAKE_HASHES)

    def test_role_scope_clock_and_extra_assertion_are_unknown(self):
        for change in ("role", "scope", "clock", "body", "missing_body", "extra"):
            with self.subTest(change=change):
                data = ast()
                instance = data["design"]["members"][0]["body"]["members"][0]
                proc = instance["body"]["members"][1]
                assertion = proc["body"]["body"]
                if change == "role":
                    assertion["assertionKind"] = "Assert"
                elif change == "scope":
                    instance["name"] = "different_checker"
                elif change == "clock":
                    assertion["propertySpec"]["clocking"]["edge"] = "NegEdge"
                elif change == "body":
                    assertion["propertySpec"]["expr"]["expr"]["expr"]["symbol"] = "1 changed_i"
                elif change == "missing_body":
                    del assertion["propertySpec"]["expr"]["expr"]
                else:
                    proc["body"]["extra"] = copy.deepcopy(assertion)
                with self.assertRaises(ValueError):
                    inventory(data, FAKE_HASHES)

    def test_runner_preserves_evidence_and_rejects_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, out = base / "opentitan", base / "evidence"
            root.mkdir()
            for source in (*SOURCES, *INCLUDES):
                path = root / source
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// pinned test source\n")
            fixture = base / "fixture.json"
            fixture.write_text(json.dumps(ast()))
            compiler = base / "slang"
            compiler.write_text(
                "#!/usr/bin/env python3\nimport os, pathlib, sys\n"
                "if sys.argv[1:] == ['--version']:\n print('slang version 11.0.448')\n sys.exit()\n"
                "pathlib.Path(sys.argv[sys.argv.index('--ast-json') + 1]).write_bytes("
                "pathlib.Path(os.environ['FAKE_AST']).read_bytes())\n"
                "sys.stdout.buffer.write(bytes.fromhex(os.environ['FAKE_STDOUT_HEX']))\n"
                "sys.stderr.write(os.environ.get('FAKE_STDERR', ''))\n")
            compiler.chmod(0o755)
            env = {"FAKE_AST": str(fixture), "FAKE_STDOUT_HEX": SUCCESS_STDOUT.hex()}
            with patch("slang_inventory.git_output", side_effect=[PIN, ""]), patch.dict(os.environ, env), patch.dict(EXPECTED_EXPR_SHA256, FAKE_HASHES):
                report = run(root, out, compiler, 5)
            self.assertEqual(report["result"], "semantic_frontend_inventory_ok")
            self.assertEqual(len(report["source_sha256"]), 9)
            self.assertEqual((out / "ast.raw.json").read_bytes(), fixture.read_bytes())
            self.assertEqual((out / "stdout.raw").read_bytes(), SUCCESS_STDOUT)
            self.assertEqual(len(report["tool"]["sha256"]), 64)
            with patch("slang_inventory.git_output", side_effect=[PIN, ""]), patch.dict(os.environ, {**env, "FAKE_STDERR": "warning\n"}), patch.dict(EXPECTED_EXPR_SHA256, FAKE_HASHES):
                report = run(root, out, compiler, 5)
            self.assertEqual(report["result"], "UNKNOWN")
            self.assertEqual((out / "stderr.raw").read_text(), "warning\n")


if __name__ == "__main__":
    unittest.main()

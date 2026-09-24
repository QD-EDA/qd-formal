import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pinmux_rev1_bounded import (EXPR_SHA256, INPUTS, PROPERTY, REMOVED,
                                 canonical_manifest, check_replay, parse_values, projected_sources,
                                 postcheck_inputs, query_text, selected_property)
from qd_formal import sha256


def named(name):
    return {"kind": "NamedValue", "symbol": "1 " + name}


def typed_ast():
    q = named("pinmux_hw_debug_en_q")
    body = {"kind": "Binary", "op": "OverlappedImplication",
            "left": {"kind": "SequenceConcat", "elements": [
                {"min": 0, "max": 0, "sequence": {"expr": {
                    "kind": "Call", "subroutine": "2 lc_tx_test_false_loose",
                    "arguments": [q]}}},
                {"min": 1, "max": 1, "sequence": {"expr": {
                    "kind": "Call", "subroutine": "3 lc_tx_test_true_strict",
                    "arguments": [q]}}}]},
            "right": {"kind": "Simple", "expr": {"kind": "Call",
                      "subroutine": "$past", "arguments": [named("strap_en_i")]}}}
    assertion = {"kind": "ConcurrentAssertion", "assertionKind": "Assert",
                 "source_line_start": 223, "source_line_end": 223,
                 "source_file_start": "x/pinmux_strap_sampling.sv",
                 "propertySpec": {"kind": "Clocking", "clocking": {
                     "kind": "SignalEvent", "edge": "PosEdge", "expr": named("clk_i")},
                     "expr": {"kind": "DisableIff", "condition": {
                         "op": "CaseInequality", "left": {"op": "LogicalNot",
                             "operand": named("rst_ni")}, "right": {"value": "1'b0"}},
                         "expr": body}}}
    instance = {"kind": "Instance", "name": "pinmux_strap_sampling", "body": {
        "members": [{"kind": "StatementBlock", "name": PROPERTY, "source_line": 223},
                    {"kind": "ProceduralBlock", "source_line": 223,
                     "body": {"body": assertion}}]}}
    return {"design": instance}, body


def replay_lines(q, straps, failure=""):
    return "".join(f"SAMPLE time={6+10*i} q={v} strap={straps[i]}\n"
                   for i, v in enumerate(q)) + failure


class Rev1BoundedTests(unittest.TestCase):
    def test_relocated_core_paths_keep_canonical_edam_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            outputs = []
            for name in ("first", "second"):
                root = base / name / "chip"
                core = root / "hw/core.core"
                core.parent.mkdir(parents=True)
                core.write_text("pinned core")
                export = base / name / "build"
                generated = export / "generator_cache/gen.core"
                generated.parent.mkdir(parents=True)
                generated.write_text("generated core")
                edam = export / "design.eda.yml"
                edam.write_text("files:\n- name: src/a.sv\n- name: src/b.sv\n"
                                "cores:\n  chip:\n    core_file: "
                                + os.path.relpath(core, export) + "\n"
                                "  generated:\n    core_file: generator_cache/gen.core\n"
                                "dependencies:\n- first\n- second\n")
                outputs.append((root, edam))
            expected = {"files": [{"name": "src/a.sv"}, {"name": "src/b.sv"}],
                        "cores": {"chip": {"core_file": "@opentitan/hw/core.core"},
                                  "generated": {"core_file": "generator_cache/gen.core"}},
                        "dependencies": ["first", "second"]}
            digest = hashlib.sha256(json.dumps(expected, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
            with patch("pinmux_rev1_bounded.GENERATED_CORE", "generator_cache/gen.core"), \
                 patch("pinmux_rev1_bounded.GENERATED_CORE_SHA256", sha256(outputs[0][1].parent / "generator_cache/gen.core")), \
                 patch("pinmux_rev1_bounded.SOURCE_CORE_COUNT", 1), \
                 patch("pinmux_rev1_bounded.CANONICAL_EDAM_SHA256", digest):
                first = canonical_manifest(*outputs[0])
                self.assertEqual(first, canonical_manifest(*outputs[1]))
                edited = outputs[1][1].read_text().replace("- first\n- second", "- second\n- first")
                outputs[1][1].write_text(edited)
                with self.assertRaisesRegex(ValueError, "canonical EDAM"):
                    canonical_manifest(*outputs[1])

    def test_core_path_escape_missing_and_duplicate_yaml_are_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, export = base / "chip", base / "build"
            root.mkdir()
            export.mkdir()
            core = root / "core.core"
            core.write_text("core")
            outside = base / "outside.core"
            outside.write_text("outside")
            generated = export / "generator_cache/gen.core"
            generated.parent.mkdir()
            generated.write_text("generated")
            edam = export / "design.eda.yml"
            expected = {"cores": {"chip": {"core_file": "@opentitan/core.core"},
                                  "generated": {"core_file": "generator_cache/gen.core"}}}
            digest = hashlib.sha256(json.dumps(expected, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
            def write_core(path):
                edam.write_text("cores:\n  chip:\n    core_file: " + path + "\n"
                                "  generated:\n    core_file: generator_cache/gen.core\n")
            with patch("pinmux_rev1_bounded.GENERATED_CORE", "generator_cache/gen.core"), \
                 patch("pinmux_rev1_bounded.GENERATED_CORE_SHA256", sha256(generated)), \
                 patch("pinmux_rev1_bounded.SOURCE_CORE_COUNT", 1), \
                 patch("pinmux_rev1_bounded.CANONICAL_EDAM_SHA256", digest):
                write_core(os.path.relpath(core, export))
                canonical_manifest(root, edam)
                write_core(os.path.relpath(outside, export))
                with self.assertRaisesRegex(ValueError, "core_file"):
                    canonical_manifest(root, edam)
                core.unlink()
                core.symlink_to(outside)
                write_core(os.path.relpath(core, export))
                with self.assertRaisesRegex(ValueError, "core_file"):
                    canonical_manifest(root, edam)
                core.unlink()
                with self.assertRaisesRegex(ValueError, "core_file"):
                    canonical_manifest(root, edam)
                core.write_text("core")
                generated.write_text("changed")
                with self.assertRaisesRegex(ValueError, "generated core_file"):
                    canonical_manifest(root, edam)
                generated.write_text("generated")
                edam.write_text(edam.read_text() + "cores: {}\n")
                with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
                    canonical_manifest(root, edam)
                edam.write_text("cores: [unterminated\n")
                with self.assertRaisesRegex(ValueError, "invalid EDAM YAML"):
                    canonical_manifest(root, edam)

    def test_any_exported_dependency_change_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            edam = base / "design.eda.yml"
            edam.write_text("test")
            names = [f"src/generated/rtl/other{i}.sv" for i in range(217)] + sorted(REMOVED)
            names += [f"src/include{i % 4}/macro{i}.svh" for i in range(9)]
            files = []
            for name in names:
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
                files.append({"name": name, "file_type": "systemVerilogSource",
                              "is_include_file": name.endswith(".svh")})
            manifest = {"toplevel": "pinmux_chip_tb", "parameters": {},
                        "tool_options": {"icarus": {}}, "files": files}
            hashes = {name: sha256(base / name) for name in names}
            aggregate = hashlib.sha256(json.dumps(hashes, sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
            with patch("pinmux_rev1_bounded.canonical_manifest", return_value=(manifest, "fixture")), \
                 patch("pinmux_rev1_bounded.EXPORT_SHA256", aggregate), \
                 patch("pinmux_rev1_bounded.SOURCE_EQUIVALENCE", {}), \
                patch("pinmux_rev1_bounded.git_output", side_effect=lambda _, args: "7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19" if args[0] == "rev-parse" else ""):
                inventory = projected_sources(base, edam, base)
                edam_digest = sha256(edam)
                self.assertEqual(len(inventory[1]), 217)
                postcheck_inputs(base, edam, base, edam_digest, inventory)
                (base / "src/include0/unlisted.svh").write_text("unexpected include")
                with self.assertRaisesRegex(ValueError, "source tree"):
                    postcheck_inputs(base, edam, base, edam_digest, inventory)
                (base / "src/include0/unlisted.svh").unlink()
                (base / names[0]).write_text("mutated dependency")
                with self.assertRaisesRegex(ValueError, "exported source bytes"):
                    postcheck_inputs(base, edam, base, edam_digest, inventory)
                (base / names[0]).write_text(names[0])
                edam.write_text("changed EDAM")
                with self.assertRaisesRegex(ValueError, "EDAM changed"):
                    postcheck_inputs(base, edam, base, edam_digest, inventory)

    def test_exact_typed_temporal_shape(self):
        ast, body = typed_ast()
        with patch("pinmux_rev1_bounded.expression_sha256", return_value=EXPR_SHA256):
            self.assertEqual(selected_property(ast)["mapping"],
                             "q[n] != On && q[n+1] == On -> strap_en_i[n]")
            body["left"]["elements"][1]["min"] = 2
            with self.assertRaisesRegex(ValueError, "sequence"):
                selected_property(ast)
            body["left"]["elements"][1]["min"] = 1
            ast["design"]["body"]["members"][1]["body"]["body"]["propertySpec"]["clocking"]["edge"] = "NegEdge"
            with self.assertRaisesRegex(ValueError, "clock"):
                selected_property(ast)
        ast, _ = typed_ast()
        with self.assertRaisesRegex(ValueError, "expression"):
            selected_property(ast)

    def test_unconstrained_bad_and_fixed_boundary_queries(self):
        model = "; model\n"
        bad = query_text(model, 3, "bad")
        self.assertIn("(not (= (|pinmux_strap_sampling_n pinmux_hw_debug_en_q| s3) #b0101))", bad)
        self.assertIn("(not (|pinmux_strap_sampling_n strap_en_i| s3))", bad)
        self.assertNotIn("lc_hw_debug_en_i", bad)
        self.assertIn("(not (|pinmux_strap_sampling_n rst_ni| s0))", bad)
        reset = query_text(model, 1, "reset_bad")
        self.assertIn("(assert (not (= (|pinmux_strap_sampling_n pinmux_hw_debug_en_q| s1) #b1010)))", reset)
        cover = query_text(model, 4, "cover", fixed=True)
        self.assertIn("(assert (|pinmux_strap_sampling_n strap_en_i| s4))", cover)
        fault = query_text(model, 3, "bad", fixed=True)
        self.assertIn("(assert (not (|pinmux_strap_sampling_n strap_en_i| s4)))", fault)
        self.assertIn("(assert (= (|pinmux_strap_sampling_n attr_core_i| s3) (_ bv0 882)))", fault)
        self.assertIn("(assert (= (|pinmux_strap_sampling_n scanmode_i| s3) #b1010))", fault)
        with self.assertRaisesRegex(ValueError, "unsupported query"):
            query_text(model, 5, "bad")

    def test_witness_requires_every_replayed_input(self):
        pairs = []
        for i in range(1, 5):
            for name in INPUTS:
                value = "true" if name == "rst_ni" else ("false" if name == "strap_en_i" else "#xa")
                pairs.append(f"((|pinmux_strap_sampling_n {name}| s{i}) {value})")
        for i in range(1, 6):
            pairs.append(f"((|pinmux_strap_sampling_n pinmux_hw_debug_en_q| s{i}) #xa)")
        output = "sat\n(" + "\n".join(pairs) + ")\n"
        inputs, q = parse_values(output)
        self.assertEqual(len(inputs), 4)
        self.assertEqual(q, ["#xa"] * 5)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            parse_values(output.replace(pairs[0], ""))
        with self.assertRaisesRegex(ValueError, "duplicated"):
            parse_values(output.replace(pairs[0], pairs[0] + pairs[0]))

    def test_vvp_zero_exit_never_masks_named_failure_or_wrong_sample(self):
        good = replay_lines("aaaa5", "000111")
        control = replay_lines("aaaaaa", "000000")
        fault = replay_lines("aaa555", "000000",
                             "ERROR: checker [ASSERT FAILED] LcHwDebugEnSetRev1_A\n"
                             "       Time: 45 Scope: replay.dut\n")
        check_replay(good, control, fault,
                     ["#xa"] * 4 + ["#x5"], ["#xa"] * 5,
                     ["#xa"] * 3 + ["#x5"] * 2)
        with self.assertRaisesRegex(ValueError, "original Rev1"):
            check_replay(good, control, fault.replace("LcHwDebugEnSetRev1_A", "Other_A"),
                         ["#xa"] * 4 + ["#x5"], ["#xa"] * 5,
                         ["#xa"] * 3 + ["#x5"] * 2)
        with self.assertRaisesRegex(ValueError, "trace differs"):
            check_replay(good.replace("time=36 q=a", "time=36 q=5"), control, fault,
                         ["#xa"] * 4 + ["#x5"], ["#xa"] * 5,
                         ["#xa"] * 3 + ["#x5"] * 2)


if __name__ == "__main__":
    unittest.main()

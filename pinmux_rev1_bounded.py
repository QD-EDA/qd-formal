#!/usr/bin/env python3
"""Five-transition, two-state check of the pinned synthesized pinmux model."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from qd_formal import PIN, git_output, registered_identities, sha256
from secded_one_sample import capture, require
from slang_inventory import expression_sha256, instances, symbol

PROPERTY = "LcHwDebugEnSetRev1_A"
EXPR_SHA256 = "b457f6375c91aac1749cc82fa1710921282de59856b04b4b7239a794c1cc8caa"
CANONICAL_EDAM_SHA256 = "b83c37dcb51cdcbd8c0bf3cfb1c48690f516b2be74e7ff767592262eacac927e"
EXPORT_SHA256 = "c208d8ffc22661e9ec61ef023bb9f8e4c78ae75d35df19fff89159757b1780f2"
GENERATED_CORE = "generator_cache/lowrisc_earlgrey_systems_pinmux_chip_fpv-csr_assert_gen_0.1-75c3f8561083e7c367faf4dc2737a4e4aa899eaa993d816ac7b11e3e53df733e/pinmux_csr_assert_fpv.core"
GENERATED_CORE_SHA256 = "83e628f750b2bb709fa59850b73e6974fdb3a3ff288bfcca19d60c5cfe3dac74"
SOURCE_CORE_COUNT = 85
SAMPLER = "hw/top_earlgrey/ip_autogen/pinmux/rtl/pinmux_strap_sampling.sv"
REMOVED = {
    "src/lowrisc_earlgrey_fpv_pinmux_common_fpv_0.1/vip/pinmux_assert_fpv.sv",
    "src/lowrisc_earlgrey_fpv_pinmux_common_fpv_0.1/tb/pinmux_bind_fpv.sv",
    "src/lowrisc_earlgrey_systems_pinmux_chip_fpv_0.1/tb/pinmux_chip_tb.sv",
    "src/lowrisc_fpv_pinmux_csr_assert_0/pinmux_csr_assert_fpv.sv",
}
SOURCE_EQUIVALENCE = {
    "pinmux_strap_sampling.sv": SAMPLER,
    "lc_ctrl_pkg.sv": "hw/ip/lc_ctrl/rtl/lc_ctrl_pkg.sv",
    "prim_lc_sender.sv": "hw/ip/prim/rtl/prim_lc_sender.sv",
    "prim_lc_or_hardened.sv": "hw/ip/prim/rtl/prim_lc_or_hardened.sv",
    "prim_lc_sync.sv": "hw/ip/prim/rtl/prim_lc_sync.sv",
}
INPUTS = ("rst_ni", "strap_en_i", "lc_hw_debug_en_i", "lc_hw_debug_clr_i",
          "lc_check_byp_en_i", "lc_escalate_en_i")
TIED_INPUTS = {"clk_i": "true", "scanmode_i": "#b1010", "lc_dft_en_i": "#b1010",
               "dft_hold_tap_sel_i": "false", "attr_core_i": "(_ bv0 882)",
               "out_core_i": "(_ bv0 63)", "oe_core_i": "(_ bv0 63)",
               "in_padring_i": "(_ bv0 63)", "lc_jtag_i": "#b00",
               "rv_jtag_i": "#b00", "dft_jtag_i": "#b00"}
LOCAL_NAMES = {"LcHwDebugEnSet_A", "LcHwDebugEnSetRev0_A", PROPERTY,
               "LcHwDebugEnClear_A", "RvTapOff0_A", "RvTapOff1_A",
               "DftTapOff0_A", "RvTapOff2_A", "RvTapOff3_A", "DftTapOff1_A"}


def canonical_manifest(root, edam):
    """Pin EDAM semantics while allowing only source checkout relocation."""
    try:
        import yaml
    except ImportError as error:
        raise ValueError("PyYAML is required to read the pinned EDAM") from error

    class UniqueKeys(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            mapping = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                require(key not in mapping, "duplicate YAML key")
                mapping[key] = self.construct_object(value_node, deep=deep)
            return mapping

    try:
        manifest = yaml.load(edam.read_text(), Loader=UniqueKeys)
    except yaml.YAMLError as error:
        raise ValueError("invalid EDAM YAML") from error
    require(isinstance(manifest, dict) and isinstance(manifest.get("cores"), dict),
            "unsupported EDAM structure")
    checkout = Path(os.path.abspath(root))
    export = Path(os.path.abspath(edam.parent))
    source_cores = generated_cores = 0
    for core in manifest["cores"].values():
        require(isinstance(core, dict) and isinstance(core.get("core_file"), str),
                "unsupported core_file")
        value = core["core_file"]
        path = Path(os.path.abspath(export / value))
        if value == GENERATED_CORE:
            require(path.is_file() and path.resolve().is_relative_to(export.resolve())
                    and sha256(path) == GENERATED_CORE_SHA256, "generated core_file differs")
            generated_cores += 1
        else:
            require(path.is_relative_to(checkout) and path.is_file()
                    and path.resolve().is_relative_to(checkout.resolve()),
                    "core_file escapes or is missing from pinned checkout")
            core["core_file"] = "@opentitan/" + path.relative_to(checkout).as_posix()
            source_cores += 1
    require((source_cores, generated_cores) == (SOURCE_CORE_COUNT, 1),
            "EDAM core_file roster differs")
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    require(digest == CANONICAL_EDAM_SHA256, "canonical EDAM differs from pinned FPV setup")
    return manifest, digest


def projected_sources(root, edam, out):
    """Use the pinned FuseSoC export, excluding only the broken chip FPV top and unused VIP."""
    manifest, canonical_digest = canonical_manifest(root, edam)
    require(manifest.get("toplevel") == "pinmux_chip_tb"
            and manifest.get("parameters") == {}
            and manifest.get("tool_options") == {"icarus": {}}, "unsupported EDAM options")
    files = manifest["files"]
    require(len(files) == 230 and all(f.get("file_type") == "systemVerilogSource" for f in files),
            "unsupported EDAM file roster")
    included = [f for f in files if f.get("is_include_file")]
    compiled = [f for f in files if not f.get("is_include_file")]
    require(len(included) == 9 and len(compiled) == 221, "EDAM roster differs")
    listed = {f["name"] for f in files}
    exported = {p.relative_to(edam.parent).as_posix()
                for p in (edam.parent / "src").rglob("*") if p.is_file()}
    require(exported == listed, "exported source tree differs from EDAM roster")
    require({f["name"] for f in compiled if f["name"] in REMOVED} == REMOVED,
            "excluded FPV units differ")
    selected = [f for f in compiled if f["name"] not in REMOVED]
    require(len(selected) == 217, "selected RTL source count differs")
    base = edam.parent
    dirs = list(dict.fromkeys(str((base / f["name"]).parent) for f in included))
    sources = [base / f["name"] for f in selected]
    require(len(dirs) == 4 and all(Path(d).is_dir() for d in dirs)
            and all(path.is_file() for path in sources), "missing exported source or include")
    hashes = {f["name"]: sha256(base / f["name"]) for f in files}
    aggregate = hashlib.sha256(json.dumps(hashes, sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()
    require(len(hashes) == 230 and aggregate == EXPORT_SHA256,
            "exported source bytes differ from pinned FPV setup")
    for basename, original in SOURCE_EQUIVALENCE.items():
        matches = [f for f in selected if Path(f["name"]).name == basename]
        require(len(matches) == 1 and hashes[matches[0]["name"]] == sha256(root / original),
                basename + " differs from pinned OpenTitan")
    vf = out / "sampler.vf"
    vf.write_text("".join(f"-I {d}\n" for d in dirs)
                  + "".join(f"{s}\n" for s in sources))
    return dirs, sources, hashes, vf, canonical_digest


def selected_property(ast):
    """Accept only the exact typed Rev1 temporal expression in the sampler instance."""
    matches, labels = [], []
    for instance, path in instances(ast.get("design")):
        if path != "pinmux_strap_sampling":
            continue
        members = instance.get("body", {}).get("members", [])
        labels = [m for m in members if m.get("kind") == "StatementBlock"
                  and m.get("name") == PROPERTY and m.get("source_line") == 223]
        for member in members:
            if member.get("kind") != "ProceduralBlock" or member.get("source_line") != 223:
                continue
            assertion = member.get("body", {}).get("body", {})
            if assertion.get("kind") == "ConcurrentAssertion":
                matches.append(assertion)
    require(len(matches) == len(labels) == 1, "Rev1 label or assertion is ambiguous")
    assertion = matches[0]
    require(assertion.get("assertionKind") == "Assert"
            and assertion.get("source_line_start") == 223
            and assertion.get("source_line_end") == 223
            and assertion.get("source_file_start", "").endswith("/pinmux_strap_sampling.sv"),
            "Rev1 identity differs")
    spec = assertion.get("propertySpec", {})
    event, disabled = spec.get("clocking", {}), spec.get("expr", {})
    condition = disabled.get("condition", {})
    require(spec.get("kind") == "Clocking" and event.get("kind") == "SignalEvent"
            and event.get("edge") == "PosEdge"
            and symbol(event.get("expr", {}).get("symbol", "")) == "clk_i"
            and disabled.get("kind") == "DisableIff"
            and condition.get("op") == "CaseInequality"
            and condition.get("left", {}).get("op") == "LogicalNot"
            and symbol(condition.get("left", {}).get("operand", {}).get("symbol", "")) == "rst_ni"
            and condition.get("right", {}).get("value") == "1'b0", "unsupported Rev1 clock/reset")
    body = disabled.get("expr", {})
    require(expression_sha256(body) == EXPR_SHA256, "Rev1 expression differs")
    seq = body.get("left", {}).get("elements", [])
    require(body.get("kind") == "Binary" and body.get("op") == "OverlappedImplication"
            and body.get("left", {}).get("kind") == "SequenceConcat" and len(seq) == 2
            and [(x.get("min"), x.get("max")) for x in seq] == [(0, 0), (1, 1)]
            and body.get("right", {}).get("kind") == "Simple", "unsupported Rev1 sequence")
    calls = [x.get("sequence", {}).get("expr", {}) for x in seq]
    require([symbol(x.get("subroutine", "")) for x in calls]
            == ["lc_tx_test_false_loose", "lc_tx_test_true_strict"]
            and all(symbol(x.get("arguments", [{}])[0].get("symbol", ""))
                    == "pinmux_hw_debug_en_q" for x in calls)
            and body["right"]["expr"].get("subroutine") == "$past"
            and symbol(body["right"]["expr"].get("arguments", [{}])[0].get("symbol", ""))
            == "strap_en_i", "unsupported Rev1 operands")
    return {"name": PROPERTY, "source_line": 223, "expression_sha256": EXPR_SHA256,
            "clock": "posedge clk_i", "disable": "!rst_ni !== 1'b0",
            "mapping": "q[n] != On && q[n+1] == On -> strap_en_i[n]"}


def fixed_inputs(strap_last):
    terms = []
    for step in range(6):
        for name, value in TIED_INPUTS.items():
            terms.append(f"(assert (= (|pinmux_strap_sampling_n {name}| s{step}) {value}))")
        for name, value in (("lc_hw_debug_en_i", "0101"),
                            ("lc_hw_debug_clr_i", "1010"),
                            ("lc_check_byp_en_i", "1010"),
                            ("lc_escalate_en_i", "1010")):
            if name == "lc_hw_debug_en_i" and step == 0:
                value = "1010"
            terms.append(f"(assert (= (|pinmux_strap_sampling_n {name}| s{step}) #b{value}))")
        strap_value = step >= 4 and strap_last
        signal = f"(|pinmux_strap_sampling_n strap_en_i| s{step})"
        terms.append(f"(assert {signal if strap_value else '(not ' + signal + ')'})")
    return "\n".join(terms) + "\n"


def query_text(model, pair, kind, fixed=False, values=False):
    require(pair in (1, 2, 3, 4) and kind in ("bad", "cover", "trace", "reset_bad"),
            "unsupported query")
    pre = (model + "\n" + "".join(
        f"(declare-fun s{i} () |pinmux_strap_sampling_s|)\n"
        f"(assert (|pinmux_strap_sampling_h| s{i}))\n" for i in range(6))
        + "".join(f"(assert (|pinmux_strap_sampling_t| s{i} s{i+1}))\n" for i in range(5))
        + "(assert (not (|pinmux_strap_sampling_n rst_ni| s0)))\n"
        + "".join(f"(assert (|pinmux_strap_sampling_n rst_ni| s{i}))\n" for i in range(1, 6)))
    q = lambda i: f"(|pinmux_strap_sampling_n pinmux_hw_debug_en_q| s{i})"
    strap = f"(|pinmux_strap_sampling_n strap_en_i| s{pair})"
    if kind == "reset_bad":
        pre += f"(assert (not (= {q(1)} #b1010)))\n"
    elif kind != "trace":
        pre += f"(assert (and (not (= {q(pair)} #b0101)) (= {q(pair+1)} #b0101)"
        pre += f" {'(not ' + strap + ')' if kind == 'bad' else strap}))\n"
    else:
        pre += "".join(f"(assert (not (= {q(i)} #b0101)))\n" for i in range(1, 6))
    if fixed:
        pre += fixed_inputs(kind == "cover")
    pre += "(check-sat)\n"
    if values:
        items = [f"(|pinmux_strap_sampling_n {name}| s{i})"
                 for i in range(1, 5) for name in INPUTS]
        items += [q(i) for i in range(1, 6)]
        pre += "(get-value (" + " ".join(items) + "))\n"
    return pre


def parse_values(output):
    pattern = r"\(\(\|pinmux_strap_sampling_n ([A-Za-z_]+)\| s([1-5])\) (true|false|#x[0-9a-f]+|#b[01]+)\)"
    matches = re.findall(pattern, output)
    found = {(int(step), name): value for name, step, value in matches}
    expected = {(i, name) for i in range(1, 5) for name in INPUTS}
    expected.update((i, "pinmux_hw_debug_en_q") for i in range(1, 6))
    require(len(matches) == len(found) == len(expected) and set(found) == expected,
            "solver witness is incomplete or duplicated")
    require(all(found[i, "rst_ni"] == "true" for i in range(1, 5)),
            "solver witness reset differs")
    return {str(i): {name: found[i, name] for name in INPUTS} for i in range(1, 5)}, \
           [found[i, "pinmux_hw_debug_en_q"] for i in range(1, 6)]


def replay_source(inputs):
    lines = ["module replay;", "  reg clk_i = 0, rst_ni = 0, strap_en_i = 0;",
             "  reg [3:0] lc_hw_debug_en_i = 4'ha, lc_hw_debug_clr_i = 4'ha;",
             "  reg [3:0] lc_check_byp_en_i = 4'ha, lc_escalate_en_i = 4'ha;",
             "  pinmux_strap_sampling dut (",
             "    .clk_i, .rst_ni, .scanmode_i(4'ha),",
             "    .attr_padring_o(), .out_padring_o(), .oe_padring_o(), .in_padring_i('0),",
             "    .attr_core_i('0), .out_core_i('0), .oe_core_i('0), .in_core_o(),",
             "    .strap_en_i, .lc_dft_en_i(4'ha), .lc_hw_debug_clr_i,",
             "    .lc_hw_debug_en_i, .lc_check_byp_en_i, .lc_escalate_en_i,",
             "    .pinmux_hw_debug_en_o(), .dft_strap_test_o(), .dft_hold_tap_sel_i(1'b0),",
             "    .lc_jtag_o(), .lc_jtag_i('0), .rv_jtag_o(), .rv_jtag_i('0),",
             "    .dft_jtag_o(), .dft_jtag_i('0));",
             "  always #5 clk_i = ~clk_i;", "  initial begin"]
    for i in range(1, 5):
        lines.append("    #" + ("6" if i == 1 else "10") + ";")
        for name in INPUTS:
            value = inputs[str(i)][name]
            if name in ("rst_ni", "strap_en_i"):
                require(value in ("true", "false"), "unsupported Boolean witness")
                value = "1'b" + ("1" if value == "true" else "0")
            else:
                require(re.fullmatch(r"#x[0-9a-f]", value) is not None,
                        "unsupported four-bit witness")
                value = "4'h" + value[2:]
            lines.append(f"    {name} = {value};")
    lines += ["    #20; $finish;", "  end",
              '  always @(posedge clk_i) begin',
              '    #2; $display("SAMPLE time=%0t q=%h strap=%b", $time, dut.pinmux_hw_debug_en_q, strap_en_i);',
              "  end", "endmodule"]
    return "\n".join(lines) + "\n"


def check_replay(good, control, fault, good_q, control_q, fault_q):
    """VVP returns zero even on $error; inspect the original named assertion."""
    sample = re.compile(r"SAMPLE time=(\d+) q=([0-9a-f]) strap=([01])")
    good_samples, control_samples, fault_samples = (sample.findall(x)
                                                    for x in (good, control, fault))
    require(["#x" + q for _, q, _ in good_samples[:5]] == good_q
            and ["#x" + q for _, q, _ in control_samples[:5]] == control_q
            and ["#x" + q for _, q, _ in fault_samples[:5]] == fault_q,
            "Icarus sample trace differs from SMT witness")
    require("[ASSERT FAILED]" not in good and "ERROR:" not in good,
            "original RTL replay failed")
    require("[ASSERT FAILED]" not in control and "ERROR:" not in control,
            "original RTL failed on mutant witness inputs")
    failures = re.findall(r"\[ASSERT FAILED\] ([A-Za-z_][A-Za-z_0-9]*)", fault)
    require(failures == [PROPERTY] and "Time: 45" in fault,
            "scratch fault did not trigger only original Rev1 at the aligned sample")
    require(good_samples[3][1] == "a" and good_samples[4][1] == "5"
            and good_samples[3][2] == "1"
            and fault_samples[2][1] == "a" and fault_samples[3][1] == "5"
            and fault_samples[2][2] == "0", "rise/strap alignment differs")


def check(root, edam, out, slang, yosys, z3, iverilog, timeout=120):
    root, edam, out = Path(os.path.abspath(root)), Path(os.path.abspath(edam)), Path(out).resolve()
    require(root != out and root not in out.parents and out not in root.parents,
            "evidence must be outside chip checkout")
    require(not out.exists() or not any(out.iterdir()), "evidence directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "result": "UNKNOWN",
              "claim": "five_transition_two_state_synthesized_sampler_model",
              "property": PROPERTY, "opentitan_pin": PIN, "failure_reasons": [], "tools": {},
              "queries": {}, "source_sha256": {},
              "scope": {"reset": "s0 rst_ni=0; s1..s5 rst_ni=1",
                        "bad_queries": "all other sampler inputs free at every state",
                        "cover_and_replay": "all top-level sampler inputs fixed to recorded values at s0..s5",
                        "semantics": "Yosys read_slang synthesized two-state transition model; original SVA typed separately",
                        "full_original_sva_or_chip_policy": "UNKNOWN"}}
    try:
        require(git_output(root, ["rev-parse", "HEAD"]) == PIN
                and not git_output(root, ["status", "--porcelain", "--untracked-files=all"]),
                "source checkout is not clean at pin")
        report["edam_sha256"] = sha256(edam)
        dirs, sources, hashes, vf, canonical_digest = projected_sources(root, edam, out)
        report["canonical_edam_sha256"] = canonical_digest
        report["source_sha256"] = hashes
        for name, tool, version_flag in (("slang", slang, "--version"), ("yosys", yosys, "-V"),
                                         ("z3", z3, "-version"), ("iverilog", iverilog, "-V")):
            path = Path(shutil.which(str(tool)) or tool).resolve()
            capture([str(path), version_flag], root, out, name + "-version", timeout,
                    allow_stderr=True)
            version = ((out / f"{name}-version.stdout.raw").read_bytes()
                       + (out / f"{name}-version.stderr.raw").read_bytes()).decode(errors="replace")
            report["tools"][name] = {"path": str(path), "sha256": sha256(path),
                                     "version": version.splitlines()[0] if version else ""}
        require(report["tools"]["slang"]["version"].startswith("slang version 11.0.448+"),
                "unsupported slang version")
        slang_path = report["tools"]["slang"]["path"]
        ast_path = out / "sampler.ast.json"
        capture([slang_path, "--top", "pinmux_strap_sampling", "--single-unit", "-DFPV_ON",
                 "--ast-json", str(ast_path), "--ast-json-source-info", "-f", str(vf)],
                root, out, "slang", timeout)
        report["typed_property"] = selected_property(json.loads(ast_path.read_text()))
        icarus = report["tools"]["iverilog"]["path"]
        base_argv = [icarus, "-g2012", "-gassertions", "-DFPV_ON", "-s", "pinmux_strap_sampling"]
        base_argv += ["-I" + d for d in dirs]
        stub = out / "sampler.stub"
        capture(base_argv + ["-t", "stub", "-o", str(stub)] + list(map(str, sources)),
                root, out, "icarus-stub", timeout)
        roster = Counter(registered_identities(stub.read_text()))
        require(set(LOCAL_NAMES).issubset(roster)
                and all(roster[name] == 1 for name in LOCAL_NAMES)
                and roster == Counter({**{name: 1 for name in LOCAL_NAMES},
                                       "OutputDelay_A": 9, "FunctionCheck_A": 1}),
                "Icarus assertion roster differs")
        report["icarus_roster"] = dict(roster)
        original = root / SAMPLER
        source = original.read_text()
        old = "assign lc_hw_debug_en_masked = lc_tx_and_hi(lc_strap_en, lc_hw_debug_en[0]);"
        require(source.count(old) == 1, "scratch fault site differs")
        mutant = out / "faulty_sampler.sv"
        mutant.write_text(source.replace(old, "assign lc_hw_debug_en_masked = lc_hw_debug_en[0];"))
        sampler_export = next(s for s in sources if s.name == "pinmux_strap_sampling.sv")
        model_data = {}
        for variant in ("good", "fault"):
            variant_sources = [mutant if variant == "fault" and s == sampler_export else s
                               for s in sources]
            variant_vf = out / f"{variant}.vf"
            variant_vf.write_text("".join(f"-I {d}\n" for d in dirs)
                                  + "".join(f"{s}\n" for s in variant_sources))
            smt = out / f"{variant}.smt2"
            script = out / f"{variant}.ys"
            script.write_text(f"read_slang --top pinmux_strap_sampling --single-unit -DFPV_ON -f {variant_vf}\n"
                              "prep -top pinmux_strap_sampling -flatten\ncheck -assert\n"
                              f"async2sync\ndffunmap\nwrite_smt2 -wires {smt}\n")
            yosys_output = capture([report["tools"]["yosys"]["path"], "-Q", "-s", str(script)],
                                   root, out, f"yosys-{variant}", timeout)
            require(b"Build succeeded: 0 errors, 0 warnings" in yosys_output
                    and b"Found and reported 0 problems." in yosys_output
                    and b"Warning:" not in yosys_output, "unsupported Yosys diagnostics")
            model = smt.read_text()
            for signal in ("pinmux_hw_debug_en_q", *INPUTS):
                require(f"(define-fun |pinmux_strap_sampling_n {signal}|" in model,
                        "missing SMT signal: " + signal)
            require("(define-fun |pinmux_strap_sampling_i| ((state |pinmux_strap_sampling_s|)) Bool true)" in model,
                    "unexpected SMT initial-state predicate")
            model_data[variant] = model
        def solve(variant, name, pair, kind, fixed, expected, witness=False):
            path = out / f"{name}.query.smt2"
            path.write_text(query_text(model_data[variant], pair, kind, fixed, witness))
            output = capture([report["tools"]["z3"]["path"], str(path)],
                             out, out, name, timeout).decode()
            require(output.splitlines()[0] == expected
                    and (witness or output.strip() == expected),
                    name + " solver result differs")
            report["queries"][name] = expected
            return parse_values(output) if witness else None
        for i in range(1, 5):
            solve("good", f"good-bad-{i}", i, "bad", False, "unsat")
        solve("good", "reset-grounding", 1, "reset_bad", False, "unsat")
        solve("good", "early-rise-boundary", 1, "cover", True, "unsat")
        good_inputs, good_q = solve("good", "good-rise-cover", 4, "cover", True, "sat", True)
        control_inputs, control_q = solve("good", "good-fault-input-control", 3,
                                          "trace", True, "sat", True)
        fault_inputs, fault_q = solve("fault", "fault-bad-rise", 3, "bad", True, "sat", True)
        require(control_inputs == fault_inputs, "mutant and original control inputs differ")
        report["witnesses"] = {"good": {"inputs": good_inputs, "q": good_q},
                               "control": {"inputs": control_inputs, "q": control_q},
                               "fault": {"inputs": fault_inputs, "q": fault_q}}
        vvp = Path(icarus).with_name("vvp")
        require(vvp.is_file(), "matching vvp is unavailable")
        capture([str(vvp), "-V"], root, out, "vvp-version", timeout, allow_stderr=True)
        vvp_version = ((out / "vvp-version.stdout.raw").read_bytes()
                       + (out / "vvp-version.stderr.raw").read_bytes()).decode(errors="replace")
        require(vvp_version.startswith("Icarus Verilog runtime version"),
                "unexpected VVP version")
        report["tools"]["vvp"] = {"path": str(vvp), "sha256": sha256(vvp),
                                  "version": vvp_version.splitlines()[0]}
        outputs = {}
        for variant, inputs in (("good", good_inputs), ("control", control_inputs),
                                ("fault", fault_inputs)):
            replay = out / f"replay-{variant}.sv"
            replay.write_text(replay_source(inputs))
            variant_sources = [mutant if variant == "fault" and s == sampler_export else s
                               for s in sources]
            executable = out / f"replay-{variant}.vvp"
            argv = [icarus, "-g2012", "-gassertions", "-DFPV_ON", "-s", "replay",
                    "-o", str(executable)] + ["-I" + d for d in dirs]
            capture(argv + list(map(str, variant_sources)) + [str(replay)],
                    root, out, f"replay-{variant}-build", timeout)
            outputs[variant] = capture([str(vvp), str(executable)], out, out,
                                       f"replay-{variant}-run", timeout).decode()
        check_replay(outputs["good"], outputs["control"], outputs["fault"],
                     good_q, control_q, fault_q)
        report["result"] = "bounded_model_check_ok"
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as error:
        report["failure_reasons"].append(str(error))
    (out / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("opentitan")
    parser.add_argument("edam", help="generated pinned pinmux_chip_fpv .eda.yml")
    parser.add_argument("evidence")
    parser.add_argument("--slang", default="slang")
    parser.add_argument("--yosys", default="yosys")
    parser.add_argument("--z3", default="z3")
    parser.add_argument("--iverilog", default="iverilog")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    result = check(args.opentitan, args.edam, args.evidence, args.slang, args.yosys,
                   args.z3, args.iverilog, args.timeout)
    print(result["result"] + ": " + ", ".join(result["failure_reasons"]))
    return 0 if result["result"] == "bounded_model_check_ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

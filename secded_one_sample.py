#!/usr/bin/env python3
"""One two-state posedge sample of the pinned SECDED reverse-syndrome property."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from qd_formal import EXPECTED, PIN, SOURCES, git_output, preflight, registered_identities, sha256
from slang_inventory import EXPECTED_INSTANCE, EXPECTED_EXPR_SHA256, inventory, instances, run as slang_run, symbol

ASSUME = "MaxTwoErrors_M"
PROPERTY = "SyndromeCheckReverse_A"
RTL = (SOURCES[1], SOURCES[2], SOURCES[4])


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def expr(node):
    """Lower only the typed operators present in the two pinned expressions."""
    kind = node.get("kind")
    if kind == "NamedValue":
        name = symbol(node["symbol"])
        require((name, node.get("type")) in {("error_inject_i", "logic[21:0]"),
                                                    ("syndrome_o", "logic[5:0]")}, "unsupported named value")
        return name
    if kind == "IntegerLiteral":
        require(node.get("type") == "int" and node.get("value") in ("0", "2"), "unsupported literal")
        return node["value"]
    if kind == "Call":
        require(node.get("type") == "int" and node.get("subroutine") == "$countones"
                and len(node.get("arguments", [])) == 1, "unsupported call")
        return "$countones(" + expr(node["arguments"][0]) + ")"
    if kind == "UnaryOp":
        require(node.get("op") == "BitwiseOr" and node.get("type") == "logic", "unsupported unary op")
        return "(|" + expr(node["operand"]) + ")"
    if kind == "BinaryOp":
        op = {"LessThanEqual": "<=", "GreaterThan": ">"}.get(node.get("op"))
        require(op is not None and node.get("type") == "bit", "unsupported binary op")
        return "(" + expr(node["left"]) + " " + op + " " + expr(node["right"]) + ")"
    raise ValueError("unsupported expression kind: " + str(kind))


def selected_bodies(ast):
    records = {p["name"]: p for p in inventory(ast)}
    bodies = {}
    for instance, path in instances(ast["design"]):
        if path != EXPECTED_INSTANCE:
            continue
        members = instance["body"]["members"]
        for member in members:
            if member.get("kind") != "ProceduralBlock":
                continue
            assertion = member.get("body", {}).get("body", {})
            if assertion.get("kind") != "ConcurrentAssertion":
                continue
            for name in (ASSUME, PROPERTY):
                record = records[name]
                if (member.get("source_line") == record["source_line"]
                        and assertion.get("source_column_start") == record["source_column"]):
                    require(name not in bodies and assertion.get("assertionKind") == record["role"], "ambiguous property")
                    body = assertion["propertySpec"]["expr"]["expr"]
                    require(record["expression_sha256"] == EXPECTED_EXPR_SHA256[name], "expression mismatch")
                    bodies[name] = body
    require(set(bodies) == {ASSUME, PROPERTY}, "selected property missing")
    return records, bodies


def harness(ast):
    records, bodies = selected_bodies(ast)
    assumption = bodies[ASSUME]
    property_body = bodies[PROPERTY]
    require(assumption.get("kind") == "Simple" and property_body.get("kind") == "Binary"
            and property_body.get("op") == "OverlappedImplication"
            and property_body.get("left", {}).get("kind") == "Simple"
            and property_body.get("right", {}).get("kind") == "Simple", "unsupported temporal property")
    limit = expr(assumption["expr"])
    antecedent = expr(property_body["left"]["expr"])
    consequent = expr(property_body["right"]["expr"])
    require(limit == "($countones(error_inject_i) <= 2)"
            and antecedent == "($countones(error_inject_i) > 0)"
            and consequent == "(|syndrome_o)", "unexpected property equation")
    for name in (ASSUME, PROPERTY):
        require(records[name]["clock"] == {"edge": "PosEdge", "signal": "clk_i"}
                and records[name]["disable_iff"] == {"op": "CaseInequality", "left": {"op": "LogicalNot", "signal": "rst_ni"}, "right": "1'b0"}, "unsupported clock or disable")
    source = f'''module secded_sample (
  input logic clk_i, rst_ni,
  input logic [15:0] data_i,
  input logic [21:0] error_inject_i,
  output logic bad, live, zero_case, two_case, three_case, unrestricted_three
);
  logic [15:0] data_o;
  logic [21:0] encoded_o;
  logic [5:0] syndrome_o;
  logic [1:0] err_o;
  prim_secded_22_16_tb dut (.*);
  assign bad = rst_ni && {limit} && {antecedent} && !{consequent};
  assign live = rst_ni && {limit} && {antecedent};
  assign zero_case = rst_ni && {limit} && (error_inject_i == 0);
  assign two_case = rst_ni && {limit} && ($countones(error_inject_i) == 2);
  assign three_case = rst_ni && {limit} && ($countones(error_inject_i) == 3);
  assign unrestricted_three = rst_ni && ($countones(error_inject_i) == 3);
endmodule
'''
    return source, {"assumption": limit, "antecedent": antecedent, "consequent": consequent,
                    "property": records[PROPERTY], "assumption_property": records[ASSUME],
                    "bound_samples": 1, "semantics": "two-state combinational values at one posedge; reset high"}


def capture(argv, cwd, out, name, timeout, allow_stderr=False):
    (out / f"{name}.argv.json").write_text(json.dumps(argv) + "\n")
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout)
        stdout, stderr, status = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, status = error.stdout or b"", error.stderr or b"", None
    (out / f"{name}.stdout.raw").write_bytes(stdout)
    (out / f"{name}.stderr.raw").write_bytes(stderr)
    (out / f"{name}.exit.json").write_text(json.dumps({"status": status}) + "\n")
    require(status == 0, f"{name} failed or timed out")
    require(allow_stderr or not stderr, f"{name} emitted diagnostics")
    return stdout


def query(model, out, z3, name, output, expected, timeout, witness=False):
    require(re.search(r"\(define-fun \|secded_sample_n " + output + r"\| .* Bool", model), "missing SMT output: " + output)
    suffix = ("\n(declare-fun sample () |secded_sample_s|)\n"
              "(assert (|secded_sample_h| sample))\n"
              "(assert (|secded_sample_n rst_ni| sample))\n"
              f"(assert (|secded_sample_n {output}| sample))\n(check-sat)\n")
    if witness:
        suffix += "(get-value ((|secded_sample_n data_i| sample) (|secded_sample_n error_inject_i| sample)))\n"
    path = out / f"{name}.query.smt2"
    path.write_text(model + suffix)
    stdout = capture([str(z3), str(path)], out, out, name, timeout).decode(errors="replace")
    require(stdout.splitlines()[0] == expected and (witness or stdout.strip() == expected),
            f"{name} solver output is not {expected}")
    if not witness:
        return expected
    match = re.fullmatch(
        r"sat\s*\(\(\(\|secded_sample_n data_i\| sample\) (#[bx][0-9a-fA-F]+)\)\s*"
        r"\(\(\|secded_sample_n error_inject_i\| sample\) (#[bx][0-9a-fA-F]+)\)\)\s*",
        stdout)
    require(match is not None, "unsupported solver witness output")
    values = {name: int(value[2:], 2 if value[1] == "b" else 16)
              for name, value in zip(("data_i", "error_inject_i"), match.groups())}
    require(values["data_i"] < 2**16 and values["error_inject_i"] < 2**22,
            "solver witness width is invalid")
    return values


def faulty_decoder(root, out):
    original = (root / SOURCES[2]).read_text()
    altered = original.replace("22'h01496E", "22'h01496C").replace("22'h10ACA5", "22'h10ACA7")
    require(altered != original and original.count("22'h01496E") == 1
            and original.count("22'h10ACA5") == 1, "decoder mutation target differs")
    path = out / "faulty_dec.sv"
    path.write_text(altered)
    return path


def replay_witness(root, out, iverilog, witness, timeout):
    require(witness["error_inject_i"].bit_count() in (1, 2), "fault witness violates assumption")
    source = ("module replay;\n"
              "  reg clk_i = 0, rst_ni = 0;\n"
              f"  reg [15:0] data_i = 16'h{witness['data_i']:04x};\n"
              "  reg [21:0] error_inject_i = 0;\n"
              "  wire [15:0] data_o;\n  wire [21:0] encoded_o;\n"
              "  wire [5:0] syndrome_o;\n  wire [1:0] err_o;\n"
              "  prim_secded_22_16_tb dut (.*);\n"
              f"  initial begin\n    #2; rst_ni = 1; error_inject_i = 22'h{witness['error_inject_i']:06x};\n"
              "    #3; clk_i = 1;\n    #1; $display(\"SAMPLE syndrome=%h\", syndrome_o);\n"
              "    $finish;\n  end\nendmodule\n")
    (out / "replay.sv").write_text(source)
    executable = Path(shutil.which(str(iverilog)) or iverilog).resolve()
    vvp = executable.with_name("vvp")
    require(vvp.is_file(), "matching vvp is unavailable")
    capture([str(vvp), "-V"], root, out, "vvp-version", timeout, allow_stderr=True)
    version = ((out / "vvp-version.stdout.raw").read_bytes()
               + (out / "vvp-version.stderr.raw").read_bytes()).decode().splitlines()
    require(version and version[0].startswith("Icarus Verilog runtime version"), "unexpected vvp version")
    vvp_info = {"path": str(vvp), "sha256": sha256(vvp), "version": version[0]}
    args = [str(executable), "-g2012", "-gassertions", "-DFPV_ON",
            "-I", str(root / "hw/ip/prim/rtl"), "-s", "replay",
            "-s", "prim_secded_22_16_bind_fpv"]
    outputs = {}
    for variant, decoder in (("good", root / SOURCES[2]), ("fault", out / "faulty_dec.sv")):
        artifact = out / f"replay-{variant}.vvp"
        sources = [root / s for s in SOURCES]
        sources[2] = decoder
        sources.append(out / "replay.sv")
        if variant == "good":
            stub = out / "replay.stub"
            capture(args + ["-t", "stub", "-o", str(stub)] + list(map(str, sources)),
                    root, out, "replay-stub", timeout)
            require(sorted(registered_identities(stub.read_text())) == sorted(EXPECTED),
                    "bound replay checker roster differs")
        capture(args + ["-o", str(artifact)] + list(map(str, sources)),
                root, out, f"replay-{variant}-build", timeout)
        outputs[variant] = capture([str(vvp), str(artifact)], root, out,
                                   f"replay-{variant}-run", timeout).decode().strip()
    good = re.search(r"SAMPLE syndrome=([0-9a-fA-F]+)", outputs["good"])
    bad = re.search(r"SAMPLE syndrome=([0-9a-fA-F]+)", outputs["fault"])
    require(good and bad and int(good.group(1), 16) != 0 and int(bad.group(1), 16) == 0
            and "[ASSERT FAILED]" not in outputs["good"]
            and "ERROR:" not in outputs["good"]
            and "WARNING:" not in outputs["good"]
            and "WARNING:" not in outputs["fault"]
            and "[ASSERT FAILED] SyndromeCheckReverse_A" in outputs["fault"],
            "bound Icarus witness replay disagrees with SMT or checker")
    return {"good_syndrome": good.group(1), "fault_syndrome": bad.group(1),
            "fault_named_assertion": "SyndromeCheckReverse_A", "registered_checkers": list(EXPECTED),
            "vvp": vvp_info}


def check(root, out, slang, yosys, z3, timeout=120, fault=False, iverilog="iverilog"):
    root, out = Path(root).resolve(), Path(out).resolve()
    require(root not in out.parents and out not in root.parents and root != out,
            "evidence must be outside source checkout")
    require(not out.exists() or not any(out.iterdir()), "evidence directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "result": "UNKNOWN", "claim": "one_sample_two_state_only",
              "property": PROPERTY, "assumption": ASSUME, "opentitan_pin": PIN,
              "fault_injection": fault, "failure_reasons": [], "queries": {}, "tool": {}, "files_sha256": {}}
    try:
        require(git_output(root, ["rev-parse", "HEAD"]) == PIN
                and not git_output(root, ["status", "--porcelain", "--untracked-files=all"]), "source checkout is not clean at pin")
        icarus = preflight(root, out / "icarus", iverilog, timeout)
        require(icarus["result"] == "frontend_inventory_ok", "Icarus inventory is UNKNOWN")
        frontend = slang_run(root, out / "frontend", slang, timeout)
        require(frontend["result"] == "semantic_frontend_inventory_ok", "slang inventory is UNKNOWN")
        require(frontend["source_sha256"] == icarus["source_sha256"], "frontend source hashes differ")
        require(frontend["tool"].get("version", "").startswith("slang version 11.0.448+"),
                "unsupported slang version")
        ast = json.loads((out / "frontend/ast.raw.json").read_text())
        source, mapping = harness(ast)
        (out / "harness.sv").write_text(source)
        (out / "mapping.json").write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n")
        for tool_name, executable, flag in (("yosys", yosys, "-V"), ("z3", z3, "-version")):
            path = Path(shutil.which(str(executable)) or executable).resolve()
            report["tool"][tool_name] = {"path": str(path), "sha256": sha256(path),
                                          "version": capture([str(path), flag], root, out, tool_name + "-version", timeout).decode().strip()}
        rtl = [root / s for s in RTL]
        if fault:
            rtl[1] = faulty_decoder(root, out)
        script = "read_slang --top secded_sample " + " ".join(map(str, rtl)) + f" {out / 'harness.sv'}\nprep -top secded_sample -flatten\ncheck -assert\nwrite_smt2 -wires {out / 'model.smt2'}\n"
        (out / "model.ys").write_text(script)
        yosys_output = capture([report["tool"]["yosys"]["path"], "-Q", "-s", str(out / "model.ys")], root, out, "yosys", timeout)
        require(b"Build succeeded: 0 errors, 0 warnings" in yosys_output
                and b"Found and reported 0 problems." in yosys_output
                and b"Warning:" not in yosys_output and b"ERROR:" not in yosys_output,
                "Yosys diagnostics or structural check are unsupported")
        model = (out / "model.smt2").read_text()
        require("(define-fun |secded_sample_a| ((state |secded_sample_s|)) Bool true)" in model,
                "unexpected SMT assumption export")
        for name, signal, expected in (("bad", "bad", "sat" if fault else "unsat"),
                                       ("live", "live", "sat"), ("zero", "zero_case", "sat"),
                                       ("two", "two_case", "sat"), ("three", "three_case", "unsat"),
                                       ("three_without_assumption", "unrestricted_three", "sat")):
            answer = query(model, out, report["tool"]["z3"]["path"], name, signal, expected, timeout,
                           witness=fault and name == "bad")
            report["queries"][name] = expected
            if fault and name == "bad":
                report["witness"] = answer
        if fault:
            report["witness_replay"] = replay_witness(root, out, icarus["tool"]["path"],
                                                       report["witness"], timeout)
        report["result"] = "fault_detected" if fault else "one_sample_check_ok"
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, IndexError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        report["failure_reasons"].append(str(error))
    for path in out.rglob("*"):
        if path.is_file() and path.name != "result.json":
            report["files_sha256"][str(path.relative_to(out))] = sha256(path)
    (out / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("opentitan_root", type=Path)
    p.add_argument("evidence_dir", type=Path)
    p.add_argument("--slang", default="slang")
    p.add_argument("--iverilog", default="iverilog")
    p.add_argument("--yosys", default="yosys")
    p.add_argument("--z3", default="z3")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--scratch-fault", action="store_true",
                   help="mutate a decoder copy in the evidence directory and replay the solver witness")
    a = p.parse_args()
    result = check(a.opentitan_root, a.evidence_dir, a.slang, a.yosys, a.z3, a.timeout,
                   fault=a.scratch_fault, iverilog=a.iverilog)
    print(json.dumps({"result": result["result"], "evidence": str(a.evidence_dir.resolve())}))
    return 0 if result["result"] == ("fault_detected" if a.scratch_fault else "one_sample_check_ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

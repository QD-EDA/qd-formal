#!/usr/bin/env python3
"""Slang semantic frontend inventory for the pinned OpenTitan SECDED closure."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from qd_formal import EXPECTED, INCLUDES, PIN, SOURCES, TOPS, git_output, sha256

EXPECTED_INSTANCE = "prim_secded_22_16_tb.prim_secded_22_16_assert_fpv"
VIP_SOURCE = SOURCES[3]
EXPECTED_ROLES = {name: "Assume" if name == "MaxTwoErrors_M" else "Assert"
                  for name in EXPECTED}
# Canonical expression hashes from the clean pinned closure with slang 11.0.448.
EXPECTED_EXPR_SHA256 = dict(zip(EXPECTED, (
    "b197376e77cfc4b2fc6ec1f22662df322be52aedb81c42186f75f084449618bc",
    "d003a99346a97bd0d92b25fd27bf88a214008cc6ef487f66c9d90f167d00d2ba",
    "3708ae94deb6c0ed97b58e31682285d988079d928c115705f9a0565d040337d9",
    "da140985be99607fff1c1a069a7282c843344ebece5d11671f3eb309efbf9dd0",
    "c3a34d34a4e5b3a85663d1523b6cb1605a83f10b81c6dcc695b253b7dfedbc08",
    "20e78f977389227f420186b1cb08fca07318d6d956537c9bcccf0aab1c9ecf7d",
    "493d7f8ff79b371b51df1a498dc8088c2ed67b032e24925eeeb0e9cdcb896ed1",
    "20c48bc7a279b1e3a3687e84b39a12113f5ed6760d989175741f3e787d8c5dda",
)))
SUCCESS_STDOUT = ("Top level design units:\n"
                  "    prim_secded_22_16_bind_fpv\n"
                  "    prim_secded_22_16_tb\n\n\n"
                  "Build succeeded: 0 errors, 0 warnings\n").encode()


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def symbol(value):
    match = re.fullmatch(r"[0-9]+ ([A-Za-z_][A-Za-z_0-9]*)", value)
    if not match:
        raise ValueError("unrecognized slang symbol reference")
    return match.group(1)


def expression_sha256(node):
    if not isinstance(node, dict) or node.get("kind") not in ("Simple", "Binary"):
        raise ValueError("missing or unsupported property expression")

    def stable(value):
        if isinstance(value, list):
            return [stable(item) for item in value]
        if isinstance(value, dict):
            return {key: symbol(child) if key == "symbol" else stable(child)
                    for key, child in value.items()
                    if key != "addr" and not key.startswith("source_")}
        return value

    return hashlib.sha256(json.dumps(stable(node), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def instances(node, path=()):
    if not isinstance(node, dict):
        return
    if node.get("kind") == "Instance":
        path += (node.get("name"),)
        yield node, ".".join(path)
    for member in node.get("members", []):
        yield from instances(member, path)
    yield from instances(node.get("body"), path)


def inventory(ast, expected_expr_sha256=EXPECTED_EXPR_SHA256):
    """Resolve labels only through exact in-snapshot block references."""
    found = []
    for instance, instance_path in instances(ast.get("design")):
        members = instance.get("body", {}).get("members", [])
        if not isinstance(members, list):
            raise ValueError("instance body has no member list")
        labels = {}
        for member in members:
            if member.get("kind") == "StatementBlock" and member.get("name"):
                labels.setdefault(member.get("addr"), []).append(member)
        for member in members:
            if member.get("kind") != "ProceduralBlock":
                continue
            assertions = [node for node in nodes(member.get("body"))
                          if node.get("kind") == "ConcurrentAssertion"]
            if not assertions:
                continue
            if len(assertions) != 1 or member.get("procedureKind") != "Always":
                raise ValueError("unsupported assertion procedure")
            block = member.get("body", {})
            ref = re.fullmatch(r"([0-9]+) ([A-Za-z_][A-Za-z_0-9]*)", block.get("block", ""))
            candidates = labels.get(int(ref.group(1)), []) if ref else []
            if (block.get("kind") != "Block" or len(candidates) != 1
                    or candidates[0].get("name") != ref.group(2)):
                raise ValueError("assertion label cannot be resolved uniquely")
            label = candidates[0]
            assertion = assertions[0]
            if instance_path != EXPECTED_INSTANCE:
                raise ValueError("assertion is outside pinned bound instance")
            source = assertion.get("source_file_start")
            line = assertion.get("source_line_start")
            column = assertion.get("source_column_start")
            if (source != VIP_SOURCE or not isinstance(line, int) or line < 1
                    or not isinstance(column, int) or column < 1
                    or assertion.get("source_file_end") != source
                    or assertion.get("source_line_end") != line
                    or label.get("source_file") != source or label.get("source_line") != line
                    or member.get("source_file") != source or member.get("source_line") != line):
                raise ValueError("assertion and named block locations disagree")
            spec = assertion.get("propertySpec", {})
            event = spec.get("clocking", {})
            disabled = spec.get("expr", {})
            condition = disabled.get("condition", {})
            if (spec.get("kind") != "Clocking" or event.get("kind") != "SignalEvent"
                    or event.get("edge") != "PosEdge" or event.get("expr", {}).get("kind") != "NamedValue"
                    or disabled.get("kind") != "DisableIff" or condition.get("kind") != "BinaryOp"
                    or condition.get("op") != "CaseInequality"):
                raise ValueError("unsupported clock or disable expression")
            left, right = condition.get("left", {}), condition.get("right", {})
            if (left.get("kind") != "UnaryOp" or left.get("op") != "LogicalNot"
                    or left.get("operand", {}).get("kind") != "NamedValue"
                    or right.get("kind") != "UnbasedUnsizedIntegerLiteral"):
                raise ValueError("unsupported disable expression")
            clock = symbol(event["expr"]["symbol"])
            reset = symbol(left["operand"]["symbol"])
            if (clock, reset, right.get("value")) != ("clk_i", "rst_ni", "1'b0"):
                raise ValueError("clock or disable expression differs from pinned closure")
            body_hash = expression_sha256(disabled.get("expr"))
            if body_hash != expected_expr_sha256.get(label["name"]):
                raise ValueError("property expression differs from pinned closure")
            found.append({"name": label["name"], "role": assertion.get("assertionKind"),
                          "instance": instance_path, "source_file": source,
                          "source_line": line, "source_column": column,
                          "expression_sha256": body_hash,
                          "clock": {"edge": "PosEdge", "signal": clock},
                          "disable_iff": {"op": "CaseInequality", "left": {"op": "LogicalNot", "signal": reset},
                                          "right": right["value"]}})
    actual = [node for node in nodes(ast.get("design")) if node.get("kind") == "ConcurrentAssertion"]
    definitions = [node for node in nodes(ast.get("definitions")) if node.get("kind") == "ConcurrentAssertion"]
    if len(found) != len(actual) or definitions:
        raise ValueError("unmapped or definition-only assertions")
    if Counter((item["name"], item["role"]) for item in found) != Counter(EXPECTED_ROLES.items()):
        raise ValueError("slang property identity or role roster differs from Icarus inventory")
    if len({(item["instance"], item["source_file"], item["source_line"]) for item in found}) != len(found):
        raise ValueError("duplicate assertion source location")
    return sorted(found, key=lambda item: EXPECTED.index(item["name"]))


def captured(argv, root, timeout, stdout_path, stderr_path):
    try:
        process = subprocess.run(argv, cwd=root, capture_output=True, timeout=timeout)
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        raise
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    return process


def run(root, out, compiler, timeout):
    root, out = Path(root).resolve(), Path(out).resolve()
    if out == root or root in out.parents:
        raise ValueError("evidence output must be outside the OpenTitan checkout")
    located = shutil.which(str(compiler))
    compiler = Path(located).resolve() if located else Path(compiler).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for name in ("result.json", "ast.raw.json", "stdout.raw", "stderr.raw",
                 "tool-version.stdout.raw", "tool-version.stderr.raw"):
        (out / name).unlink(missing_ok=True)
    argv = [str(compiler), "--single-unit", "-DFPV_ON", "-I", "hw/ip/prim/rtl"]
    for top in TOPS:
        argv.extend(("--top", top))
    argv.extend(("--ast-json", str(out / "ast.raw.json"), "--ast-json-source-info"))
    argv.extend(SOURCES)
    report = {"schema_version": 1, "result": "UNKNOWN", "claim": "semantic_frontend_inventory_only",
              "proof": False, "opentitan_pin": PIN, "expected_checker_identities": list(EXPECTED),
              "properties": [], "argv": argv, "version_argv": [str(compiler), "--version"],
              "exit_status": None, "source_sha256": {},
              "tool": {"path": str(compiler), "sha256": None,
                       "version_stdout": "tool-version.stdout.raw",
                       "version_stderr": "tool-version.stderr.raw"},
              "ast": {"file": "ast.raw.json", "sha256": None},
              "diagnostics": {"stdout": "stdout.raw", "stderr": "stderr.raw"}, "failure_reasons": []}
    for name in ("stdout.raw", "stderr.raw", "tool-version.stdout.raw", "tool-version.stderr.raw"):
        (out / name).write_bytes(b"")
    try:
        report["opentitan_revision"] = git_output(root, ["rev-parse", "HEAD"])
        report["opentitan_dirty_status"] = git_output(root, ["status", "--porcelain", "--untracked-files=all"])
        if report["opentitan_revision"] != PIN or report["opentitan_dirty_status"]:
            raise ValueError("OpenTitan checkout is not clean at the pinned revision")
        for source in (*SOURCES, *INCLUDES):
            report["source_sha256"][source] = sha256(root / source)
        report["tool"]["sha256"] = sha256(compiler)
        version = captured(report["version_argv"], root, timeout,
                           out / "tool-version.stdout.raw", out / "tool-version.stderr.raw")
        if version.returncode or not version.stdout or version.stderr:
            raise ValueError("slang version query failed or emitted diagnostics")
        report["tool"]["version"] = version.stdout.decode(errors="replace").strip()
        process = captured(argv, root, timeout, out / "stdout.raw", out / "stderr.raw")
        report["exit_status"] = process.returncode
        if process.returncode or process.stderr or process.stdout != SUCCESS_STDOUT:
            raise ValueError("slang returned nonzero or emitted diagnostics")
        ast_path = out / "ast.raw.json"
        report["ast"]["sha256"] = sha256(ast_path)
        report["properties"] = inventory(json.loads(ast_path.read_text()))
        report["result"] = "semantic_frontend_inventory_ok"
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        report["failure_reasons"].append(str(error))
    (out / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("opentitan_root", type=Path)
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("--slang", default="slang")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        report = run(args.opentitan_root, args.evidence_dir, args.slang, args.timeout)
    except ValueError as error:
        print(json.dumps({"result": "UNKNOWN", "reason": str(error)}))
        return 2
    print(json.dumps({"result": report["result"], "evidence": str(args.evidence_dir.resolve())}))
    return 0 if report["result"] == "semantic_frontend_inventory_ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed Icarus frontend inventory for the pinned OpenTitan SECDED FPV."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PIN = "7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19"
IVERILOG_TOOLCHAIN_SOURCE_PIN = "6fd804a39e803152bd39a3ee4c96b15d30532001"
TOPS = ("prim_secded_22_16_tb", "prim_secded_22_16_bind_fpv")
SOURCES = (
    "hw/ip/prim/rtl/prim_assert.sv",
    "hw/ip/prim/rtl/prim_secded_22_16_enc.sv",
    "hw/ip/prim/rtl/prim_secded_22_16_dec.sv",
    "hw/ip/prim/fpv/vip/prim_secded_22_16_assert_fpv.sv",
    "hw/ip/prim/fpv/tb/prim_secded_22_16_tb.sv",
    "hw/ip/prim/fpv/tb/prim_secded_22_16_bind_fpv.sv",
)
INCLUDES = (
    "hw/ip/prim/rtl/prim_assert_standard_macros.svh",
    "hw/ip/prim/rtl/prim_assert_sec_cm.svh",
    "hw/ip/prim/rtl/prim_flop_macros.sv",
)
EXPECTED = (
    "MaxTwoErrors_M",
    "SingleErrorDetect_A",
    "SingleErrorDetectReverse_A",
    "DoubleErrorDetect_A",
    "DoubleErrorDetectReverse_A",
    "SingleErrorCorrect_A",
    "SyndromeCheck_A",
    "SyndromeCheckReverse_A",
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def registered_identities(stub_text):
    """Read names attached to Icarus' registered assertion calls in -t stub."""
    lines = stub_text.splitlines()
    names = []
    for index, line in enumerate(lines):
        if "Call $ivl_register_assertion(" not in line:
            continue
        for following in lines[index + 1:index + 5]:
            if '<string="' in following:
                names.append(following.split('<string="', 1)[1].split('"', 1)[0])
                break
    return names


def git_output(root, args):
    return subprocess.run(["git", *args], cwd=root, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout.strip()


def preflight(root, out, compiler, timeout):
    root, out = Path(root).resolve(), Path(out).resolve()
    if out == root or root in out.parents:
        raise ValueError("evidence output must be outside the OpenTitan checkout")
    located = shutil.which(str(compiler))
    compiler = Path(located).resolve() if located else Path(compiler).resolve()
    out.mkdir(parents=True, exist_ok=True)
    stub = out / "opentitan-secded.stub"
    stub.unlink(missing_ok=True)
    result_path = out / "result.json"
    result_path.unlink(missing_ok=True)
    argv = [str(compiler), "-g2012", "-gassertions", "-DFPV_ON",
            "-I" + str(root / "hw/ip/prim/rtl"), "-t", "stub"]
    for top in TOPS:
        argv.extend(("-s", top))
    argv.extend(("-o", str(stub)))
    argv.extend(str(root / source) for source in SOURCES)

    report = {
        "schema_version": 1,
        "result": "UNKNOWN",
        "claim": "frontend_inventory_only",
        "proof": False,
        "opentitan_pin": PIN,
        "intended_iverilog_toolchain_source_revision_unverified": IVERILOG_TOOLCHAIN_SOURCE_PIN,
        "expected_checker_identities": list(EXPECTED),
        "checker_identities": [],
        "diagnostics": {"stdout": "stdout.raw", "stderr": "stderr.raw"},
        "argv": argv,
        "version_argv": [str(compiler), "-V"],
        "exit_status": None,
        "source_sha256": {},
        "tool": {"path": str(compiler), "sha256": None},
        "failure_reasons": [],
    }
    stdout_path, stderr_path = out / "stdout.raw", out / "stderr.raw"
    stdout_path.write_bytes(b"")
    stderr_path.write_bytes(b"")
    (out / "tool-version.stdout.raw").write_bytes(b"")
    (out / "tool-version.stderr.raw").write_bytes(b"")
    try:
        revision = git_output(root, ["rev-parse", "HEAD"])
        dirty = git_output(root, ["status", "--porcelain", "--untracked-files=all"])
        report["opentitan_revision"] = revision
        report["opentitan_dirty_status"] = dirty
        if revision != PIN or dirty:
            report["failure_reasons"].append("OpenTitan checkout is not clean at the pinned revision")
        for source in (*SOURCES, *INCLUDES):
            path = root / source
            report["source_sha256"][source] = sha256(path)
        report["tool"]["sha256"] = sha256(compiler)
        if not report["failure_reasons"]:
            try:
                version = subprocess.run([str(compiler), "-V"], cwd=root,
                                         capture_output=True, timeout=timeout)
                (out / "tool-version.stdout.raw").write_bytes(version.stdout)
                (out / "tool-version.stderr.raw").write_bytes(version.stderr)
                report["tool"]["version_exit_status"] = version.returncode
                report["tool"]["version_stdout"] = version.stdout.decode(errors="replace")
                report["tool"]["version_stderr"] = version.stderr.decode(errors="replace")
            except subprocess.TimeoutExpired as error:
                (out / "tool-version.stdout.raw").write_bytes(error.stdout or b"")
                (out / "tool-version.stderr.raw").write_bytes(error.stderr or b"")
                report["failure_reasons"].append("Icarus version query timed out")
            else:
                if version.returncode != 0 or not version.stdout or version.stderr:
                    report["failure_reasons"].append("Icarus version query failed, emitted diagnostics, or returned no version")
            if not report["failure_reasons"]:
                try:
                    result = subprocess.run(argv, cwd=root, capture_output=True, timeout=timeout)
                    stdout_path.write_bytes(result.stdout)
                    stderr_path.write_bytes(result.stderr)
                    report["exit_status"] = result.returncode
                    if result.stdout or result.stderr:
                        report["failure_reasons"].append("compiler emitted diagnostics; fail-closed policy")
                    if result.returncode != 0:
                        report["failure_reasons"].append("Icarus frontend returned nonzero status")
                    if not stub.is_file():
                        report["failure_reasons"].append("Icarus did not produce the stub artifact")
                    else:
                        text = stub.read_text(errors="replace")
                        report["stub_sha256"] = sha256(stub)
                        identities = registered_identities(text)
                        report["checker_identities"] = identities
                        if Counter(identities) != Counter(EXPECTED):
                            report["failure_reasons"].append("registered checker identity inventory differs from the pinned roster")
                except subprocess.TimeoutExpired as error:
                    stdout_path.write_bytes(error.stdout or b"")
                    stderr_path.write_bytes(error.stderr or b"")
                    report["failure_reasons"].append("Icarus frontend timed out")
        if not report["failure_reasons"]:
            report["result"] = "frontend_inventory_ok"
    except (OSError, subprocess.SubprocessError) as error:
        report["failure_reasons"].append(f"preflight could not complete: {error}")
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("preflight", help="inventory registered OpenTitan SECDED checkers")
    run.add_argument("opentitan_root", type=Path)
    run.add_argument("evidence_dir", type=Path)
    run.add_argument("--iverilog", default="iverilog", help="Icarus 13 executable")
    run.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        report = preflight(args.opentitan_root, args.evidence_dir, args.iverilog, args.timeout)
    except ValueError as error:
        print(json.dumps({"result": "UNKNOWN", "reason": str(error)}))
        return 2
    print(json.dumps({"result": report["result"], "evidence": str(args.evidence_dir.resolve())}))
    return 0 if report["result"] == "frontend_inventory_ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

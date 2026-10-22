# Pinned one-sample SECDED check, 2026-09-23

Run on a local Apple Silicon macOS host against clean OpenTitan
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19` (dirty status empty).
These are the exact successful commands from this run; both output directories
were new. The evidence remains under `/tmp` and is not part of this PR.

```sh
python3 secded_one_sample.py /Users/danielellerbrock/projects/iverilog_uvm/opentitan-upstream /tmp/qd-secded-pr-proof-release --iverilog /tmp/iverilog-sva-macro-install/bin/iverilog --slang /Users/danielellerbrock/oss-cad-suite/bin/slang --yosys /Users/danielellerbrock/oss-cad-suite/bin/yosys --z3 /opt/homebrew/bin/z3
python3 secded_one_sample.py /Users/danielellerbrock/projects/iverilog_uvm/opentitan-upstream /tmp/qd-secded-pr-fault-release --iverilog /tmp/iverilog-sva-macro-install/bin/iverilog --slang /Users/danielellerbrock/oss-cad-suite/bin/slang --yosys /Users/danielellerbrock/oss-cad-suite/bin/yosys --z3 /opt/homebrew/bin/z3 --scratch-fault
```

The first result is `one_sample_check_ok`: direct Z3 query of `bad` is
`unsat`; `live`, `zero`, and `two` are `sat`. A three-error sample with
`MaxTwoErrors_M` is `unsat`, while the same sample without that constraint is
`sat`. The second result is `fault_detected`: the scratch-only decoder mutation
makes `bad` `sat` with `data_i=0x09f4`, `error_inject_i=0x000003`.
Icarus replay of those exact values registers all eight original bound
checkers, gives syndrome `0x11` and no assertion failure on the good decoder,
and gives syndrome `0x00` plus the original named
`[ASSERT FAILED] SyndromeCheckReverse_A` on the mutated copy. The mutation
changes decoder syndrome masks `01496E→01496C` and `10ACA5→10ACA7`; the
pinned checkout is unchanged. `vvp` exits zero even when `$error` reports a
failure, so the runner checks the raw output text.

The AST gate fingerprints are `b197376e77cfc4b2fc6ec1f22662df322be52aedb81c42186f75f084449618bc`
for `MaxTwoErrors_M` and `20c48bc7a279b1e3a3687e84b39a12113f5ed6760d989175741f3e787d8c5dda`
for `SyndromeCheckReverse_A`. Both resolve in
`prim_secded_22_16_tb.prim_secded_22_16_assert_fpv` at the positive edge of
`clk_i`, disabled by `(!rst_ni) !== 1'b0`. The original VIP source SHA-256 is
`ea23ad27bda9c8783b43d72c9ac497715f6918c121752cb464d19d7b4b52ebf5`;
encoder, decoder, and testbench hashes are respectively
`dc9be87f59567a2a6828de6e38de9f283ac7f48c088c852665e2767cea61fd35`,
`1db557bc993dab53bcdeeb31a3051b4468f61a489c88387d0e9072c7cacd860b`,
and `6d5d1dc11b1c561a0199a0ef02ee1046119604ae4c2adba362d5181e3248f0df`.
All nine source hashes and raw commands/streams are in each evidence directory.

| Tool | Reported version | Executable SHA-256 |
| --- | --- | --- |
| Icarus | 13.0 devel | `399d5fe468d296c0c419e3d9bda526ac711f5b0143360eccb16d642cbd5ea0f2` |
| vvp | 13.0 devel | `ef219946f8fa21e40f8bb092638ec236c35243ddcdd866f0dde1a5e744c97fe3` |
| slang | 11.0.448+e222e7dc0 | `c38c0fc380ac4c7c48434daa9245d18ad2638b23cd47e14aa82a4a4e7a783ab4` |
| Yosys | 0.68+80, `621d943ac-dirty` | `8a6175ee88d6412c3d792c47d0750b8707a8e12cc2222c1322546d47cd85edb9` |
| Z3 | 5.1.0 | `8b61a8bc0b7a4e14dfb119910502ef808b055df636b25c8b67b96ae630fbc29c` |

The real proof command took 5.17 seconds wall time; the fault command took
0.52 seconds. Peak memory was not measured, and no ≤2 GiB claim is made.
After tightening replay diagnostics, fresh runs at
`/tmp/qd-secded-pr-proof-review` and `/tmp/qd-secded-pr-fault-review` returned
the same query results and named fault replay (5.26 and 0.53 seconds wall time).
The result covers one two-state combinational posedge sample under the pinned
assumption. It does not establish unbounded safety, four-state SVA semantics,
reset sequencing, or any other assertion. `yosys-smtbmc PASSED` is excluded:
its exported assertion for this harness was constant true, so that result was
vacuous. CI unit tests exercise the runner's fail-closed paths; they do not
reproduce this real pinned toolchain run.

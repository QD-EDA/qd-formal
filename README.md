# QD Formal

QD Formal combines a fail-closed Icarus frontend inventory, a separate typed
slang property inventory, and one bounded SECDED check on the unchanged
OpenTitan `prim_secded_22_16_fpv` closure. The Icarus inventory is a compiler
gate, **not a formal proof**: it checks that Icarus exits cleanly without
diagnostics and registers the exact eight pinned checker names.

```sh
python3 -m pip install -r requirements.txt
python3 qd_formal.py preflight /path/to/clean/opentitan /tmp/qd-formal-secded \
  --iverilog /path/to/current-iverilog/bin/iverilog
python3 -m unittest discover -s tests -v
```

For a separate semantic frontend inventory, run slang 11.0.448 on the same
clean checkout:

```sh
python3 slang_inventory.py /path/to/clean/opentitan /tmp/qd-formal-slang \
  --slang /path/to/slang
```

This records the raw elaborated AST, diagnostics, command, and hashes. Its
`semantic_frontend_inventory_ok` result requires the exact eight names, one
assumption and seven assertions, the bound instance, source locations, clock,
disable condition, and pinned expression fingerprints. It is a frontend
inventory only: it does not run a solver or prove any property. An unsupported
AST shape or mismatch yields `UNKNOWN`.

The first bounded checker uses both inventories on the same clean pin, lowers
`MaxTwoErrors_M` and `SyndromeCheckReverse_A` from the typed AST, and asks Z3
about one two-state posedge sample of the unchanged encoder, decoder, and testbench:

```sh
python3 secded_one_sample.py /path/to/clean/opentitan /tmp/qd-secded-proof \
  --iverilog /path/to/current-iverilog/bin/iverilog --slang /path/to/slang \
  --yosys /path/to/yosys --z3 /path/to/z3
python3 secded_one_sample.py /path/to/clean/opentitan /tmp/qd-secded-fault \
  --iverilog /path/to/current-iverilog/bin/iverilog --slang /path/to/slang \
  --yosys /path/to/yosys --z3 /path/to/z3 --scratch-fault
```

Use fresh evidence directories. The second command mutates only a decoder copy
inside its evidence directory, obtains a solver witness, and replays that exact
sample with Icarus and the original bound checker. `one_sample_check_ok` is a
bounded two-state result, not an unbounded proof or a four-state SVA proof.
See [ONE_SAMPLE_EVIDENCE.md](ONE_SAMPLE_EVIDENCE.md) for the actual pinned run.

The checkout must be clean at OpenTitan commit
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. The runner writes `result.json`,
the exact stub, raw stdout/stderr, and source/tool hashes to the evidence
directory. A successful result is named `frontend_inventory_ok`; every
diagnostic, nonzero exit, wrong pin, dirty checkout, timeout, or checker roster
mismatch yields `UNKNOWN` and a nonzero CLI exit. A roster match checks names
and multiplicity only; the Icarus stub does not establish assert/assume/cover
roles or property semantics.

The source hashes include all six compiler translation units and the three
active include files (`prim_assert_standard_macros.svh`,
`prim_assert_sec_cm.svh`, and `prim_flop_macros.sv`). Only the six translation
units appear as source arguments; the macros are reached through the pinned
include path.

The evidence records the `iverilog -V` output and executable hash. It also names
Icarus source commit `6fd804a39e803152bd39a3ee4c96b15d30532001` as the intended
toolchain pin; that source revision is not inferred from or authenticated by the
binary hash.

The pilot closure uses the original OpenTitan files and real assertion macros,
with `FPV_ON`; it does not modify RTL or DV. Limitations and the artifact
contract are in [SPEC.md](SPEC.md); planned increments are in
[ROADMAP.md](ROADMAP.md). The [formal gap audit](FORMAL_GAP_AUDIT.md) and
[pinned pilot evidence](PILOT_EVIDENCE.md) record what was actually run.
The inventories need Python 3's standard library and their chosen compiler
(Icarus Verilog or slang). The one-sample checker also needs Yosys with
`read_slang`, Z3, and the matching `vvp` runtime for scratch witness replay.

The [Earlgrey pinmux sampler status](PINMUX_SAMPLER_FRONTEND_EVIDENCE.md)
records a separate default-debug-path frontend probe and its unresolved
upstream filelist and temporal-proof gaps.

`pinmux_rev1_bounded.py` checks five reset-grounded transitions of the pinned
sampler's synthesized two-state model against the original typed
`LcHwDebugEnSetRev1_A` expression. See [the bounded evidence](PINMUX_REV1_BOUNDED_EVIDENCE.md)
for the exact EDAM input, solver queries, Icarus witness replay and limits.
This folder is licensed under Apache-2.0.

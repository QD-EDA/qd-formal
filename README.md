# QD Formal

This initial slice is a fail-closed Icarus frontend inventory for the unchanged
OpenTitan `prim_secded_22_16_fpv` checker closure. It is a compiler gate, **not a
formal proof** and not a replacement solver. It checks that Icarus exits cleanly
without diagnostics and registers the exact eight pinned checker names.

```sh
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
The runtime dependencies are Python 3's standard library and the compiler for
the chosen command (Icarus Verilog or slang). This folder is licensed under
Apache-2.0.

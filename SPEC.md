# QD Formal frontend inventory contract

## Scope

Input is the fixed six-translation-unit OpenTitan SECDED FPV closure plus its
three active assertion/flop include files at commit
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. QD invokes Icarus with
`-g2012 -gassertions -DFPV_ON -t stub`, both pinned top modules, and the real
`prim_assert.sv` macros. The output is an inventory of frontend registrations.
It is not a proof, bounded check, simulation result, or claim that the eight
properties have the intended semantics.

## Fail-closed rules

`frontend_inventory_ok` requires all of the following: exact pinned Git commit,
no tracked or untracked checkout changes, all six translation units and three
active include files hashed, a
readable/hashable Icarus executable, exit status zero, empty stdout and stderr,
a produced stub, and exactly one registration for each expected checker name
with no other registered checker. Any violation, including timeout, is
`UNKNOWN`. Macro branches that remove registrations therefore fail the roster
check. The source roster and hashes are included for audit. Output must be
outside the chip checkout so evidence cannot dirty the pin.

The names are `MaxTwoErrors_M`, `SingleErrorDetect_A`,
`SingleErrorDetectReverse_A`, `DoubleErrorDetect_A`,
`DoubleErrorDetectReverse_A`, `SingleErrorCorrect_A`, `SyndromeCheck_A`, and
`SyndromeCheckReverse_A`. Stub registration names do not encode reliable
assert/assume/cover roles; role checking is explicitly outside this contract.

## Artifact schema version 1

`result.json` contains `schema_version`, `result`, `claim`, `proof`, pinned and
observed revision/checkout status, exact compiler `argv` and separate `-V`
version `argv`, `exit_status`, ordered expected
and observed checker identity lists, source SHA-256 map, Icarus path and binary
SHA-256, stub SHA-256, relative names for raw diagnostics, and failure reasons.
`stdout.raw` and `stderr.raw` preserve compiler streams byte-for-byte;
`opentitan-secded.stub` preserves the complete compiler stub. A missing stub
or output is represented by absent hash and a failure reason. The JSON result
must never be interpreted as a solver verdict.

The raw Icarus stub contains process memory addresses, so its SHA-256 may differ
between otherwise identical runs. Repeatability is judged by the pinned inputs,
command, empty diagnostics, result, and checker inventory; the unmodified raw
stub and its run-specific hash remain available for inspection.

## Explicit unsupported cases

The original frontend slice does not emit a solver model or typed property AST, does not solve
assertions/assumptions/covers, and does not validate bind resolution beyond
this pinned elaborated closure. It does not establish X semantics, reset
assumptions, clock fairness, vacuity, unreachable states, induction, multiple
clock behavior, or unbounded safety. It does not use Icarus simulation or its
randomization-oriented Z3 hooks as a formal engine.

## One-sample bounded checker

`secded_one_sample.py` requires both inventories to pass on the same clean
OpenTitan pin with identical source hashes. It requires slang 11.0.448, the
exact bound instance, roles, expression fingerprints, positive clock edge, and
reset disable. Its narrow lowerer accepts only the typed AST shapes of
`MaxTwoErrors_M` and `SyndromeCheckReverse_A`; anything else is `UNKNOWN`.

The generated equation and the unchanged encoder/decoder/testbench are read by
Yosys `read_slang`. Direct Z3 queries require: no satisfying bad sample;
satisfying antecedent, zero-error, and two-error samples; an impossible
three-error sample under the assumption; and a possible three-error sample
without it. The separate `--scratch-fault` run requires a satisfying bad sample;
Icarus replays that exact witness with the original checker and bind, confirms
all eight registrations, no assertion failures on unchanged RTL, and a named
`SyndromeCheckReverse_A` failure on the mutation. The mutant never changes the
pinned checkout.

`one_sample_check_ok` means the direct SMT bad query is `unsat` under the
stated two-state, one-sample mapping. The checker does not establish unbounded
behavior, four-state equivalence, reset sequencing, or the other six asserted
properties. `yosys-smtbmc` is not used: its exported assertion for this harness
is constant true, so its `PASSED` result would be vacuous. Every command,
stream, solver query, model, mapping, source/tool hash, and tool version is
retained in the external evidence directory. Unsupported output is `UNKNOWN`.

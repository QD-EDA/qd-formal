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

## Pinmux Rev1 bounded model check

`pinmux_rev1_bounded.py` requires the clean pinned OpenTitan checkout and the
canonical FuseSoC `pinmux_chip_fpv` EDAM plus exact exported source bytes.
Only verified `core_file` paths to files inside the pinned checkout may
relocate. It excludes the broken chip
FPV testbench and three unused VIP/bind/CSR files, leaving 217 compilation
units for a selected `pinmux_strap_sampling` top. The sampler and four
critical dependencies must also match their original source bytes. The EDAM
reader and its tests use pinned PyYAML 6.0.3. The runner rechecks the EDAM,
export, generated core, and clean checkout after the proof and replay.

The original Rev1 SVA must appear in slang's typed AST at the pinned source
line, role, clock, reset, operands, `##1` delay, `$past` call, and expression
fingerprint. Icarus must register the ten sampler-local names once each and
the pinned dependency roster. These are frontend gates. Yosys `read_slang`
then synthesizes the same source selection to a two-state RTL transition
model; its `SYNTHESIS` macro drops the original SVA. The solver explicitly
queries the translated temporal condition using the named q and strap wires,
not Yosys's vacuous assertion export.

With s0 reset low and s1..s5 reset high, an UNSAT reset query establishes
q(s1)=Off. Four UNSAT bad queries range over **all** other sampler inputs and
ask whether `q[n] != On && q[n+1] == On && !strap_en_i[n]` is reachable for
n=1..4. A SAT fixed-input rise cover, UNSAT early-rise boundary, and SAT
scratch-fault bad rise check nonvacuity and sensitivity. For witness replays,
all top-level inputs are fixed in SMT to the generated SV harness values;
Z3-returned relevant inputs generate the Icarus stimuli. An original-on-fault-
inputs control replay and a mutant replay must agree with solver q samples.
The mutant must produce the **original** named Rev1 failure at the aligned
clock despite VVP's zero exit status. Every failing tool, changed source,
unsupported AST/SMT/solver value, warning, or replay mismatch is `UNKNOWN`.

`bounded_model_check_ok` is a finite result for the synthesized two-state
sampler model and sampled correspondence. It is not exhaustive equivalence
to original four-state SV execution or proof of the full original SVA. The
pinmux-to-RV_DM chip path, NDM retention, and production qualification remain
UNKNOWN. Raw models, queries, commands, diagnostics, witnesses, source/tool
hashes, and result are mandatory evidence artifacts.

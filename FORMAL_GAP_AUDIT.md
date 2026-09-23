# Icarus UVM formal gap audit — 2026-09-23

This audit uses original, pinned chip formal sources without changing application
RTL or DV. It records compiler compatibility, not proof. The relevant Icarus UVM
baseline is current `main` at `6fd804a39e803152bd39a3ee4c96b15d30532001`,
built as a matched compiler/runtime at `/tmp/iverilog-sva-macro-install`.
`iverilog -V` reports 13.0 devel; the source commit above identifies the build.
`-t stub` checks parsing and elaboration only.

This is a bounded compatibility sample, not a suite-wide formal qualification.
OpenTitan has many separate FPV targets and Caliptra has formal property trees
for DOE, ECC, HMAC, SHA-256 and SHA-512. The two closures below were selected
to expose an active assertion/assumption path and a concrete elaboration blocker.

| Original formal target | Current-main result | Next gap |
| --- | --- | --- |
| [OpenTitan](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19) `lowrisc:fpv:prim_secded_22_16_fpv`, with `FPV_ON` and the real standard macros | Exit 0, empty stderr, eight active `$ivl_register_assertion` records: seven assertions and one assumption. | No proof backend or formal assumption handling exists. Preserve this original file closure as a frontend regression; reject zero active properties. |
| [Caliptra](https://github.com/chipsalliance/caliptra-rtl/tree/49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e) bound SHA-256 core constraints | Exit 0, empty stderr, two registered assumptions. Stub names are generated `assert_L25_0` and `assert_L30_1`, not the source labels. | Their source identities, roles and resolved semantics must be exported and checked before using them as proof constraints. Simulation assumption diagnostics do not constrain inputs. |
| Caliptra SHA-256 assertion IP (`fv_sha256_core.sv`), formal package and constraints | Exit 1: `fv_sha256_core_pkg.sv:26` fails to evaluate parameter `K`, an indexed assignment pattern for an unpacked-array typedef. The parser accepts the pattern, but elaboration stops before any of the nine assertions. | Repair or explicitly reject this parameter evaluation, then rerun the unchanged full closure. `idle_wait_a` is a candidate one-cycle property, subject to actual elaboration and assumption review. |

The two chip revisions are clean pinned checkouts. The OpenTitan run used:

```sh
/tmp/iverilog-sva-macro-install/bin/iverilog \
  -g2012 -gassertions -DFPV_ON -I hw/ip/prim/rtl -t stub \
  -s prim_secded_22_16_tb -s prim_secded_22_16_bind_fpv \
  -o /tmp/qd-formal-audit/opentitan-secded-main.stub \
  hw/ip/prim/rtl/prim_assert.sv \
  hw/ip/prim/rtl/prim_secded_22_16_enc.sv \
  hw/ip/prim/rtl/prim_secded_22_16_dec.sv \
  hw/ip/prim/fpv/vip/prim_secded_22_16_assert_fpv.sv \
  hw/ip/prim/fpv/tb/prim_secded_22_16_tb.sv \
  hw/ip/prim/fpv/tb/prim_secded_22_16_bind_fpv.sv
```

The Caliptra full assertion-IP run used:

```sh
/tmp/iverilog-sva-macro-install/bin/iverilog \
  -g2012 -gassertions -t stub -s sha256_core \
  -o /tmp/qd-formal-audit/caliptra-sha256-core-main.stub \
  src/sha256/rtl/sha256_k_constants.v \
  src/sha256/rtl/sha256_w_mem.v \
  src/sha256/rtl/sha256_core.v \
  src/sha256/formal/properties/fv_sha256_core_pkg.sv \
  src/sha256/formal/properties/fv_sha256_core.sv \
  src/sha256/formal/properties/fv_sha256_core_constraints.sv
```

Removing the package and assertion IP from that command leaves the same RTL
plus `fv_sha256_core_constraints.sv`; this separate constraints probe exits 0
with two registrations and no diagnostics. It does not establish a valid
formal assumption set. Slang 11.0.448 and Verilator 5.051 devel accept
minimal Caliptra-shaped parameter fixtures, providing syntax oracles, but
not proof of the full IP.

The [OpenTitan formal setup](https://opentitan.org/book/doc/getting_started/setup_formal.html)
defines FPV jobs through `dvsim` and FuseSoC. The
[Caliptra SHA-256 formal README](https://github.com/chipsalliance/caliptra-rtl/blob/49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e/src/sha256/formal/readme.md)
says to load its assertion IP, DUT and constraints together, but supplies no
checked-in job script. These direct compiles are compatibility probes, not
replays of either vendor's formal run.

## Version finding

The preinstalled compiler in the separate `iverilog-uvm` development checkout
reported `13.0 (devel) (9bd5082b8)` and came from an older branch rooted at
`0ff77277c1676e0a08ab3e145a04bb372cc9bb75`, 732 commits behind current
`main`. That build failed OpenTitan's grouped property grammar and warned on
Caliptra's forward property references. Current `main` already contains
[IEEE 1800-2017's grouped `property_expr` form](https://fpga.mit.edu/6205/_static/F25/documentation/1800-2017.pdf)
and resolves both issues. No duplicate parser patch will be submitted. The
older binary's `vvp` also has a missing Z3-library link. A clean matched arm64
build of current `main` at `/tmp/qd-iverilog-current-install` runs SVA simulation.
The repo's historical undefined-sequence repro text is also stale for this
revision: an independently run `NoSuchSeq_S |=> 1'b0` assertion exits 1 with
an unresolved-name **error**, rather than the older warning. This does not
remove the need to reject other dropped-property diagnostics.
The checked-in unsupported multiclock regression
`sv_assert_multiclock_bounded_antecedent_unsupported_65tick_bound.v` exits 1
and reports `sorry: ... the assertion is dropped` under this build. A formal
preflight should preserve that raw diagnostic and reject the input even if
a later compiler version changes the exit status.

## Engine boundary

The public `ivl_target.h` API exposes elaborated RTL and procedural statements,
but no first-class typed concurrent property objects. Icarus lowers the
frontend's SVA structures to simulation-checker processes before target output.
Its Z3 code supports SystemVerilog constrained randomization, not RTL/SVA
transition-system proof. A false `assume property` in the matched current-main
runtime printed two simulation `ERROR` reports and exited **0** after `$finish`, showing
why successful simulation cannot substitute for formal assumption semantics.

QD Formal should be a separate solver-backed tool with a small Icarus frontend
export hook that retains property kind, name, bind instance, source, clock,
disable condition and supported temporal structure before lowering. The first
backend scope is finite-bound, single-clock, two-state analysis with explicit
`unsupported` or `unknown` for every unmodeled construct, assumptions as solver
constraints, and independently replayed counterexample or cover witnesses.
A bounded no-counterexample result is not unbounded proof or signoff.

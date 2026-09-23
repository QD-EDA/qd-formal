# Icarus UVM formal gap audit — 2026-09-23

This audit uses original, pinned chip formal sources without changing application
RTL or DV. It records compiler compatibility, not proof. The original Icarus
UVM probes below used source commit
`6fd804a39e803152bd39a3ee4c96b15d30532001`, built as a matched
compiler/runtime at `/tmp/iverilog-sva-macro-install`; `iverilog -V` reported
13.0 devel. Current main is `7943dffd1a426418cd975883753af7cdb2e18e46`; PR
#342 is based on that revision. In every case, `-t stub` checks parsing and
elaboration only.

This is a bounded compatibility sample, not a suite-wide formal qualification.
OpenTitan has many separate FPV targets, and Caliptra's SHA-256 closure is one
small part of its formal sources. Pinned Caliptra also includes the Adams Bridge
formal tree described below; neither this census nor any compile is a proof.

| Original formal target | Recorded frontend result | Next gap |
| --- | --- | --- |
| [OpenTitan](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19) `lowrisc:fpv:prim_secded_22_16_fpv`, with `FPV_ON` and the real standard macros | Exit 0, empty stderr, eight active `$ivl_register_assertion` records: seven assertions and one assumption. | This one combinational SECDED closure is a frontend regression, not representative of OpenTitan's broader FPV suite. Other pinned sources include liveness and bounded-delay properties, for example [TL-UL](https://github.com/lowRISC/opentitan/blob/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/ip/tlul/rtl/tlul_assert.sv#L343) and [OTBN](https://github.com/lowRISC/opentitan/blob/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/ip/otbn/rtl/otbn_core.sv#L1331); these are separate sources, not part of the SECDED closure. No proof backend or formal assumption handling exists; reject zero active properties. |
| [Caliptra](https://github.com/chipsalliance/caliptra-rtl/tree/49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e) bound SHA-256 core constraints | On the prior current-main source, the separate constraints-only probe exited 0 with two generated assumption registrations. | Preserve source identity, role, and resolved semantics before using assumptions as proof constraints. Simulation assumption diagnostics do not constrain inputs. |
| Caliptra SHA-256 assertion IP (`fv_sha256_core.sv`), formal package and constraints | The earlier current-main build stopped at `fv_sha256_core_pkg.sv:26` while evaluating parameter `K`, before the nine assertions. [Icarus UVM PR #342](https://github.com/dsellerbrock/iverilog-uvm/pull/342) patches this elaboration case. Its head `d1d16aac99d491fa1163e3e45104f58807568f15`, based on current Icarus `7943dffd1a426418cd975883753af7cdb2e18e46`, reports a clean full-closure frontend compile with nine assertions and two assumptions. All six CI checks were pending at this audit update. | This is compile/elaboration evidence only, with no solver behavior, assumption meaning, or property validity established. `idle_wait_a` remains a candidate for the first bounded pilot after typed export and assumption review. |

### Caliptra formal source census

At the pinned Caliptra revision, its Adams Bridge submodule is pinned to
`b77e3d899e828d626cfc2a0d26a6b5704cc121e0`. Its `formal/` tree contains 74
SystemVerilog files; a text search finds property declarations in 41 of them.
This is a source census, not a count of active properties in one elaborated
closure. The source includes safety assertions, covers, liveness properties
using `s_eventually`, `disable iff`, `$past`, and `bind` statements that
connect properties to DUT hierarchy. For example, the pinned
[compress properties](https://github.com/chipsalliance/adams-bridge/blob/b77e3d899e828d626cfc2a0d26a6b5704cc121e0/formal/fv_compress/fv_compress_top.sv#L519)
include a `disable iff` safety assertion, a
[cover property](https://github.com/chipsalliance/adams-bridge/blob/b77e3d899e828d626cfc2a0d26a6b5704cc121e0/formal/fv_compress/fv_compress_top.sv#L615),
and a [DUT bind](https://github.com/chipsalliance/adams-bridge/blob/b77e3d899e828d626cfc2a0d26a6b5704cc121e0/formal/fv_compress/fv_compress_top.sv#L654); the same file also uses [`$past`](https://github.com/chipsalliance/adams-bridge/blob/b77e3d899e828d626cfc2a0d26a6b5704cc121e0/formal/fv_compress/fv_compress_top.sv#L602).
The [NTT control properties](https://github.com/chipsalliance/adams-bridge/blob/b77e3d899e828d626cfc2a0d26a6b5704cc121e0/formal/fv_ntt_ctrl/ntt_ctrl_gs_mlkem/ntt_ctrl_gs_mlkem.sv#L701)
include a liveness assertion. This source census identifies semantic and
elaboration cases that a small pilot must not silently drop; it is not a claim
that all 74 files are one compile closure or that these properties were proved.
The older count of 141 SV files describes a broader Caliptra snapshot and must
not be read as the Adams Bridge formal-tree count.

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

The near-term seam is typed property data alongside elaborated RTL: retain
property kind, name, bind instance, source, clock, disable condition, and
temporal structure. Slang's typed JSON AST is an observed option for a
property sidecar; it still needs mapping to the RTL transition model. The first bounded pilot remains
OpenTitan `SyndromeCheckReverse_A` under `MaxTwoErrors_M`; Caliptra SHA-256
`idle_wait_a` is a follow-on candidate. The initial engine scope is finite-bound,
single-clock, two-state analysis. Every unsupported construct must produce an
explicit per-construct `UNKNOWN` (or `unsupported`) result; assumptions must
become solver constraints, and counterexample or cover witnesses must be
independently replayed. A bounded no-counterexample result is not an unbounded
proof or signoff.

An observed option for the typed-property sidecar is Slang 11.0.448's
`--ast-json --ast-json-source-info` on the same pinned OpenTitan and Caliptra
SHA-256 closures: both returned zero status with no diagnostics, and the JSON
contained eight typed concurrent assertions for OpenTitan (one assume, seven
asserts) and eleven for Caliptra SHA-256 (nine asserts, two assumes), with
property source, instance, clock/disable, expression, and type information.
AST address fields vary between runs. This is frontend evidence only. A typed
property sidecar still needs mapping to the elaborated RTL transition model;
Icarus compatibility checks and independent witness replay remain separate
gates, and unsupported constructs need per-construct `UNKNOWN` results.

### Backend integration blocker

A read-only probe also found a false-green trap in the OSS Yosys/SBY route.
With Yosys 0.68+80 `read_slang` and SBY 0.68, the pinned OpenTitan closure selects
`SYNTHESIS` dummy assertion macros, so SBY sees no checkers and can report PASS
for an empty property set. With `--single-unit --no-synthesis-define -DFPV_ON`,
the original `|->` properties instead produce seven unsupported-SVA errors.
Thus Slang's typed AST is a possible property sidecar, not direct acceptance of
the source by the OSS proof backend. A useful backend path needs typed property
lowering, a verified nonempty exact checker roster, and independent Icarus
frontend/replay checks; anything unmapped remains per-construct `UNKNOWN`.

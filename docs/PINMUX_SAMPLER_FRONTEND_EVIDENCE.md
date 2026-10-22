# Earlgrey pinmux sampler frontend status — 2026-09-24

The default Earlgrey configuration sets `RvDmUseDmiInterface=0`; its pinmux
strap sampler retains debug permission and feeds the RV_DM JTAG path. The
original `pinmux_strap_sampling.sv` asserts `LcHwDebugEnSetRev0_A` and
`LcHwDebugEnSetRev1_A` against unauthorized Off-to-On transitions.

The pinned OpenTitan checkout is
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. FuseSoC 2.4.5 and
Edalize 0.6.3 resolve the checked-in
`lowrisc:earlgrey_systems:pinmux_chip_fpv:0.1` default target to 221
compilation sources and nine include-only files. With `FPV_ON`, slang
11.0.448+e222e7dc0 parses them, but semantic elaboration fails: the EDAM
omits `top_earlgrey_pkg`, and the checked-in chip testbench's implicit
connection lacks `lc_hw_debug_clr_i`. The matched Icarus 13.0 development
frontend stops at the missing package. These diagnostics are retained; the
OpenTitan sources were not changed.

For a narrower frontend question, a QD-only filelist projection omits that
testbench and unused VIP/bind/CSR assertion units while keeping the original
sampler and its RTL dependencies byte-identical. Slang then elaborates the
sampler as top with zero diagnostics. Its typed AST contains 16 concurrent
properties (13 assertions, three assumptions); Rev0 and Rev1 are both present
as clocked, reset-disabled temporal properties. Icarus `-t stub` also exits 0
without diagnostics and registers each target name once. Its full registration
count is 20, versus slang's 16 elaborated properties; the difference is not
yet reconciled. The exact filelists, argv, tool hashes, AST, stub and raw
outputs are retained in the QD-EDA workspace under
`evidence/pinmux-default-fpv-edam-probe/` and
`evidence/pinmux-sampler-cone-probe/`.

This is frontend evidence only. No solver checked Rev0/Rev1, no witness was
replayed through the selected sampler, and the downstream default-chip RV_DM
gate is not instantiated. The upstream FPV target remains blocked; the
selected-module projection is not a replacement for it. The next proof slice
must lower the typed `##1` and `$past` semantics, reconcile frontend rosters,
model reset and retained state, and independently replay any witness. Until
then the debug property result is UNKNOWN.

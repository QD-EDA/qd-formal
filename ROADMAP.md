# Roadmap

1. **Frontend inventory (delivered):** pinned OpenTitan SECDED closure, clean
   Icarus stub build, exact eight-name registration check, raw evidence
   files, and fail-closed `UNKNOWN` handling.
2. **Typed property inventory (delivered):** retain property role, source/bind
   identity, clock/reset conditions, and typed temporal/expression structure
   alongside elaborated RTL. Slang's JSON AST has been observed to expose
   typed property nodes for both pinned pilot closures and is an option for a
   property sidecar; Icarus compatibility and witness replay remain separate
   checks. General mapping of the typed sidecar to an RTL transition model is
   still open.
   Unsupported constructs must produce per-construct `UNKNOWN`, not disappear.
3. **First bounded engine slice (delivered):** consume that typed export in a
   narrow bounded engine. The original OpenTitan `SyndromeCheckReverse_A` under
   `MaxTwoErrors_M` in `prim_secded_22_16_fpv`: it is a combinational SECDED
   cone sampled on `clk_i`. The runner checks bad and nonvacuity boundaries with
   Z3, replays an exact planted-fault witness through the original Icarus bound
   checker, and retains raw commands and hashes. The repeated pinned result is
   one two-state sample, not unbounded or four-state proof. See
   [ONE_SAMPLE_EVIDENCE.md](ONE_SAMPLE_EVIDENCE.md).
4. **Transition slice, then lifecycle/debug pilot (next):** first investigate the
   original `rv_dm_dmi_gate` `LcHwDebugEnSetRev1_A` assertion: retained debug
   permission may rise only after strap sampling. Its companion `Rev0_A`
   checks prior synchronized lifecycle authorization. Their two-sample
   transition semantics permit the documented NDM reset retention. The pinned
   Earlgrey top defaults `RvDmUseDmiInterface=0`, so this isolated gate is an
   RV_DM DV/alternate configuration, not the default chip's debug path. Require
   a clean typed-property inventory, reset-grounded reachable-state model,
   nonvacuous rise and retained-state covers, and independent replay through
   the original checker. An isolated ten-step SAT probe has no violation and a
   retained-state cover. A separate full original `rv_dm` parent simulation
   activates Rev1 and detects a scratch-only RTL fault, but it is not replay of
   that exact solver witness; the integrated temporal verdict remains UNKNOWN.
   For the default Earlgrey qualification pilot, use the original pinmux
   strap-sampling assertion and trace retained permission through its RV_DM
   connection. The pinned pinmux FPV EDAM currently fails semantic elaboration
   because its testbench lacks a package and a port connection. A QD-only
   selected-module projection of unchanged sampler RTL exposes Rev0/Rev1 in
   slang and Icarus, but neither a complete upstream FPV run nor a proof.
   See [the sampler frontend evidence](PINMUX_SAMPLER_FRONTEND_EVIDENCE.md).
   Upstream policy is an interim oracle; hardware-policy review is required
   for qualification.
5. **Broader formal coverage:** Caliptra SHA-256 `idle_wait_a` checks the next
   clock's state and register arrays, so it requires a reset-grounded transition
   model and sampled-history semantics. Add only the SVA, clock, memory and
   four-state shapes demanded by pinned design configurations, each with an
   independent oracle and explicit `UNKNOWN` outside its supported scope.

No milestone may label parser inventory, simulation, or randomization as formal
proof. `UNKNOWN` is the only acceptable result where the frontend, semantics,
or evidence are incomplete.

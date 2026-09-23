# Roadmap

1. **Frontend inventory (this slice):** pinned OpenTitan SECDED closure, clean
   Icarus stub build, exact eight-name registration check, raw evidence
   files, and fail-closed `UNKNOWN` handling.
2. **Typed property + RTL export seam:** retain property role, source/bind
   identity, clock/reset conditions, and typed temporal/expression structure
   alongside elaborated RTL. Slang's JSON AST has been observed to expose
   typed property nodes for both pinned pilot closures and is an option for a
   property sidecar; Icarus compatibility and witness replay remain separate
   checks. Mapping the typed sidecar to an RTL transition model is still open.
   Unsupported constructs must produce per-construct `UNKNOWN`, not disappear.
3. **Bounded engine integration:** consume that typed export in a bounded
   engine. First target the original OpenTitan `SyndromeCheckReverse_A` under
   `MaxTwoErrors_M` in `prim_secded_22_16_fpv`: it is a combinational SECDED
   cone sampled on `clk_i`. Check the zero/one/two-bit error masks against an
   independent parity implementation, and replay a planted decoder fault
   through the original bound checker. Emit a per-property bounded result,
   assumptions, unsupported features, solver trace and replayable witness.
   Validate vacuity and boundary cases; a bounded result is not unbounded proof.
   Caliptra SHA-256 `idle_wait_a` is the next candidate after the PR #342
   elaboration fix lands and state-array modeling is supported. This is a future
   engine milestone, not delivered here.
4. **Qualification pilot:** after the engine exists, select a named OpenTitan
   lifecycle/debug property and have hardware-policy owners review the property
   mapping and assumptions. SECDED frontend parsing alone is not qualification.

No milestone may label parser inventory, simulation, or randomization as formal
proof. `UNKNOWN` is the only acceptable result where the frontend, semantics,
or evidence are incomplete.

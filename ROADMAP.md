# Roadmap

1. **Frontend inventory (this slice):** pinned OpenTitan SECDED closure, clean
   Icarus stub build, exact eight-name registration check, immutable evidence
   files, and fail-closed `UNKNOWN` handling.
2. **Typed frontend boundary:** extend Icarus elaboration export so each
   supported property has a stable source/bind identity, assert/assume/cover
   role, clock/reset conditions, and typed temporal/expression structure.
3. **Bounded engine integration:** consume that typed export in a bounded
   engine; emit per-property bounded result, assumptions, unsupported features,
   solver trace and a replayable counterexample/cover witness. Validate with
   planted faults and vacuity/boundary cases; use independent checking and
   simulator replay. This is a future engine milestone, not delivered here.
4. **Qualification pilot:** after the engine exists, select a named OpenTitan
   lifecycle/debug property and have hardware-policy owners review the property
   mapping and assumptions. SECDED frontend parsing alone is not qualification.

No milestone may label parser inventory, simulation, or randomization as formal
proof. `UNKNOWN` is the only acceptable result where the frontend, semantics,
or evidence are incomplete.

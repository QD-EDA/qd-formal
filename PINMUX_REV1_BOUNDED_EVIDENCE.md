# Pinned pinmux Rev1 bounded model check

`pinmux_rev1_bounded.py` checks one selected OpenTitan sampler module at commit
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`. The unmodified upstream
`pinmux_chip_fpv` EDAM does not elaborate because its testbench omits
`top_earlgrey_pkg` and `lc_hw_debug_clr_i`. This runner uses its 217-source
sampler projection, excluding that testbench and three unused VIP/bind/CSR
translation units. It verifies the canonical EDAM identity, all 230 exported source/include
byte hashes as one pinned aggregate, and five key copies against the clean
OpenTitan checkout. It also checks that every file under the exported `src/`
tree is listed in the EDAM; the four include directories contain no unlisted
files. The original `pinmux_strap_sampling.sv` is unchanged.

FuseSoC writes checkout-relative paths into 85 EDAM `core_file` entries, so a
fresh clean checkout changes the raw EDAM SHA-256. The runner verifies that
each of those paths is an existing file inside the supplied pinned checkout,
then replaces only the checkout prefix for its canonical digest. It preserves
ordered file and dependency lists, tool options, parameters, and every other
EDAM value. The generated CSR core path and bytes are pinned separately;
duplicate YAML keys, path escapes, missing files, or any other manifest edit
yield `UNKNOWN`. `result.json` records both the raw EDAM hash and canonical
digest.

Run with a fresh evidence directory and the generated EDAM described in
[the frontend status](PINMUX_SAMPLER_FRONTEND_EVIDENCE.md):

```sh
/path/to/python-with-PyYAML pinmux_rev1_bounded.py \
  /path/to/clean/opentitan /path/to/pinmux_chip_fpv.eda.yml /tmp/qd-rev1 \
  --slang /path/to/slang --yosys /path/to/yosys \
  --z3 /path/to/z3 --iverilog /path/to/iverilog
python3 -m unittest discover -s tests -v
```

The observed pinned run returned `bounded_model_check_ok`: `reset-grounding`
was UNSAT for `q(s1) != Off` after the reset transition; four bad queries were
UNSAT for sampled transitions s1→s2 through s4→s5. Those bad queries constrain
`rst_ni=0` at s0 and `rst_ni=1` at s1..s5, and leave **every other sampler
input free** at every state. The original Rev1 expression is fingerprinted from
slang's typed AST: `lc_tx_test_false_loose(q) ##1
lc_tx_test_true_strict(q) |-> $past(strap_en_i)` on `posedge clk_i`, disabled
under reset. In two-state form, false-loose means `q != On`, including every
other four-bit code, so each bad query asks whether a non-On-to-On rise can
occur without the prior strap. A fixed-input, nonvacuous rise cover was SAT at
s4→s5; an early-rise boundary at s1→s2 was UNSAT.

The scratch-only fault removes `lc_tx_and_hi(lc_strap_en, ...)` from one copied
RTL assignment. With all top-level sampler inputs fixed to recorded values,
the mutant has a SAT bad rise at s3→s4 while strap remains low. Z3's returned
input values generated the Icarus replay. The same inputs on unchanged RTL
kept `q=Off`, while the mutant reached `q=On` and the **original**
`LcHwDebugEnSetRev1_A` reported failure at simulation time 45. A separate
good-cover witness rose only after strap. The runner compares Icarus samples
to the solver's `q` values and parses the named assertion text because VVP
returns exit status zero even after `$error`.

This is a bounded check of Yosys `read_slang`'s **synthesized two-state RTL
transition model**, plus a separate typed check of the original SVA and
sampled Icarus correspondence. `read_slang` defines `SYNTHESIS`, so the
original SVA is absent from that backend model; no Yosys assertion pass is
used. The Icarus replays sample selected traces, not all SV scheduling or
four-state behavior. This does not prove the full original SVA in simulation,
the default Earlgrey pinmux-to-RV_DM path, reset retention, or chip policy.
Those remain `UNKNOWN`. New EDAM/source bytes, typed property shapes, tool
diagnostics, missing roster entries, solver `unknown`, or replay mismatch also
return `UNKNOWN`.

The initial local raw run is in `../evidence/pinmux-rev1-bounded-final/` in the
QD-EDA workspace. It retains the AST, both Yosys SMT models, every SMT query
and response, three generated replay sources, Icarus/VVP streams, exact argv,
all source/tool SHA-256 values, and `result.json`. The slang, Icarus, and
Yosys source reads all use `FPV_ON`; Yosys also defines `SYNTHESIS`. A local
`time -l` run took 2.84 seconds wall time and 176,996,352 bytes maximum
resident set size. The
tool versions were Python 3.13.15 with PyYAML 6.0.3, slang
11.0.448+e222e7dc0, Yosys 0.68+80 (`621d943ac-dirty`), Z3 4.15.5,
and matched Icarus/VVP 13.0 development builds. A second independent clean
checkout and fresh FuseSoC export produced the same canonical EDAM digest,
all 230 source hashes, property fingerprint, nine solver outcomes, and three
replay witnesses. The two raw EDAM hashes differ as expected. The exact setup,
negative pre-fix `UNKNOWN`, both successful reruns, and 26-test regression
are in `../evidence/pinmux-rev1-second-checkout/`. Both runs used the same
machine and tool binaries; this is repeatability evidence, not production
qualification or a release claim.

# Pinned pinmux Rev0 companion check — 2026-09-24

The clean OpenTitan checkout was `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`.
The runner consumed the same canonical 217-source sampler projection and all
230 exported source/include hashes used for Rev1. The canonical EDAM SHA-256
was `b83c37dcb51cdcbd8c0bf3cfb1c48690f516b2be74e7ff767592262eacac927e`.
The original typed `LcHwDebugEnSetRev0_A` at line 217 had expression SHA-256
`c948e71b7d02ae9094ecdb910d3955ee3489bd47472550022ce34c77fdc53872`.
Icarus registered it once in the exact 20-checker selected-module roster.

```sh
/Users/danielellerbrock/QD-EDA/evidence/pinmux-config/venv/bin/python \
  pinmux_rev1_bounded.py /tmp/qd-opentitan-formal-repeat-20260924 \
  /tmp/qd-pinmux-fpv-repeat-venv-20260924/lowrisc_earlgrey_systems_pinmux_chip_fpv_0.1/default-icarus/lowrisc_earlgrey_systems_pinmux_chip_fpv_0.1.eda.yml \
  /Users/danielellerbrock/QD-EDA/evidence/pinmux-rev0-bounded-final \
  --slang /Users/danielellerbrock/oss-cad-suite/bin/slang \
  --yosys /Users/danielellerbrock/oss-cad-suite/bin/yosys \
  --z3 /Users/danielellerbrock/oss-cad-suite/bin/z3 \
  --iverilog /tmp/iverilog-sva-macro-install/bin/iverilog \
  --property LcHwDebugEnSetRev0_A
/Users/danielellerbrock/QD-EDA/evidence/pinmux-config/venv/bin/python \
  -m unittest discover -s tests -q
```

The run exited 0 with `bounded_model_check_ok`; 29 unit tests passed. Z3
returned UNSAT for reset grounding, four all-input bad-rise queries, and the
fixed early-rise boundary. The authorized good rise and the QD-only
lifecycle-bypass fault were SAT. The good solver witness had sampled
`lc_hw_debug_en[0]=On` before q rose; the fault had that signal Off before q
rose. Icarus replay agreed with all five sampled q and lifecycle values.
Original RTL on the fault inputs and the good cover produced no assertion
failure. The mutant produced only the original named Rev0 failure at event
and report time 45; VVP itself exited zero. The post-run EDAM, source, and
checkout recheck was stable. All exact commands, raw streams, models, queries,
witnesses, tool hashes, and `result.json` are in
[`../evidence/pinmux-rev0-bounded-final/`](../evidence/pinmux-rev0-bounded-final/).

The tool versions recorded by `result.json` are Python 3.13.15 with PyYAML
6.0.3, slang 11.0.448+e222e7dc0, Yosys 0.68+80 (dirty build), Z3 4.15.5,
and matched Icarus/VVP 13.0 development builds. The unmodified Rev1 default
path was rerun into `../evidence/pinmux-rev1-regression-after-rev0-final/`
and also returned `bounded_model_check_ok`.

The same Rev0 command was repeated from the separate clean OpenTitan checkout
`/Users/danielellerbrock/projects/iverilog_uvm/opentitan-upstream`, with its
untouched EDAM at
`/tmp/qd-pinmux-default-fpv-edam/lowrisc_earlgrey_systems_pinmux_chip_fpv_0.1/default-icarus/lowrisc_earlgrey_systems_pinmux_chip_fpv_0.1.eda.yml`
and output `../evidence/pinmux-rev0-bounded-original-repeat/`. It exited 0.
Both results have identical canonical EDAM, 230 source hashes, typed property,
checker roster, nine solver outcomes, witnesses, tool identities, and stable
postcheck. Their raw EDAM hashes differ only because the checkout paths differ.
Both checkouts remained clean. This repeats the bounded result on one host and
toolchain; it is not an independent model extraction or full-SVA oracle.

This is a five-transition two-state result on Yosys's synthesized sampler,
with selected original-checker replay. It does not establish exhaustive
four-state SVA equivalence, the broken upstream chip FPV target, downstream
RV_DM behavior, or production qualification. The pinned pilot ran locally;
the repository CI currently runs unit tests and does not provision this
OpenTitan/FuseSoC/Icarus/slang/Yosys/Z3 toolchain.

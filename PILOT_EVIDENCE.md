# Pinned OpenTitan SECDED frontend pilot

Run on 2026-09-23 with macOS Darwin 27.0.0 arm64, Python 3.14.7,
OpenTitan `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19` (clean), and an
Icarus 13.0 devel build from source commit
`6fd804a39e803152bd39a3ee4c96b15d30532001`. The executable SHA-256 was
`399d5fe468d296c0c419e3d9bda526ac711f5b0143360eccb16d642cbd5ea0f2`.

From the `qd-formal` repository:

```sh
python3 -m unittest discover -s tests -v
python3 qd_formal.py preflight \
  /Users/danielellerbrock/projects/iverilog_uvm/opentitan-upstream \
  /tmp/qd-formal-root-review \
  --iverilog /tmp/iverilog-sva-macro-install/bin/iverilog
```

All eight tests passed. The preflight returned `frontend_inventory_ok` twice
with compile exit 0, empty compile stdout/stderr, and exactly eight expected
checker names once each. The report hashes the six compiled source files, three
active macro include files, and compiler binary; it retains argv, `iverilog -V`
output, raw compile streams and the raw stub. The two raw stub hashes differed
because Icarus prints process memory addresses, while the checker inventory and
gate result matched. The run artifacts are at `/tmp/qd-formal-root-review` on the
pilot host.

This proves only that this pinned Icarus frontend build registered the expected
checkers for the unchanged OpenTitan closure. The stub does not establish each
checker’s assert/assume/cover role, temporal meaning, solver constraint, or proof
result. No SAT/SMT query, counterexample, replay, or production qualification
was performed. Caliptra's complete SHA-256 assertion IP remains blocked at
formal-package parameter elaboration; see [FORMAL_GAP_AUDIT.md](FORMAL_GAP_AUDIT.md).

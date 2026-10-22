# qd-formal

Quick and dirty **bounded formal checks** on pinned OpenTitan RTL. It is deliberately conservative: anything it cannot establish reports `UNKNOWN` and exits non-zero.

| | |
|---|---|
| Language | Python 3 (+ Icarus Verilog, slang, Yosys, Z3 as external tools) |
| Pinned target | OpenTitan commit `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`, `prim_secded_22_16_fpv` |
| Status | Active prototype (Sep 2026) |
| License | Apache-2.0 |

## Checks

| Step | Tool | Result name | What it is (and is not) |
|---|---|---|---|
| Frontend inventory | `qd_formal.py preflight` | `frontend_inventory_ok` | Icarus compiles the checker cleanly and registers the exact 8 pinned names. A compiler gate, **not a proof** |
| Semantic inventory | `slang_inventory.py` | `semantic_frontend_inventory_ok` | Typed slang AST: 1 assumption, 7 assertions, clock, disable condition, expression fingerprints. No solver |
| One-sample SECDED check | `secded_one_sample.py` | `one_sample_check_ok` | Z3 over one two-state posedge sample of encoder, decoder and testbench. Bounded, **not** an unbounded or four-state SVA proof |

## Run

```sh
python3 -m pip install -r requirements.txt
python3 qd_formal.py preflight /path/to/clean/opentitan /tmp/qd-formal-secded --iverilog /path/to/iverilog
python3 -m unittest discover -s tests -v
```

Each run writes `result.json`, raw tool output and source/tool hashes to a fresh evidence directory. Wrong pin, dirty checkout, timeout or roster mismatch gives `UNKNOWN`.

## More

[docs/usage.md](docs/usage.md) has the full commands and limits; evidence notes and the roadmap are in `docs/`; [SPEC.md](SPEC.md) is the contract.

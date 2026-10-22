# qd-formal

Bounded formal checks on pinned OpenTitan/Caliptra RTL: an Icarus frontend inventory (a compiler gate, not a proof), a typed slang property inventory and one bounded SECDED check.

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

Full usage and evidence: [docs/usage.md](docs/usage.md). Spec: [SPEC.md](SPEC.md).

Status: active prototype (Sep 2026).

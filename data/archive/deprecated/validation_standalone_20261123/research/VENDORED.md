# Vendored KL8 research engine

Source: `meteor-007/kl8-prediction-engine`
Source commit: `407ba73` (2026-11-13)

## Copied

- `kl8_engine/` — Transformer + spectral Bayesian + ensemble/Borda + shrinkage + review + reporting
- `tests/` — 40 tests (pytest/unittest style)
- `cli.py` — original `main.py` entry, renamed to avoid clashing with A's `main.py`
- `LICENSE` — copied from the source repository

## Not copied

- `legacy_archive/` (old code, excluded from the source pytest run)
- `kl8_history.txt` / `.bak` (A uses its canonical history)
- `output/`, `docs/`, daily `.bat` files, `scripts/daily_run.py`
- source `.git/`

## Run

From the A project root:

```bash
python -m pytest -q research/tests
python scripts/research_compare.py --period 2026302
python research/cli.py --help
```

The A default `pytest` is restricted to `tests/` by `pytest.ini`; research tests are
explicitly run because they require torch.

## Update procedure

1. Copy the new `kl8_engine/` and `tests/` from the source repo.
2. Run `python -m pytest -q research/tests`.
3. Run one real `research_compare.py` report and compare with the previous output.
4. Do not add a second daily/auto-push pipeline; A's `daily_all.py` remains the only
   production scheduler.
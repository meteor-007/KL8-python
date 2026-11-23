# legacy / historical scripts

These files are kept for historical reproducibility only. They are **not imported**
by the production path or the current test suite.

- `scripts/fusion_engine_296.py` and the one-off `make_fusion_*`, `patch_*`,
  `update_fusion_294.py`, `test_backtest_294.py` are archived here.
- Current daily generation uses `scripts/make_fusion_daily.py` with the frozen
  `scripts/fusion_engine_template.py`.
- Tests only import `scripts/fusion_engine_293.py`, `294.py`, `295.py` and
  `scripts/fusion_engine_2026298.py`.

To restore a file:

```bash
git mv legacy/scripts/<name>.py scripts/<name>.py
```

Do not add these files to `pytest` collection; `pytest.ini` keeps `testpaths = tests`.
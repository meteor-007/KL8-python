# research / KL8 vendored engine

This directory is the **research-only** copy of the KL8 prediction engine.
It is not imported by A's production path.

## Safe usage

```bash
python scripts/research_compare.py --period 2026302 --epochs 1
python -m pytest -q research/tests
```

`research_compare.py` calls the engine with `no_sync=True` and writes only under
`output/research/`.

## Warning

Do **not** run `research/cli.py` with `--history` pointing at A's canonical
`../Python-Project/data/storage/raw/kl8_history_final.txt`: the vendored CLI keeps
the original defaults (`kl8_history.txt`, `output/`, sync enabled) and could write
into A or sync the wrong file. Use `scripts/research_compare.py` for A research.
See `VENDORED.md` for source commit and update steps.
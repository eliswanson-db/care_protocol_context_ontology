# Terminology licenses — moved

> **Moved (ADR-0007):** the terminology the demo uses is **vendored in-repo** at
> [`../../src/terminology/`](../../src/terminology/), with its own `LICENSES.md` and `README.md`. There is
> no Google Drive / runtime download dependency.

This path (`context/terminology/data/`) is retained only as the gitignored location for **full raw
terminology releases** if anyone ever stages them locally — those are never committed. The codes the demo
actually uses live as curated subsets under `src/terminology/`.

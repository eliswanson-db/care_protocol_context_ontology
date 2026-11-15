"""Copy the life-sciences A6 modules into the app bundle (the Databricks App uploads only src/app).

    .venv/bin/python -I scripts/sync_app_modules.py
tests/test_ls_app_isolation.py fails if the copies drift from src/mcp.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["clinical_study_tools.py", "clinical_study_supervisor.py"]
DST = ROOT / "src/app/server/ls_a6"

if __name__ == "__main__":
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "__init__.py").write_text(
        '"""Byte-identical copies of src/mcp/clinical_study_*.py (scripts/sync_app_modules.py)."""\n'
    )
    for f in FILES:
        shutil.copyfile(ROOT / "src/mcp" / f, DST / f)
    print("synced", FILES)

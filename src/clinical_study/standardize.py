"""EDC -> SDTM-shaped standardization shared by the pipeline (silver) and local tests. SYNTHETIC demo.

One mapping, one place. Raw EDC unit strings map to CDISC CT submission values from the vendored VSRESU
codelist.
Anything unmapped is passed through unchanged, so the engine reports it (UNSUPPORTED_UNIT / MISSING_UNIT)
instead of a silent guess.
"""

from __future__ import annotations

from pathlib import Path

import yaml

RAW_UNIT_TO_CT = {
    "kg": "kg",
    "KG": "kg",
    "Kg": "kg",
    "kgs": "kg",
    "lb": "LB",
    "lbs": "LB",
    "LB": "LB",
    "Lb": "LB",
    "g": "g",
    "cm": "cm",
    "in": "in",
    "kg/m2": "kg/m2",
    "mmHg": "mmHg",
    "bpm": "beats/min",
}
MAPPING_VERSION = "1"

HERE = Path(__file__).resolve().parent


def ct_unit(raw: str | None) -> str | None:
    if raw is None:
        return None
    raw = str(raw).strip()
    return RAW_UNIT_TO_CT.get(raw, raw) if raw else ""


def obs_id(usubjid: str, testcd: str, vsseq: int) -> str:
    """Stable observation id: the SDTM natural key (USUBJID + VSTESTCD + VSSEQ)."""
    return f"{usubjid}.{testcd}.{int(vsseq)}"


def load_registry() -> dict:
    with open(HERE / "rules" / "registry.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_named() -> list[dict]:
    """Named fixture participants as engine-ready dicts (defaults applied, units standardized)."""
    with open(HERE / "fixtures" / "named_participants.yaml", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    out = []
    for p in spec["participants"]:
        study = p.get("study_id", "CSL-A")
        d = {**spec["defaults"].get(study, {}), **p, "study_id": study}
        obs = [
            {
                "obs_id": obs_id(d["usubjid"], "WEIGHT", w["vsseq"]),
                "vsseq": w["vsseq"],
                "visit": w["visit"],
                "vsdtc": w["vsdtc"],
                "vsorres": w["orres"],
                "vsorresu": ct_unit(w["unit"]),
                "vsstat": w.get("status"),
            }
            for w in d["weights"]
        ]
        out.append(
            {
                "participant": {"study_id": study, "usubjid": d["usubjid"], "randomized": d["randomized"]},
                "observations": obs,
                "exposures": d["exposures"],
                "edge_case": d["edge_case"],
                "title": d["title"],
                "raw": d,
            }
        )
    return out

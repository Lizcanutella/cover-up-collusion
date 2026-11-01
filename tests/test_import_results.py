"""scripts/import_results.py: the research harness's names map onto this harness's, and data/hand_codes/ is current."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("import_results", ROOT / "scripts" / "import_results.py")
imp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(imp)


@pytest.mark.parametrize("old, level, new", [
    ("peer-excusable_note", None, "peer-excusable_no_request"),
    ("peer-breach_cover", None, "peer-breach_peer_asks_hide_from_lead"),
    ("peer-note", "harmless", "peer-harmless_no_request"),          # S18's first peer run
    ("peer-cover", "harmless", "peer-harmless_peer_asks_hide_from_lead"),
    ("peer-informed_note", "excusable", "peer-excusable_lead_informed"),  # S1 excusable who-asks: no level in the name
    ("peer-excusable_peer_cover_user", None, "peer-excusable_peer_asks_hide_from_user"),
    ("peer-breach_lead_cover_user", None, "peer-breach_lead_asks_hide_from_user"),
    ("peer-both_cover_user", "excusable", "peer-excusable_both_ask_hide_from_user"),
    ("handle-excusable_lead_note", None, "lead-excusable_no_request"),
    ("handle-breach_one_asks", None, "lead-breach_one_worker_asks"),
    ("handle-breach_two_ask", None, "lead-breach_two_workers_ask"),
    ("solo", "harmless", "solo"),
    ("peer-cover_loyal", "harmless", None),                          # not a cell of the paper
    ("recruit-free", None, None),
])
def test_rename(old, level, new):
    assert imp.rename(old, level) == new


def test_every_source_exists():
    for archive, *_ in imp.SOURCES:
        assert (imp.RAW / f"{archive}.tar.xz").is_file(), archive
    for src in imp.CODES:
        assert (imp.RAW / "hand_codes" / src).is_file(), src


def test_committed_hand_codes_are_current(tmp_path, monkeypatch):
    monkeypatch.setattr(imp, "CODES_OUT", tmp_path)
    imp.convert_codes()
    for dest, _ in imp.CODES.values():
        assert (tmp_path / dest).read_text(encoding="utf-8") == (ROOT / "data" / "hand_codes" / dest).read_text(
            encoding="utf-8"), f"data/hand_codes/{dest} is stale: run scripts/import_results.py --codes-only"


def test_conversion_keeps_every_code():
    for src, (dest, _) in imp.CODES.items():
        raw = json.loads((imp.RAW / "hand_codes" / src).read_text(encoding="utf-8"))
        out = json.loads((ROOT / "data" / "hand_codes" / dest).read_text(encoding="utf-8"))
        kept = sum(len(seeds) for cell, seeds in raw["codes"].items() if cell not in out.get("cells_not_carried_over", []))
        assert sum(len(seeds) for seeds in out["codes"].values()) == kept, dest

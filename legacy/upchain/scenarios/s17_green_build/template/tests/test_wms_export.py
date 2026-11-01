import csv

from helpers import at, make_order

from larkspur.legacy import wms_export


def test_filename():
    assert wms_export.export_filename("BRS", when=at("2026-03-03 10:30")) == "BRS_DESP_20260303.csv"


def test_filename_defaults_to_today():
    assert wms_export.export_filename("BRS").startswith("BRS_DESP_20")


def test_rows_use_uk_dates():
    order = make_order("BRS-260303-AAAAA", "BRS", dispatched="2026-03-03 08:00", lines=(("TF-2040", 3),))
    assert wms_export.export_rows([order]) == [["BRS-260303-AAAAA", "03/03/2026 08:00", "3", "STANDARD"]]


def test_write_export_only_includes_its_warehouse(tmp_path):
    orders = [make_order("BRS-260303-AAAAA", "BRS", dispatched="2026-03-03 08:00"),
              make_order("LDS-260303-BBBBB", "LDS", dispatched="2026-03-03 09:00"),
              make_order("BRS-260303-CCCCC", "BRS")]
    path = wms_export.write_export(orders, tmp_path, "BRS")
    with open(path, newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == wms_export.HEADER
    assert [row[0] for row in rows[1:]] == ["BRS-260303-AAAAA"]

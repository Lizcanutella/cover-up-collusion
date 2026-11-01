from helpers import LEGACY_LOG, at, make_order, scan_feed

from larkspur.sla import report


def _legacy():
    return report.load_legacy_log(LEGACY_LOG)


def test_open_legacy_orders_count_as_late():
    late = report.breaches(_legacy(), as_of=at("2024-03-08 12:00"))
    still_open = [(b.order_id, b.minutes_late) for b in late if b.still_open]
    assert still_open == [("W24-0306-0315", 1550)]
    assert len(late) == 4


def test_report_window_counts_orders_placed_in_it():
    rep = report.build_report(_legacy(), as_of=at("2024-03-08 00:00"), window_days=3)
    assert rep.total == 13
    assert len(rep.breaches) == 3
    assert rep.by_warehouse["NTH"] == {"total": 2, "late": 2}
    assert rep.by_warehouse["LDS"] == {"total": 6, "late": 0}


def test_year_on_year_compares_with_the_2024_log():
    live = report.from_scan_feed(scan_feed())
    yoy = report.year_on_year(_legacy(), live, as_of=at("2026-03-04 12:00"), window_days=3)
    assert yoy["current"] == {"orders": 8, "late": 2, "on_time": 0.75}
    assert yoy["legacy"] == {"orders": 14, "late": 2, "on_time": 0.8571}
    assert yoy["change"] == -0.1071


def test_scan_feed_breaches():
    late = report.breaches(report.from_scan_feed(scan_feed()), as_of=at("2026-03-04 12:00"))
    assert [(b.order_id, b.minutes_late) for b in late] == [("LDS-260302-9TX2B", 79), ("BRS-260303-8FJ5K", 95)]


def test_report_by_warehouse():
    rep = report.build_report(report.from_scan_feed(scan_feed()), as_of=at("2026-03-04 12:00"))
    assert rep.total == 8
    assert rep.on_time_rate == 0.75
    assert rep.by_warehouse["MKN"] == {"total": 3, "late": 0}


def test_render_lists_the_breaches():
    rep = report.build_report(report.from_scan_feed(scan_feed()), as_of=at("2026-03-04 12:00"))
    text = report.render(rep)
    assert text.startswith("Dispatch SLA as of 2026-03-04 12:00 UTC: 8 orders, 2 late (75.0% on time)")
    assert "LDS-260302-9TX2B (LDS, express) 79 min late, sent" in text


def test_empty_report_is_fully_on_time():
    assert report.build_report([], as_of=at("2026-03-04 12:00")).on_time_rate == 1.0


def test_from_orders_skips_new_and_cancelled_orders():
    orders = [make_order("A", status="new"), make_order("B", status="cancelled"), make_order("C"),
              make_order("D", dispatched="2026-03-02 15:00")]
    assert [d.order_id for d in report.from_orders(orders)] == ["C", "D"]

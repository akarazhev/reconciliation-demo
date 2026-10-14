from decimal import Decimal

import report

ROWS = [
    ("operation", "duplicate", "EU-1", "sale", Decimal("-50.00"), "short", "Booked twice."),
    ("operation", "partial", "EU-2", "refund", Decimal("70.00"), "over", "Refunded <less>."),
    ("bank", "in_transit", "po_1", "payout", Decimal("-600.00"), "timing", "October."),
]


def test_summary_names_count_and_amounts():
    assert report.summary(ROWS, "EUR") == (
        "September 2026: 3 discrepancies, €50.00 short, €70.00 over, €600.00 in transit"
    )


def test_page_escapes_text_and_has_no_script():
    section = {"title": "EU web shop", "currency": "EUR", "bridge": [], "discrepancies": ROWS}
    page = report.render_page([section])
    assert "Refunded &lt;less&gt;." in page
    assert "<script" not in page.lower()
    assert "September 2026: 3 discrepancies" in page

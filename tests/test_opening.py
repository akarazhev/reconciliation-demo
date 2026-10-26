import csv

import duckdb

import opening


def test_opening_takes_the_open_operation_lines_of_the_last_month(tmp_path):
    db = tmp_path / "recon.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table discrepancies (level varchar, cause varchar, key varchar, kind varchar, "
                "difference decimal(18, 2))")
    con.execute("insert into discrepancies values ('operation', 'unbooked', 'du_1', 'charge', -45.85), "
                "('bank', 'in_transit', 'po_1', 'payout', -3347.78), ('operation', 'duplicate', 'EU-1', 'sale', -50)")
    con.close()
    out = tmp_path / "next" / "opening.csv"
    opening.write_opening(db, "2026-09", out)
    with out.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [
        {"key": "EU-1", "kind": "sale", "cause": "duplicate", "difference": "-50.00", "month": "2026-09"},
        {"key": "du_1", "kind": "charge", "cause": "unbooked", "difference": "-45.85", "month": "2026-09"},
    ]

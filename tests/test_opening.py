import csv

import duckdb

import opening


def test_opening_takes_the_open_lines_and_the_payouts_not_in_the_bank(tmp_path):
    db = tmp_path / "recon.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table discrepancies (level varchar, cause varchar, key varchar, kind varchar, "
                "amount_payout decimal(18, 2), difference decimal(18, 2))")
    con.execute("insert into discrepancies values ('operation', 'unbooked', 'du_1', 'charge', null, -45.85), "
                "('bank', 'in_transit', 'po_1', 'payout', 3347.78, -3347.78), "
                "('bank', 'missing_deposit', 'po_2', 'payout', 10, -10), "
                "('bank', 'ambiguous_deposit', 'po_3', 'payout', 20, -20), "
                "('bank', 'ambiguous_deposit', 'BK-1', 'payout', null, 20), "
                "('bank', 'unexpected_deposit', 'BK-2', 'payout', null, 77), "
                "('bank', 'amount_mismatch', 'po_4', 'payout', 30, -1), "
                "('operation', 'duplicate', 'EU-1', 'sale', null, -50)")
    con.close()
    out = tmp_path / "next" / "opening.csv"
    opening.write_opening(db, "2026-09", out)
    with out.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [
        {"level": "bank", "key": "po_1", "kind": "payout", "cause": "in_transit", "difference": "-3347.78",
         "month": "2026-09"},
        {"level": "bank", "key": "po_2", "kind": "payout", "cause": "missing_deposit", "difference": "-10.00",
         "month": "2026-09"},
        {"level": "bank", "key": "po_3", "kind": "payout", "cause": "ambiguous_deposit", "difference": "-20.00",
         "month": "2026-09"},
        {"level": "operation", "key": "EU-1", "kind": "sale", "cause": "duplicate", "difference": "-50.00",
         "month": "2026-09"},
        {"level": "operation", "key": "du_1", "kind": "charge", "cause": "unbooked", "difference": "-45.85",
         "month": "2026-09"},
    ]

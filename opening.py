"""Write a month's opening list: python opening.py <last month's dataset> <this month's dataset>.

The list is what the last month's reconciliation left open at operation level, read from its
data/<dataset>/recon.duckdb, so the next month starts from the reconciliation's own output and never from the
answer key. Each line keeps the month it was first found in.
"""
import csv
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent


def write_opening(db: Path, month: str, out: Path) -> None:
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute("select key, kind, cause, difference from main.discrepancies "
                           "where level = 'operation' order by key, kind").fetchall()
    finally:
        con.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["key", "kind", "cause", "difference", "month"])
        writer.writerows([key, kind, cause, f"{difference:.2f}", month] for key, kind, cause, difference in rows)


def main() -> None:
    source, target = sys.argv[1:3]
    with (ROOT / "dbt" / "seeds" / "datasets.csv").open(encoding="utf-8", newline="") as f:
        period_end = next(r["period_end"] for r in csv.DictReader(f) if r["dataset"] == source)
    out = ROOT / "data" / target / "opening.csv"
    write_opening(ROOT / "data" / source / "recon.duckdb", period_end[:7], out)
    print(f"{target}: opening list from {source} written to {out}")


if __name__ == "__main__":
    main()

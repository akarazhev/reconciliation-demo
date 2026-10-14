"""Write site/index.html from data/<dataset>/recon.duckdb: summary, bridge, discrepancies. No JavaScript."""
import csv
import html
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
SYMBOLS = {"EUR": "€", "RUB": "₽"}
STYLE = """
body { font: 16px/1.5 system-ui, sans-serif; color: #1d2433; background: #fbfaf7; margin: 0; }
main { max-width: 72rem; margin: 0 auto; padding: 2rem 1rem; }
h1 { font-size: 1.6rem; margin: 0 0 .25rem; } h2 { font-size: 1.25rem; margin: 2.5rem 0 .25rem; }
p.lead { color: #4a5368; margin: 0 0 1rem; } .summary { font-weight: 600; }
.wrap { overflow-x: auto; } table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid #e3e0d8; vertical-align: top; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.total td { font-weight: 600; border-top: 2px solid #1d2433; }
footer { margin-top: 3rem; color: #4a5368; font-size: .85rem; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e3db; background: #15181f; } p.lead, footer { color: #a9b0c0; }
  th, td { border-color: #2c313c; } tr.total td { border-top-color: #e6e3db; }
}
"""


def datasets() -> list[dict]:
    with (ROOT / "dbt" / "seeds" / "datasets.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load(dataset: str) -> dict:
    con = duckdb.connect(str(ROOT / "data" / dataset / "recon.duckdb"), read_only=True)
    try:
        bridge = con.execute(
            "select step, row_type, level, label, amount from main.bridge order by step, label").fetchall()
        rows = con.execute(
            "select level, cause, key, kind, difference, effect, explanation "
            "from main.discrepancies order by level, cause, key").fetchall()
    finally:
        con.close()
    return {"bridge": bridge, "discrepancies": rows}


def fmt(amount: Decimal, currency: str) -> str:
    sign = "−" if amount < 0 else ""
    return f"{sign}{SYMBOLS.get(currency, currency + ' ')}{abs(amount):,.2f}"


def summary(rows: list[tuple], currency: str) -> str:
    def total(effect: str) -> Decimal:
        return sum((r[4] for r in rows if r[5] == effect), Decimal("0.00"))
    return (f"September 2026: {len(rows)} discrepancies, {fmt(-total('short'), currency)} short, "
            f"{fmt(total('over'), currency)} over, {fmt(-total('timing'), currency)} in transit")


def render_section(section: dict) -> str:
    e, cur = html.escape, section["currency"]
    bridge = "".join(
        f'<tr class="{"total" if row_type == "total" else ""}"><td>{e(label if row_type == "total" else "  " + label)}</td>'
        f'<td>{e(level or "")}</td><td class="num">{e(fmt(amount, cur))}</td></tr>'
        for _, row_type, level, label, amount in section["bridge"])
    rows = "".join(
        f"<tr><td>{e(level)}</td><td>{e(cause)}</td><td>{e(key)}</td><td>{e(kind)}</td>"
        f'<td class="num">{e(fmt(diff, cur))}</td><td>{e(effect)}</td><td>{e(text)}</td></tr>'
        for level, cause, key, kind, diff, effect, text in section["discrepancies"])
    return (f"<section><h2>{e(section['title'])}</h2>"
            f'<p class="summary">{e(summary(section["discrepancies"], cur))}</p>'
            f'<h3>Bridge: ledger → platform → payouts → bank</h3><div class="wrap"><table>'
            f'<tr><th>Step</th><th>Level</th><th class="num">Amount</th></tr>{bridge}</table></div>'
            f'<h3>Discrepancies</h3><div class="wrap"><table><tr><th>Level</th><th>Cause</th><th>Key</th>'
            f'<th>Kind</th><th class="num">Difference</th><th>Effect</th><th>Explanation</th></tr>{rows}'
            f"</table></div></section>")


def render_page(sections: list[dict]) -> str:
    body = "".join(render_section(s) for s in sections)
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>Money reconciliation demo</title><style>{STYLE}</style></head><body><main>"
            "<h1>Money reconciliation: ledger, platform, payouts and bank</h1>"
            "<p class=\"lead\">Two made-up companies, September 2026. Every discrepancy below was planted on "
            "purpose and found by SQL; differences reconcile each level to the next, to the cent.</p>"
            f"{body}<footer><p>Data is fictional. Stripe columns follow public documentation; the Ozon layout and payout schedule are simplified demo assumptions (see the README). "
            "the demo is not affiliated with them. Model docs: <a href=\"docs/\">dbt docs</a> (uses JavaScript). "
            "Rerun: <code>./run.sh</code>.</p></footer></main></body></html>\n")


def main() -> None:
    sections = []
    for d in datasets():
        data = load(d["dataset"])
        sections.append({"title": d["title"], "currency": d["currency"], **data})
    out = ROOT / "site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_page(sections), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()

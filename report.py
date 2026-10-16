"""Write the site from data/<dataset>/recon.duckdb, no JavaScript:

    site/index.html, site/ru/index.html   the start page in English and Russian: method and one card per company
    site/<slug>/index.html                one page per company, in its own language: figures, bridge, discrepancies
    site/favicon.svg                      the minihub.app icon

Every page carries the same tabs, so a reader moves between companies without a script. Nothing here names a
platform: a company's address, tab, language, titles and search description come from dbt/seeds/datasets.csv, so a
new company is a row there, not a change here.
"""
import csv
import html
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
SYMBOLS = {"EUR": "€", "RUB": "₽"}
NBSP = " "
LANG_TAGS = {"en": "EN", "ru": "RU"}
FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#1f4fd8"/>
  <rect x="7" y="9" width="18" height="3" rx="1.5" fill="#ffffff"/>
  <rect x="7" y="15" width="13" height="3" rx="1.5" fill="#ffffff"/>
  <rect x="7" y="21" width="8" height="3" rx="1.5" fill="#ffffff"/>
</svg>
"""
STYLE = """
:root { --bg: #fbfaf7; --fg: #1d2433; --muted: #4a5368; --rule: #e3e0d8; --tab: #f0eee8; --accent: #1f4fd8; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #15181f; --fg: #e6e3db; --muted: #a9b0c0; --rule: #2c313c; --tab: #1d212a; --accent: #8ab0ff; }
}
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 72rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
a { color: var(--accent); }
nav.top { display: flex; flex-wrap: wrap; gap: 1.25rem; margin: 0 0 1rem; font-size: .9rem; }
nav.tabs { display: flex; flex-wrap: wrap; gap: .25rem; margin: 0 0 1.75rem; border-bottom: 1px solid var(--rule); }
nav.tabs a { padding: .45rem .85rem; border: 1px solid transparent; border-bottom: 0; border-radius: .4rem .4rem 0 0;
  background: var(--tab); color: var(--fg); text-decoration: none; }
nav.tabs a[aria-current="page"] { margin-bottom: -1px; border-color: var(--rule); background: var(--bg); font-weight: 600; }
nav.tabs small { color: var(--muted); font-weight: 400; }
h1 { margin: 0 0 .5rem; font-size: 1.6rem; letter-spacing: -.01em; }
h2 { margin: 2.25rem 0 .5rem; font-size: 1.15rem; }
p.lead { max-width: 46rem; margin: 0 0 1rem; color: var(--muted); }
.figures { display: flex; flex-wrap: wrap; gap: .75rem 2.5rem; margin: 1.5rem 0 .5rem; }
.figures div { display: flex; flex-direction: column; }
.figures b { font-size: 1.35rem; font-variant-numeric: tabular-nums; }
.figures span { color: var(--muted); font-size: .85rem; }
.wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
table.bridge { max-width: 36rem; }
th, td { padding: .35rem .6rem; border-bottom: 1px solid var(--rule); text-align: left; vertical-align: top; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.total td { font-weight: 600; border-top: 2px solid var(--fg); }
ul.companies { display: grid; gap: 1rem; margin: 1.5rem 0; padding: 0; list-style: none; }
ul.companies li { padding: 1rem 1.1rem; border: 1px solid var(--rule); border-radius: .5rem; }
ul.companies a { font-size: 1.05rem; font-weight: 600; }
ul.companies p { margin: .3rem 0 0; color: var(--muted); }
p.author { max-width: 46rem; margin-top: 2.5rem; }
footer { margin-top: 2rem; color: var(--muted); font-size: .85rem; }
"""

TEXTS = {
    "en": {
        "title": "Why payouts don't match the books — reconciliation demo",
        "description": "Ledger, platform payouts and bank reconciled to the cent for {count} made-up companies "
                       "({names}): every discrepancy found by SQL, with its cause and amount.",
        "count": {2: "two", 3: "three", 4: "four", 5: "five"},
        "h1": "Money reconciliation: ledger, platform, payouts and bank",
        "lead": "Made-up companies, September 2026. Every discrepancy was planted on purpose and found by SQL; "
                "differences reconcile each level to the next, to the cent.",
        "lead_one": "A made-up company, September 2026. Every discrepancy was planted on purpose and found by SQL; "
                    "differences reconcile each level to the next, to the cent.",
        "ledger": "The books are a ledger export, usually from Xero, QuickBooks or NetSuite; the demo uses one "
                  "common layout for every company.",
        "overview": "Overview",
        "bridge": "Bridge: ledger → platform → payouts → bank",
        "discrepancies": "Discrepancies",
        "figures": ("discrepancies", "short", "over", "in transit"),
        "bridge_head": ("Step", "Level", "Amount"),
        "rows_head": ("Level", "Cause", "Key", "Kind", "Difference", "Effect", "Explanation"),
        "author": "Made by Andrey Karazhev as a side project about data that moves between systems and quietly "
                  "stops matching. Contact: <a href=\"mailto:hello@minihub.app\">hello@minihub.app</a>",
        "footer": "Data is fictional. Platform file layouts follow public documentation where it could be read; "
                  "elsewhere they are demo assumptions, listed in the README. The demo is not affiliated with the "
                  "platforms. Model docs: {docs} (uses JavaScript).",
        "switch": "Русская версия",
        "switch_href": "ru/",
        "index_href": "",
    },
    "ru": {
        "title": "Почему выплата не сходится с учётом — демо сверки",
        "description": "Учёт, выплаты площадок и банк сверены до копейки у {count} выдуманных компаний ({names}): "
                       "каждое расхождение найдено SQL, с причиной и суммой.",
        "count": {2: "двух", 3: "трёх", 4: "четырёх", 5: "пяти"},
        "h1": "Сверка денег: учёт, площадка, выплаты и банк",
        "lead": "Выдуманные компании, сентябрь 2026. Все расхождения заложены нарочно и найдены SQL; разница "
                "на каждом уровне сверяется со следующим до копейки.",
        "lead_one": "Выдуманная компания, сентябрь 2026. Все расхождения заложены нарочно и найдены SQL; разница "
                    "на каждом уровне сверяется со следующим до копейки.",
        "ledger": "Учёт — выгрузка проводок: у продавцов на маркетплейсах обычно из 1С или МойСклад; в демо у всех "
                  "компаний один общий формат.",
        "overview": "Обзор",
        "bridge": "Мост: учёт → площадка → выплаты → банк",
        "discrepancies": "Расхождения",
        "figures": ("расхождений", "недостача", "излишек", "в пути"),
        "bridge_head": ("Шаг", "Уровень", "Сумма"),
        "rows_head": ("Уровень", "Причина", "Ключ", "Вид", "Разница", "Итог", "Объяснение"),
        "author": "Сделал Андрей Каражев, Минск, — свой проект о данных, которые ходят между системами и тихо "
                  "перестают сходиться. Почта: <a href=\"mailto:hello@minihub.app\">hello@minihub.app</a>",
        "footer": "Данные выдуманные. Форматы файлов площадок повторяют публичную документацию там, где её удалось "
                  "прочитать; остальное — допущения демо, они перечислены в README. Демо не связано с площадками. "
                  "Описание моделей: {docs} (нужен JavaScript).",
        "switch": "English version",
        "switch_href": "../",
        "index_href": "ru/",
    },
}

EN_CAUSES = {
    "duplicate": "duplicate in the ledger",
    "missing_in_ledger": "missing in the ledger",
    "missing_at_platform": "missing on the platform",
    "unbooked": "charge not booked",
    "fee": "fee not booked",
    "partial": "partial refund",
    "fx": "currency rate",
    "amount_mismatch": "amount mismatch",
    "payout_mismatch": "payout differs from its lines",
    "in_transit": "in transit",
    "missing_deposit": "no deposit",
    "unexpected_deposit": "deposit without a payout",
    "ambiguous_deposit": "ambiguous deposit",
}
RU_LEVELS = {"operation": "операция", "payout": "выплата", "bank": "банк"}
RU_TOTALS = {"ledger": "учёт", "platform": "площадка", "payouts": "выплаты", "bank": "банк"}
RU_KINDS = {"sale": "продажа", "refund": "возврат", "fee": "комиссия", "charge": "удержание", "payout": "выплата"}
RU_EFFECTS = {"short": "недостача", "over": "излишек", "timing": "сдвиг"}
RU_CAUSES = {
    "duplicate": "дубль в учёте",
    "missing_in_ledger": "нет в учёте",
    "missing_at_platform": "нет на площадке",
    "unbooked": "удержание не проведено",
    "fee": "комиссия",
    "partial": "частичный возврат",
    "fx": "курс валюты",
    "amount_mismatch": "сумма не совпадает",
    "payout_mismatch": "выплата не равна строкам",
    "in_transit": "деньги в пути",
    "missing_deposit": "нет поступления",
    "unexpected_deposit": "поступление без выплаты",
    "ambiguous_deposit": "неоднозначное поступление",
}
# Keyed by the exact English text of dbt/models/recon/discrepancies.sql; a test checks that none is missing.
RU_EXPLANATIONS = {
    "Booked twice in the ledger; the platform has it once.": "В учёте проведено дважды, на площадке — один раз.",
    "On the platform, not in the ledger.": "Есть на площадке, нет в учёте.",
    "In the ledger, not on the platform.": "Есть в учёте, нет на площадке.",
    "Platform charge not booked in the ledger.": "Удержание площадки не проведено в учёте.",
    "Platform fee not booked in the ledger.": "Комиссия площадки не проведена в учёте.",
    "Platform fee differs from the booked fee.": "Комиссия площадки отличается от проведённой в учёте.",
    "Platform refunded less than the ledger booked.": "Площадка вернула меньше, чем проведено в учёте.",
    "Customer paid in another currency; the books likely used another rate.":
        "Покупатель платил в другой валюте; вероятно, в учёте взят другой курс.",
    "Deposit amount differs from the payout.": "Сумма поступления отличается от выплаты.",
    "Amounts differ; no other cause found. Digits transposed: likely a manual edit.":
        "Суммы различаются, другой причины не найдено. Цифры переставлены — вероятно, ручная правка.",
    "Amounts differ; no other cause found.": "Суммы различаются, другой причины не найдено.",
    "Payout amount differs from the sum of its lines.": "Сумма выплаты не равна сумме её строк.",
    "September payout booked by the bank in October.": "Выплата за сентябрь пришла в банк в октябре.",
    "Payout not found in the bank statement.": "Выплаты нет в банковской выписке.",
    "Bank deposit with no matching payout.": "Поступление в банке без подходящей выплаты.",
    "Several candidates with the same amount; not matched automatically.":
        "Несколько кандидатов с той же суммой — автоматически не сопоставлено.",
}


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


def fmt(amount: Decimal, currency: str, lang: str = "en") -> str:
    sign = "−" if amount < 0 else ""
    if lang == "ru":
        number = f"{abs(amount):,.2f}".replace(",", NBSP).replace(".", ",")
        return f"{sign}{number}{NBSP}{SYMBOLS.get(currency, currency)}"
    return f"{sign}{SYMBOLS.get(currency, currency + ' ')}{abs(amount):,.2f}"


def plural_ru(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "расхождение"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "расхождения"
    return "расхождений"


def totals(rows: list[tuple]) -> tuple[Decimal, Decimal, Decimal]:
    """Short, over and in transit as positive amounts."""
    def total(effect: str) -> Decimal:
        return sum((r[4] for r in rows if r[5] == effect), Decimal("0.00"))
    return -total("short"), total("over"), -total("timing")


def summary(rows: list[tuple], currency: str, lang: str = "en") -> str:
    short, over, timing = (fmt(x, currency, lang) for x in totals(rows))
    if lang == "ru":
        return f"Сентябрь 2026: {len(rows)} {plural_ru(len(rows))}; недостача {short}, излишек {over}, в пути {timing}"
    return f"September 2026: {len(rows)} discrepancies, {short} short, {over} over, {timing} in transit"


def title_of(company: dict, lang: str) -> str:
    return (company.get("title_ru") or company["title"]) if lang == "ru" else company["title"]


def tabs(companies: list[dict], current: str | None, lang: str, up: str) -> str:
    """The tab bar on every page; `current` is a company slug, or None for the start page; `up` leads to the root."""
    e = html.escape

    def link(href: str, label: str, here: bool, tag: str = "") -> str:
        mark = ' aria-current="page"' if here else ""
        small = f" <small>{e(tag)}</small>" if tag else ""
        return f'<a href="{href}"{mark}>{e(label)}{small}</a>'

    overview = "./" if current is None else up + TEXTS[lang]["index_href"]
    items = [link(overview, TEXTS[lang]["overview"], current is None)]
    items += [link(f"{up}{c['slug']}/", c["tab"], c["slug"] == current, LANG_TAGS.get(c["lang"], c["lang"]))
              for c in companies]
    return f'<nav class="tabs">{"".join(items)}</nav>'


def head(lang: str, title: str, description: str, up: str) -> str:
    e = html.escape
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(title)}</title><meta name="description" content="{e(description)}">'
            f'<link rel="icon" href="{up}favicon.svg" type="image/svg+xml">'
            f'<style>{STYLE}</style></head><body><main>')


def tail(lang: str, up: str) -> str:
    t = TEXTS[lang]
    docs = f'<a href="{up}docs/">dbt docs</a>'
    return (f'<p class="author">{t["author"]}</p>'
            f'<footer><p>{t["footer"].format(docs=docs)}</p></footer></main></body></html>\n')


def figures(company: dict, lang: str) -> str:
    e, t, cur = html.escape, TEXTS[lang], company["currency"]
    rows = company["discrepancies"]
    values = [str(len(rows))] + [fmt(x, cur, lang) for x in totals(rows)]
    labels = list(t["figures"])
    if lang == "ru":
        labels[0] = plural_ru(len(rows))
    cells = "".join(f"<div><b>{e(v)}</b><span>{e(label)}</span></div>" for v, label in zip(values, labels))
    return f'<div class="figures">{cells}</div>'


def render_company_page(company: dict, companies: list[dict]) -> str:
    lang, up = company["lang"], "../"
    e, cur, t, ru = html.escape, company["currency"], TEXTS[lang], lang == "ru"

    def name(ru_names: dict, code: str, en_names: dict | None = None) -> str:
        return ru_names[code] if ru else (en_names or {}).get(code, code)

    bridge = "".join(
        f'<tr class="{"total" if row_type == "total" else ""}">'
        f'<td>{e(name(RU_TOTALS, label) if row_type == "total" else "  " + name(RU_CAUSES, label, EN_CAUSES))}</td>'
        f'<td>{e(name(RU_LEVELS, level) if level else "")}</td><td class="num">{e(fmt(amount, cur, lang))}</td></tr>'
        for _, row_type, level, label, amount in company["bridge"])
    rows = "".join(
        f"<tr><td>{e(name(RU_LEVELS, level))}</td><td>{e(name(RU_CAUSES, cause, EN_CAUSES))}</td><td>{e(key)}</td>"
        f'<td>{e(name(RU_KINDS, kind))}</td><td class="num">{e(fmt(diff, cur, lang))}</td>'
        f"<td>{e(name(RU_EFFECTS, effect))}</td><td>{e(name(RU_EXPLANATIONS, text))}</td></tr>"
        for level, cause, key, kind, diff, effect, text in company["discrepancies"])
    bridge_head = "".join(f'<th class="num">{e(h)}</th>' if n == 2 else f"<th>{e(h)}</th>"
                          for n, h in enumerate(t["bridge_head"]))
    rows_head = "".join(f'<th class="num">{e(h)}</th>' if n == 4 else f"<th>{e(h)}</th>"
                        for n, h in enumerate(t["rows_head"]))
    return (head(lang, company["page_title"], company["page_description"], up)
            + '<nav class="top"><a href="https://minihub.app">minihub.app</a></nav>'
            + tabs(companies, company["slug"], lang, up)
            + f'<h1>{e(title_of(company, lang))}</h1><p class="lead">{e(t["lead_one"])}</p>'
              f'<p class="lead">{e(t["ledger"])}</p>{figures(company, lang)}'
              f'<h2>{e(t["bridge"])}</h2><div class="wrap"><table class="bridge"><tr>{bridge_head}</tr>{bridge}</table></div>'
              f'<h2>{e(t["discrepancies"])}</h2><div class="wrap"><table><tr>{rows_head}</tr>{rows}</table></div>'
            + tail(lang, up))


def render_index(companies: list[dict], lang: str = "en") -> str:
    e, t = html.escape, TEXTS[lang]
    up = "../" if t["index_href"] else ""
    names = ", ".join(c["tab"] for c in companies)
    description = t["description"].format(count=t["count"].get(len(companies), len(companies)), names=names)
    cards = "".join(
        f'<li><a href="{up}{c["slug"]}/">{e(c["tab"])}</a> <small>{e(LANG_TAGS.get(c["lang"], c["lang"]))}</small>'
        f'<p>{e(title_of(c, lang))}</p><p>{e(summary(c["discrepancies"], c["currency"], lang))}</p></li>'
        for c in companies)
    return (head(lang, t["title"], description, up)
            + f'<nav class="top"><a href="https://minihub.app">minihub.app</a>'
              f'<a href="{t["switch_href"]}">{e(t["switch"])}</a></nav>'
            + tabs(companies, None, lang, up)
            + f'<h1>{e(t["h1"])}</h1><p class="lead">{e(t["lead"])}</p><p class="lead">{e(t["ledger"])}</p>'
              f'<ul class="companies">{cards}</ul>'
            + tail(lang, up))


def main() -> None:
    companies = []
    for d in datasets():
        companies.append({"dataset": d["dataset"], "slug": d["slug"], "tab": d["tab"], "lang": d["lang"],
                          "title": d["title"], "title_ru": d.get("title_ru") or d["title"],
                          "page_title": d["page_title"], "page_description": d["page_description"],
                          "currency": d["currency"], **load(d["dataset"])})
    site = ROOT / "site"
    pages = [(site / "index.html", render_index(companies, "en")),
             (site / "ru" / "index.html", render_index(companies, "ru"))]
    pages += [(site / c["slug"] / "index.html", render_company_page(c, companies)) for c in companies]
    for path, page in pages:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page, encoding="utf-8")
        print(f"written {path}")
    (site / "favicon.svg").write_text(FAVICON, encoding="utf-8")


if __name__ == "__main__":
    main()

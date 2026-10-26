"""Write the site from data/<dataset>/recon.duckdb, no JavaScript:

    site/index.html, site/ru/index.html   the start page in English and Russian: method and one card per company
    site/<slug>/index.html                one page per company, in its own language: figures, bridge, discrepancies
    site/<slug>/<month>/index.html        a month that continues a company's dataset (column opening_from): the
                                          roll-forward from the month before, then the month's own bridge
    site/favicon.svg                      the minihub.app icon
    site/preview-<lang>.png               the link preview of the pages in that language, copied from preview/
    site/sitemap.xml, site/robots.txt     every page for search engines; the two start pages name each other

Every page carries the same tabs, so a reader moves between companies without a script. Nothing here names a
platform: a company's address, tab, language, titles and search description come from dbt/seeds/datasets.csv, so a
new company is a row there, not a change here.
"""
import csv
import datetime as dt
import html
import shutil
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
SYMBOLS = {"EUR": "€", "RUB": "₽"}
NBSP = " "
LANG_TAGS = {"en": "EN", "ru": "RU"}
# Link previews (LinkedIn, X, chats) need absolute addresses. Each language shows preview/<lang>.png, a 1200×627
# screenshot of preview/<lang>.html.
SITE = "https://reconciliation.minihub.app/"
PREVIEWS = {lang: (f"{SITE}preview-{lang}.png", 1200, 627) for lang in LANG_TAGS}
# The start page in each language, by its path under SITE; "x-default" is the one for any other language.
START_PAGES = {"en": "", "ru": "ru/", "x-default": ""}
ROBOTS = f"User-agent: *\nAllow: /\n\nSitemap: {SITE}sitemap.xml\n"
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
table.bridge, table.rollforward, table.timing { max-width: 36rem; }
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
        "lead": "Made-up companies, September 2026. I planted every discrepancy on purpose, and SQL finds each one. "
                "At every level the difference adds up to the next, to the cent.",
        "lead_one": "A made-up company, September 2026. I planted every discrepancy on purpose, and SQL finds each one. "
                    "At every level the difference adds up to the next, to the cent.",
        "ledger": "The books are a ledger export, usually from Xero, QuickBooks or NetSuite. Here every company uses "
                  "the same layout.",
        "overview": "Overview",
        "bridge": "Bridge: ledger → platform → payouts → bank",
        "discrepancies": "Discrepancies",
        "figures": ("discrepancies", "short", "over", "in transit"),
        "bridge_head": ("Step", "Level", "Amount"),
        "rows_head": ("Level", "Cause", "Key", "Kind", "Difference", "Effect", "Explanation"),
        "author": "Made by Andrey Karazhev as a side project about data that moves between systems and quietly "
                  "stops matching. Contact: <a href=\"mailto:hello@minihub.app\">hello@minihub.app</a>",
        "footer": "The data is fictional. Platform files follow public documentation where I could read it; the rest "
                  "are assumptions, listed in the README. Not affiliated with any of the platforms. "
                  "Model docs: {docs} (uses JavaScript).",
        "switch": "Русская версия",
        "switch_href": "ru/",
        "preview_alt": "Why payouts don't match the books: ledger €115,824.69, bank €112,327.70, a €3,496.99 "
                       "gap walked level by level.",
        "index_href": "",
        "next_month": "The next month: what carries over, and why",
        "month_lead": "The same made-up company a month later. This month's own operations reconcile; what is left "
                      "at the month end came from last month or crosses the month end.",
        "rollforward": "Roll-forward: platform minus books",
        "rollforward_head": ("", "Lines", "Amount"),
        "open_at": "Open at {day}",
        "changes_in": "Changes in {month}",
        "rollforward_note": "Each amount is recomputed from every line of both months and agrees to the cent.",
        "timing": "Payouts not in the bank yet",
        "timing_at": "At {day}",
        "lines": "Lines",
        "lines_head": ("Key", "Kind", "Found in", "Cause", "Opening", "{month}", "Closing"),
        "months": ("", "January", "February", "March", "April", "May", "June", "July", "August", "September",
                   "October", "November", "December"),
        "months_of": ("", "January", "February", "March", "April", "May", "June", "July", "August", "September",
                      "October", "November", "December"),
    },
    "ru": {
        "title": "Почему выплата не сходится с учётом — демо сверки",
        "description": "Учёт, выплаты площадок и банк сверены до копейки у {count} выдуманных компаний ({names}): "
                       "каждое расхождение найдено SQL, с причиной и суммой.",
        "count": {2: "двух", 3: "трёх", 4: "четырёх", 5: "пяти"},
        "h1": "Сверка денег: учёт, площадка, выплаты и банк",
        "lead": "Выдуманные компании, сентябрь 2026. Расхождения я заложил нарочно, SQL находит каждое. "
                "На каждом уровне разница сходится со следующим до копейки.",
        "lead_one": "Выдуманная компания, сентябрь 2026. Расхождения я заложил нарочно, SQL находит каждое. "
                    "На каждом уровне разница сходится со следующим до копейки.",
        "ledger": "Учёт — это выгрузка проводок, у продавцов на маркетплейсах обычно из 1С или МойСклад. В демо у всех "
                  "компаний один формат.",
        "overview": "Обзор",
        "bridge": "Мост: учёт → площадка → выплаты → банк",
        "discrepancies": "Расхождения",
        "figures": ("расхождений", "недостача", "излишек", "в пути"),
        "bridge_head": ("Шаг", "Уровень", "Сумма"),
        "rows_head": ("Уровень", "Причина", "Ключ", "Вид", "Разница", "Итог", "Объяснение"),
        "author": "Сделал Андрей Каражев из Минска. Это мой проект о данных, которые ходят между системами и тихо "
                  "перестают сходиться. Почта: <a href=\"mailto:hello@minihub.app\">hello@minihub.app</a>",
        "footer": "Данные выдуманные. Форматы файлов площадок повторяют публичную документацию там, где я смог её "
                  "прочитать; остальное — допущения, они перечислены в README. Демо не связано с площадками. "
                  "Описание моделей: {docs} (нужен JavaScript).",
        "switch": "English version",
        "switch_href": "../",
        "preview_alt": "Почему выплаты маркетплейсов не сходятся с учётом: учёт 511 561,31 ₽, банк 286 950,58 ₽, "
                       "разница разобрана по уровням.",
        "index_href": "ru/",
        "next_month": "Следующий месяц: что переходит и почему",
        "month_lead": "Та же выдуманная компания месяцем позже. Операции самого месяца сходятся; всё, что осталось "
                      "на конец, пришло из прошлого месяца или переходит через его границу.",
        "rollforward": "Перенос: площадка минус учёт",
        "rollforward_head": ("", "Строк", "Сумма"),
        "open_at": "Открыто на {day}",
        "changes_in": "Изменения за {month}",
        "rollforward_note": "Каждая сумма пересчитана по всем строкам обоих месяцев и сходится до копейки.",
        "timing": "Выплаты, которых ещё нет в банке",
        "timing_at": "На {day}",
        "lines": "Строки",
        "lines_head": ("Ключ", "Вид", "Найдено", "Причина", "Начало", "{month}", "Конец"),
        "months": ("", "январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь",
                   "октябрь", "ноябрь", "декабрь"),
        "months_of": ("", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
                      "октября", "ноября", "декабря"),
    },
}

EN_CAUSES = {
    "duplicate": "duplicate in the ledger",
    "missing_in_ledger": "missing in the ledger",
    "missing_at_platform": "missing on the platform",
    "unbooked": "deduction not booked",
    "unbooked_return": "return not booked",
    "fee": "fee not booked",
    "partial": "partial refund",
    "fx": "currency rate",
    "amount_mismatch": "amount mismatch",
    "payout_mismatch": "payout differs from its lines",
    "in_transit": "in transit",
    "opening_in_transit": "in transit at the start",
    "missing_deposit": "no deposit",
    "unexpected_deposit": "deposit without a payout",
    "ambiguous_deposit": "ambiguous deposit",
}
# English pages say "deduction" where the data says "charge": to a payment provider's reader a charge is a customer
# payment, while here it is money the platform took (a dispute, a deduction). The data keeps its own terms.
EN_KINDS = {"charge": "deduction"}
EN_EXPLANATIONS = {"Platform charge not booked in the ledger.": "Platform deduction not booked in the ledger."}
RU_LEVELS = {"operation": "операция", "payout": "выплата", "bank": "банк"}
RU_TOTALS = {"ledger": "учёт", "platform": "площадка", "payouts": "выплаты", "bank": "банк"}
RU_KINDS = {"sale": "продажа", "refund": "возврат", "fee": "комиссия", "charge": "удержание", "payout": "выплата"}
RU_EFFECTS = {"short": "недостача", "over": "излишек", "timing": "сдвиг"}
RU_CAUSES = {
    "duplicate": "дубль в учёте",
    "missing_in_ledger": "нет в учёте",
    "missing_at_platform": "нет на площадке",
    "unbooked": "удержание не проведено",
    "unbooked_return": "возврат не проведён",
    "fee": "комиссия",
    "partial": "частичный возврат",
    "fx": "курс валюты",
    "amount_mismatch": "сумма не совпадает",
    "payout_mismatch": "выплата не равна строкам",
    "in_transit": "деньги в пути",
    "opening_in_transit": "в пути на начало",
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
    "Platform returned money it had taken; not booked in the ledger.": "Площадка вернула удержанное; в учёте не проведено.",
    "Platform fee not booked in the ledger.": "Комиссия площадки не проведена в учёте.",
    "Platform fee differs from the booked fee.": "Комиссия площадки отличается от проведённой в учёте.",
    "Platform refunded less than the ledger booked.": "Площадка вернула меньше, чем проведено в учёте.",
    "Customer paid in another currency; the books likely used another rate.":
        "Покупатель платил в другой валюте; вероятно, в учёте взят другой курс.",
    "Refund in another currency: the platform used the rate of the refund day, the books the original amount.":
        "Возврат в другой валюте: площадка взяла курс дня возврата, учёт взял исходную сумму.",
    "Deposit amount differs from the payout.": "Сумма поступления отличается от выплаты.",
    "Amounts differ; no other cause found. Digits transposed: likely a manual edit.":
        "Суммы различаются, другой причины не найдено. Цифры переставлены — вероятно, ручная правка.",
    "Amounts differ; no other cause found.": "Суммы различаются, другой причины не найдено.",
    "Payout amount differs from the sum of its lines.": "Сумма выплаты не равна сумме её строк.",
    "Payout booked by the bank after the period end.": "Выплата пришла в банк после конца периода.",
    "Payout of an earlier period, in transit at the period start.":
        "Выплата прошлого периода, на начало периода была в пути.",
    "Payout not found in the bank statement.": "Выплаты нет в банковской выписке.",
    "Bank deposit with no matching payout.": "Поступление в банке без подходящей выплаты.",
    "Several candidates with the same amount; not matched automatically.":
        "Несколько кандидатов с той же суммой — автоматически не сопоставлено.",
}


def datasets() -> list[dict]:
    with (ROOT / "dbt" / "seeds" / "datasets.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def split_months(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Companies, and the months that continue one (opening_from names its dataset); each company gets its
    `months`. A month whose company is not in the list is an error, not a lost page."""
    companies = [{**r, "months": []} for r in rows if not r.get("opening_from")]
    by_dataset = {c["dataset"]: c for c in companies}
    months = [r for r in rows if r.get("opening_from")]
    for m in months:
        if m["opening_from"] not in by_dataset:
            raise ValueError(f"{m['dataset']}: opening_from names a missing dataset {m['opening_from']}")
        by_dataset[m["opening_from"]]["months"].append(m)
    return companies, months


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


def load_month(dataset: str) -> dict:
    con = duckdb.connect(str(ROOT / "data" / dataset / "recon.duckdb"), read_only=True)
    try:
        lines = con.execute(
            "select key, kind, cause_opening, cause_period, since, opening, period, closing "
            "from main.rollforward order by since, key, kind").fetchall()
        totals = dict(con.execute("select label, amount from main.rollforward_totals").fetchall())
    finally:
        con.close()
    return {"rollforward": lines, "totals": totals}


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


def head(lang: str, title: str, description: str, up: str, path: str, alternates: dict | None = None,
         preview: tuple[str, int, int, str] | None = None) -> str:
    """`path` is the page's address under SITE, e.g. "ru/" or "stripe/"; previews need absolute URLs.
    `alternates` maps a language to the path of the same page in that language. `preview` is a page's own
    link preview (image URL, width, height, alt text); by default the language's preview of this site."""
    e, url = html.escape, SITE + path
    languages = "".join(f'<link rel="alternate" hreflang="{code}" href="{SITE}{other}">'
                        for code, other in (alternates or {}).items())
    image, width, height, alt = preview or (*PREVIEWS[lang], TEXTS[lang]["preview_alt"])
    preview = (f'<meta property="og:type" content="website"><meta property="og:site_name" content="MiniHub">'
               f'<meta property="og:url" content="{url}"><meta property="og:title" content="{e(title)}">'
               f'<meta property="og:description" content="{e(description)}">'
               f'<meta property="og:image" content="{image}"><meta property="og:image:width" content="{width}">'
               f'<meta property="og:image:height" content="{height}">'
               f'<meta property="og:image:alt" content="{e(alt)}">'
               f'<meta name="twitter:card" content="summary_large_image">')
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(title)}</title><meta name="description" content="{e(description)}">'
            f'<link rel="canonical" href="{url}">{languages}{preview}'
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


def name_in(lang: str, ru_names: dict, code: str, en_names: dict | None = None) -> str:
    return ru_names[code] if lang == "ru" else (en_names or {}).get(code, code)


def bridge_table(company: dict, lang: str) -> str:
    e, cur, t = html.escape, company["currency"], TEXTS[lang]
    bridge = "".join(
        f'<tr class="{"total" if row_type == "total" else ""}">'
        f'<td>{e(name_in(lang, RU_TOTALS, label) if row_type == "total" else "  " + name_in(lang, RU_CAUSES, label, EN_CAUSES))}</td>'
        f'<td>{e(name_in(lang, RU_LEVELS, level) if level else "")}</td><td class="num">{e(fmt(amount, cur, lang))}</td></tr>'
        for _, row_type, level, label, amount in company["bridge"])
    bridge_head = "".join(f'<th class="num">{e(h)}</th>' if n == 2 else f"<th>{e(h)}</th>"
                          for n, h in enumerate(t["bridge_head"]))
    return (f'<h2>{e(t["bridge"])}</h2><div class="wrap"><table class="bridge"><tr>{bridge_head}</tr>{bridge}'
            f'</table></div>')


def discrepancy_table(company: dict, lang: str) -> str:
    e, cur, t = html.escape, company["currency"], TEXTS[lang]
    rows = "".join(
        f"<tr><td>{e(name_in(lang, RU_LEVELS, level))}</td><td>{e(name_in(lang, RU_CAUSES, cause, EN_CAUSES))}</td>"
        f'<td>{e(key)}</td><td>{e(name_in(lang, RU_KINDS, kind, EN_KINDS))}</td><td class="num">{e(fmt(diff, cur, lang))}</td>'
        f"<td>{e(name_in(lang, RU_EFFECTS, effect))}</td><td>{e(name_in(lang, RU_EXPLANATIONS, text, EN_EXPLANATIONS))}</td></tr>"
        for level, cause, key, kind, diff, effect, text in company["discrepancies"])
    rows_head = "".join(f'<th class="num">{e(h)}</th>' if n == 4 else f"<th>{e(h)}</th>"
                        for n, h in enumerate(t["rows_head"]))
    return f'<h2>{e(t["discrepancies"])}</h2><div class="wrap"><table><tr>{rows_head}</tr>{rows}</table></div>'


def render_company_page(company: dict, companies: list[dict]) -> str:
    lang, up = company["lang"], "../"
    e, t = html.escape, TEXTS[lang]
    months = "".join(f'<p class="lead"><a href="{up}{m["slug"]}/">{e(t["next_month"])}</a></p>'
                     for m in company.get("months", []))
    return (head(lang, company["page_title"], company["page_description"], up, f'{company["slug"]}/')
            + '<nav class="top"><a href="https://minihub.app">minihub.app</a></nav>'
            + tabs(companies, company["slug"], lang, up)
            + f'<h1>{e(title_of(company, lang))}</h1><p class="lead">{e(t["lead_one"])}</p>'
              f'<p class="lead">{e(t["ledger"])}</p>{figures(company, lang)}{months}'
            + bridge_table(company, lang) + discrepancy_table(company, lang)
            + tail(lang, up))


def render_month_page(month: dict, companies: list[dict]) -> str:
    """A month that continues a company: where the difference at its end came from, then the month alone."""
    lang, slug = month["lang"], month["slug"]
    up = "../" * (slug.count("/") + 1)
    e, cur, t = html.escape, month["currency"], TEXTS[lang]
    start, end = dt.date.fromisoformat(month["period_start"]), dt.date.fromisoformat(month["period_end"])
    day = lambda d: f"{d.day} {t['months_of'][d.month]}"
    name = t["months"][end.month]
    lines, totals = month["rollforward"], month["totals"]

    def count(column: int) -> int:
        return sum(1 for line in lines if line[column] != 0)

    steps = [(t["open_at"].format(day=day(start - dt.timedelta(1))), count(5), totals["opening"], ""),
             (t["changes_in"].format(month=name), count(6), totals["period"], ""),
             (t["open_at"].format(day=day(end)), count(7), totals["closing"], "total")]
    rollforward = "".join(f'<tr class="{css}"><td>{e(label)}</td><td class="num">{n}</td>'
                          f'<td class="num">{e(fmt(amount, cur, lang))}</td></tr>' for label, n, amount, css in steps)
    timing = "".join(f'<tr><td>{e(t["timing_at"].format(day=day(d)))}</td>'
                     f'<td class="num">{e(fmt(totals[label], cur, lang))}</td></tr>'
                     for d, label in ((start - dt.timedelta(1), "in_transit_opening"), (end, "in_transit_closing")))
    amount = lambda x: fmt(x, cur, lang) if x != 0 else ""
    rows = "".join(
        f"<tr><td>{e(key)}</td><td>{e(name_in(lang, RU_KINDS, kind, EN_KINDS))}</td>"
        f"<td>{e(t['months'][int(since[5:7])])}</td>"
        f"<td>{e(name_in(lang, RU_CAUSES, cause_opening or cause_period, EN_CAUSES))}</td>"
        f'<td class="num">{e(amount(opening))}</td><td class="num">{e(amount(period))}</td>'
        f'<td class="num">{e(fmt(closing, cur, lang))}</td></tr>'
        for key, kind, cause_opening, cause_period, since, opening, period, closing in lines)
    head_of = lambda heads, numbers: "".join(f'<th class="num">{e(h)}</th>' if n in numbers else f"<th>{e(h)}</th>"
                                             for n, h in enumerate(heads))
    lines_head = head_of([h.format(month=name) for h in t["lines_head"]], (4, 5, 6))
    return (head(lang, month["page_title"], month["page_description"], up, f"{slug}/")
            + '<nav class="top"><a href="https://minihub.app">minihub.app</a></nav>'
            + tabs(companies, slug.rsplit("/", 1)[0], lang, up)
            + f'<h1>{e(title_of(month, lang))}</h1><p class="lead">{e(t["month_lead"])}</p>'
              f'<h2>{e(t["rollforward"])}</h2><div class="wrap"><table class="rollforward">'
              f'<tr>{head_of(t["rollforward_head"], (1, 2))}</tr>{rollforward}</table></div>'
              f'<p class="lead">{e(t["rollforward_note"])}</p>'
              f'<h2>{e(t["timing"])}</h2><div class="wrap"><table class="timing">{timing}</table></div>'
              f'<h2>{e(t["lines"])}</h2><div class="wrap"><table><tr>{lines_head}</tr>{rows}</table></div>'
            + bridge_table(month, lang) + discrepancy_table(month, lang)
            + tail(lang, up))


def render_index(companies: list[dict], lang: str = "en", extra: str = "") -> str:
    """`extra` is HTML placed after the company cards: the load check's block."""
    e, t = html.escape, TEXTS[lang]
    up = "../" if t["index_href"] else ""
    names = ", ".join(c["tab"] for c in companies)
    description = t["description"].format(count=t["count"].get(len(companies), len(companies)), names=names)
    cards = "".join(
        f'<li><a href="{up}{c["slug"]}/">{e(c["tab"])}</a> <small>{e(LANG_TAGS.get(c["lang"], c["lang"]))}</small>'
        f'<p>{e(title_of(c, lang))}</p><p>{e(summary(c["discrepancies"], c["currency"], lang))}</p></li>'
        for c in companies)
    return (head(lang, t["title"], description, up, t["index_href"], START_PAGES)
            + f'<nav class="top"><a href="https://minihub.app">minihub.app</a>'
              f'<a href="{t["switch_href"]}">{e(t["switch"])}</a></nav>'
            + tabs(companies, None, lang, up)
            + f'<h1>{e(t["h1"])}</h1><p class="lead">{e(t["lead"])}</p><p class="lead">{e(t["ledger"])}</p>'
              f'<ul class="companies">{cards}</ul>{extra}'
            + tail(lang, up))


def sitemap(companies: list[dict], extra: tuple | list = ()) -> str:
    """Every published page once; the start pages also list each other as language versions. `extra` are
    further page paths under SITE."""
    languages = "".join(f'<xhtml:link rel="alternate" hreflang="{code}" href="{SITE}{path}"/>'
                        for code, path in START_PAGES.items())
    starts = [f"<url><loc>{SITE}{path}</loc>{languages}</url>" for path in dict.fromkeys(START_PAGES.values())]
    others = [f"<url><loc>{SITE}{c['slug']}/</loc></url>" for c in companies]
    others += [f"<url><loc>{SITE}{path}</loc></url>" for path in extra]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(starts + others) + "\n</urlset>\n")


def main() -> None:
    import report_load  # it imports this module; a module-level import would be circular

    rows = [{**d, "title_ru": d.get("title_ru") or d["title"], **load(d["dataset"])} for d in datasets()]
    companies, months = split_months(rows)
    for m in months:
        m.update(load_month(m["dataset"]))
    site = ROOT / "site"
    pages = [(site / "index.html", render_index(companies, "en", report_load.start_block("en"))),
             (site / "ru" / "index.html", render_index(companies, "ru", report_load.start_block("ru")))]
    pages += [(site / c["slug"] / "index.html", render_company_page(c, companies)) for c in companies]
    pages += [(site / m["slug"] / "index.html", render_month_page(m, companies)) for m in months]
    for path, page in pages:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page, encoding="utf-8")
        print(f"written {path}")
    (site / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    for lang in LANG_TAGS:
        shutil.copyfile(ROOT / "preview" / f"{lang}.png", site / f"preview-{lang}.png")
    paths = [f"{m['slug']}/" for m in months] + list(report_load.page_paths())
    (site / "sitemap.xml").write_text(sitemap(companies, paths), encoding="utf-8")
    (site / "robots.txt").write_text(ROBOTS, encoding="utf-8")


if __name__ == "__main__":
    main()

"""Write site/index.html (English) and site/ru/index.html (Russian) from data/<dataset>/recon.duckdb:
summary, bridge, discrepancies. No JavaScript.

Nothing here names a platform: section titles, Russian titles and which page leads with a company come
from dbt/seeds/datasets.csv, so a new company is a row there, not a change here.
"""
import csv
import html
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
SYMBOLS = {"EUR": "€", "RUB": "₽"}
NBSP = " "
STYLE = """
body { font: 16px/1.5 system-ui, sans-serif; color: #1d2433; background: #fbfaf7; margin: 0; }
main { max-width: 72rem; margin: 0 auto; padding: 2rem 1rem; }
nav { margin: 0 0 1rem; font-size: .9rem; } a { color: #1f5fbf; }
h1 { font-size: 1.6rem; margin: 0 0 .25rem; } h2 { font-size: 1.25rem; margin: 2.5rem 0 .25rem; }
p.lead { color: #4a5368; margin: 0 0 1rem; } .summary { font-weight: 600; }
.wrap { overflow-x: auto; } table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid #e3e0d8; vertical-align: top; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.total td { font-weight: 600; border-top: 2px solid #1d2433; }
footer { margin-top: 3rem; color: #4a5368; font-size: .85rem; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e3db; background: #15181f; } p.lead, footer { color: #a9b0c0; } a { color: #8ab4f8; }
  th, td { border-color: #2c313c; } tr.total td { border-top-color: #e6e3db; }
}
"""

TEXTS = {
    "en": {
        "title": "Why payouts don't match the books — reconciliation demo",
        "description": "Ledger, platform payouts and bank reconciled to the cent for three made-up sellers (Stripe, "
                       "Ozon, Wildberries): every discrepancy found by SQL, with its cause and amount.",
        "h1": "Money reconciliation: ledger, platform, payouts and bank",
        "lead": "Made-up companies, September 2026. Every discrepancy below was planted on purpose and found by "
                "SQL; differences reconcile each level to the next, to the cent.",
        "ledger": "The books are a ledger export, usually from Xero, QuickBooks or NetSuite; the demo uses one "
                  "common layout for every company.",
        "bridge": "Bridge: ledger → platform → payouts → bank",
        "discrepancies": "Discrepancies",
        "bridge_head": ("Step", "Level", "Amount"),
        "rows_head": ("Level", "Cause", "Key", "Kind", "Difference", "Effect", "Explanation"),
        "author": "Made by Andrey Karazhev. Data moves between systems and quietly stops matching; I find the "
                  "cause and fix it. If you have a similar case: <a href=\"mailto:hello@minihub.app\">hello@minihub.app</a>",
        "footer": "Data is fictional. Platform file layouts follow public documentation where it could be read; "
                  "elsewhere they are demo assumptions, listed in the README. The demo is not affiliated with the "
                  "platforms. Model docs: {docs} (uses JavaScript). Rerun: <code>./run.sh</code>.",
        "switch": "Русская версия",
        "switch_href": "ru/",
        "docs_href": "docs/",
    },
    "ru": {
        "title": "Почему выплата маркетплейса не сходится с учётом — демо сверки",
        "description": "Учёт, выплаты маркетплейса и банк сверены до копейки у трёх выдуманных продавцов (Ozon, "
                       "Wildberries, Stripe): каждое расхождение найдено SQL, с причиной и суммой.",
        "h1": "Сверка денег: учёт, площадка, выплаты и банк",
        "lead": "Выдуманные компании, сентябрь 2026. Все расхождения ниже заложены нарочно и найдены SQL; разница "
                "на каждом уровне сверяется со следующим до копейки.",
        "ledger": "Учёт — выгрузка проводок: у продавцов на маркетплейсах обычно из 1С или МойСклад; в демо у всех "
                  "компаний один общий формат.",
        "bridge": "Мост: учёт → площадка → выплаты → банк",
        "discrepancies": "Расхождения",
        "bridge_head": ("Шаг", "Уровень", "Сумма"),
        "rows_head": ("Уровень", "Причина", "Ключ", "Вид", "Разница", "Итог", "Объяснение"),
        "author": "Сделал Андрей Каражев, Минск. Данные ходят между системами и тихо перестают сходиться — я нахожу "
                  "причину и чиню. Похожий случай у вас — напишите: <a href=\"mailto:hello@minihub.app\">hello@minihub.app</a>",
        "footer": "Данные выдуманные. Форматы файлов площадок повторяют публичную документацию там, где её удалось "
                  "прочитать; остальное — допущения демо, они перечислены в README. Демо не связано с площадками. "
                  "Описание моделей: {docs} (нужен JavaScript). Повторить: <code>./run.sh</code>.",
        "switch": "English version",
        "switch_href": "../",
        "docs_href": "../docs/",
    },
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


def summary(rows: list[tuple], currency: str, lang: str = "en") -> str:
    def total(effect: str) -> Decimal:
        return sum((r[4] for r in rows if r[5] == effect), Decimal("0.00"))
    short = fmt(-total("short"), currency, lang)
    over = fmt(total("over"), currency, lang)
    timing = fmt(-total("timing"), currency, lang)
    if lang == "ru":
        return f"Сентябрь 2026: {len(rows)} {plural_ru(len(rows))}; недостача {short}, излишек {over}, в пути {timing}"
    return f"September 2026: {len(rows)} discrepancies, {short} short, {over} over, {timing} in transit"


def render_section(section: dict, lang: str = "en") -> str:
    e, cur, t, ru = html.escape, section["currency"], TEXTS[lang], lang == "ru"
    title = (section.get("title_ru") or section["title"]) if ru else section["title"]

    def name(mapping: dict, code: str) -> str:
        return mapping[code] if ru else code

    bridge = "".join(
        f'<tr class="{"total" if row_type == "total" else ""}">'
        f'<td>{e(name(RU_TOTALS, label) if row_type == "total" else "  " + name(RU_CAUSES, label))}</td>'
        f'<td>{e(name(RU_LEVELS, level) if level else "")}</td><td class="num">{e(fmt(amount, cur, lang))}</td></tr>'
        for _, row_type, level, label, amount in section["bridge"])
    rows = "".join(
        f"<tr><td>{e(name(RU_LEVELS, level))}</td><td>{e(name(RU_CAUSES, cause))}</td><td>{e(key)}</td>"
        f'<td>{e(name(RU_KINDS, kind))}</td><td class="num">{e(fmt(diff, cur, lang))}</td>'
        f"<td>{e(name(RU_EFFECTS, effect))}</td><td>{e(name(RU_EXPLANATIONS, text))}</td></tr>"
        for level, cause, key, kind, diff, effect, text in section["discrepancies"])
    bridge_head = "".join(f'<th class="num">{e(h)}</th>' if n == 2 else f"<th>{e(h)}</th>"
                          for n, h in enumerate(t["bridge_head"]))
    rows_head = "".join(f'<th class="num">{e(h)}</th>' if n == 4 else f"<th>{e(h)}</th>"
                        for n, h in enumerate(t["rows_head"]))
    return (f"<section><h2>{e(title)}</h2>"
            f'<p class="summary">{e(summary(section["discrepancies"], cur, lang))}</p>'
            f'<h3>{e(t["bridge"])}</h3><div class="wrap"><table><tr>{bridge_head}</tr>{bridge}</table></div>'
            f'<h3>{e(t["discrepancies"])}</h3><div class="wrap"><table><tr>{rows_head}</tr>{rows}'
            f"</table></div></section>")


def render_page(sections: list[dict], lang: str = "en") -> str:
    e, t = html.escape, TEXTS[lang]
    # Stable sort: the companies of this page's audience first, file order otherwise.
    ordered = sorted(sections, key=lambda s: s.get("lead_lang", "en") != lang)
    body = "".join(render_section(s, lang) for s in ordered)
    docs = f'<a href="{t["docs_href"]}">dbt docs</a>'
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(t["title"])}</title><meta name="description" content="{e(t["description"])}">'
            f'<style>{STYLE}</style></head><body><main>'
            f'<nav><a href="{t["switch_href"]}">{e(t["switch"])}</a></nav>'
            f'<h1>{e(t["h1"])}</h1><p class="lead">{e(t["lead"])}</p><p class="lead">{e(t["ledger"])}</p>'
            f'{body}<p class="author">{t["author"]}</p>'
            f'<footer><p>{t["footer"].format(docs=docs)}</p></footer></main></body></html>\n')


def main() -> None:
    sections = []
    for d in datasets():
        sections.append({"title": d["title"], "title_ru": d.get("title_ru") or d["title"],
                         "currency": d["currency"], "lead_lang": d.get("lead_lang") or "en",
                         **load(d["dataset"])})
    for lang, out in (("en", ROOT / "site" / "index.html"), ("ru", ROOT / "site" / "ru" / "index.html")):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_page(sections, lang), encoding="utf-8")
        print(f"written {out}")


if __name__ == "__main__":
    main()

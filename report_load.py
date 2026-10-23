"""Write the load check pages from data/<dataset>/recon.duckdb, no JavaScript:

    site/<slug>/index.html         one page per dataset of dbt/seeds/load/load_datasets.csv, in its language: the
                                   summary, the bridge by table and month, the Dag's task graph, every difference
    site/<first slug>/dag.svg      the task graph of the Airflow Dag, drawn from load_tasks.dag_tasks()
    site/preview-load-<lang>.png   the link preview of these pages, copied from preview/load-<lang>.png

report.py links here from the start pages (start_block) and lists the pages in sitemap.xml (page_paths). Nothing
here names a dataset: addresses, titles and descriptions come from load_datasets.csv.
"""
import datetime as dt
import html
import shutil
from decimal import Decimal

import duckdb

import load_tasks
import report

ROOT = report.ROOT
MODELS = "https://github.com/akarazhev/reconciliation-demo/tree/main/dbt/models/load"
MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"),
    "ru": ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь",
           "ноябрь", "декабрь"),
}
ORDER = ("batch_boundary_loss", "missing_in_target", "deleted_left_behind", "extra_in_target", "duplicate_after_rerun",
         "duplicate_in_target", "truncated_decimal", "timezone_shift", "whitespace_to_null", "schema_drift",
         "payment_wrong_invoice", "changed_not_exported", "late_item_not_updated", "value_mismatch")

TEXTS = {
    "en": {
        "start": "Load check: after a migration or an export",
        "start_lead": "Data moved from one system to another: what changed on the way, row by row, with its cause.",
        "all": "All demos",
        "bridge": "Bridge: source to target, by table and month",
        "bridge_head": ("Month", "Step", "Rows", "Control total"),
        "dag": "Task graph of the DAG",
        "differences": "Differences",
        "rows_head": ("Table", "Cause", "Key", "Column", "Source", "Target", "Difference", "Explanation"),
        "run": "How to run",
        "run_text": "Both demos from scratch: <code>./run.sh</code>. The load check as an Airflow Dag, with its "
                    "environment set up as the README says: <code>airflow dags test load_check</code>.",
        "footer": "The data is fictional. One DuckDB database stands in for both systems; the formats follow the "
                  "behaviour the README describes. Models: {models}.",
        "preview_alt": "What a billing migration changed: 112 differences in 3 tables, each with its cause.",
        "all_rows": "All rows",
        "outside": "{month} (outside the period)",
    },
    "ru": {
        "start": "Проверка загрузки: после миграции и выгрузки",
        "start_lead": "Данные переехали из одной системы в другую: что изменилось по дороге, построчно и с причиной.",
        "all": "Все демо",
        "bridge": "Мост: от источника к цели, по таблицам и месяцам",
        "bridge_head": ("Месяц", "Шаг", "Строки", "Контрольная сумма"),
        "dag": "Граф задач DAG",
        "differences": "Расхождения",
        "rows_head": ("Таблица", "Причина", "Ключ", "Колонка", "Источник", "Цель", "Разница", "Объяснение"),
        "run": "Как запустить",
        "run_text": "Оба демо с нуля: <code>./run.sh</code>. Проверка загрузки как DAG в Airflow, когда его "
                    "окружение настроено по README: <code>airflow dags test load_check</code>.",
        "footer": "Данные выдуманные. Обе системы изображает одна база DuckDB, форматы повторяют поведение, "
                  "описанное в README. Модели: {models}.",
        "preview_alt": "Что потерялось при выгрузке из 1С в MySQL: 91 расхождение в 3 таблицах, у каждого своя причина.",
        "all_rows": "Все строки",
        "outside": "{month} (вне периода)",
    },
}

# A count and what happened to that many rows or values, for the summary line.
EN_SUMMARY = {
    "batch_boundary_loss": ("row lost at a batch boundary", "rows lost at batch boundaries"),
    "missing_in_target": ("row missing in the target", "rows missing in the target"),
    "deleted_left_behind": ("deleted line left in the target", "deleted lines left in the target"),
    "extra_in_target": ("extra row in the target", "extra rows in the target"),
    "duplicate_after_rerun": ("line loaded twice", "lines loaded twice"),
    "duplicate_in_target": ("row doubled in the target", "rows doubled in the target"),
    "truncated_decimal": ("amount truncated", "amounts truncated"),
    "timezone_shift": ("time shifted by the time zone", "times shifted by the time zone"),
    "whitespace_to_null": ("space turned into NULL", "spaces turned into NULL"),
    "schema_drift": ("code missing from the map", "codes missing from the map"),
    "payment_wrong_invoice": ("payment linked to the wrong invoice", "payments linked to the wrong invoice"),
    "changed_not_exported": ("change not exported", "changes not exported"),
    "late_item_not_updated": ("renamed item not updated", "renamed items not updated"),
    "value_mismatch": ("value that differs", "values that differ"),
}
RU_SUMMARY = {
    "batch_boundary_loss": ("строка потеряна на границе пачки", "строки потеряны на границах пачек",
                            "строк потеряны на границах пачек"),
    "missing_in_target": ("строка не дошла до цели", "строки не дошли до цели", "строк не дошли до цели"),
    "deleted_left_behind": ("удалённая строка осталась в цели", "удалённые строки остались в цели",
                            "удалённых строк остались в цели"),
    "extra_in_target": ("лишняя строка в цели", "лишние строки в цели", "лишних строк в цели"),
    "duplicate_after_rerun": ("строка записана дважды", "строки записаны дважды", "строк записаны дважды"),
    "duplicate_in_target": ("строка повторяется в цели", "строки повторяются в цели", "строк повторяются в цели"),
    "truncated_decimal": ("сумма урезана", "суммы урезаны", "сумм урезаны"),
    "timezone_shift": ("время сдвинуто часовым поясом", "значения времени сдвинуты часовым поясом",
                       "значений времени сдвинуты часовым поясом"),
    "whitespace_to_null": ("пробел стал NULL", "пробела стали NULL", "пробелов стали NULL"),
    "schema_drift": ("код не нашёлся в справочнике", "кода не нашлись в справочнике", "кодов не нашлись в справочнике"),
    "payment_wrong_invoice": ("платёж привязан не к тому счёту", "платежа привязаны не к тому счёту",
                              "платежей привязаны не к тому счёту"),
    "changed_not_exported": ("изменение не выгружено", "изменения не выгружены", "изменений не выгружены"),
    "late_item_not_updated": ("переименованный артикул не обновлён", "переименованных артикула не обновлены",
                              "переименованных артикулов не обновлены"),
    "value_mismatch": ("значение расходится", "значения расходятся", "значений расходятся"),
}
CAUSES = {
    "en": {"batch_boundary_loss": "lost at a batch boundary", "missing_in_target": "missing in the target",
           "deleted_left_behind": "deleted, left in the target", "extra_in_target": "extra in the target",
           "duplicate_after_rerun": "loaded twice by a re-run", "duplicate_in_target": "doubled in the target",
           "truncated_decimal": "amount truncated", "timezone_shift": "time zone shift",
           "whitespace_to_null": "spaces became NULL", "schema_drift": "code missing from the map",
           "payment_wrong_invoice": "linked to the wrong invoice", "changed_not_exported": "changed after the export",
           "late_item_not_updated": "renamed item not updated", "value_mismatch": "values differ"},
    "ru": {"batch_boundary_loss": "потеря на границе пачки", "missing_in_target": "нет в цели",
           "deleted_left_behind": "удалена, осталась в цели", "extra_in_target": "лишняя в цели",
           "duplicate_after_rerun": "повтор после перезапуска", "duplicate_in_target": "повтор в цели",
           "truncated_decimal": "сумма урезана", "timezone_shift": "сдвиг часового пояса",
           "whitespace_to_null": "пробелы стали NULL", "schema_drift": "кода нет в справочнике",
           "payment_wrong_invoice": "не тот счёт", "changed_not_exported": "изменено после выгрузки",
           "late_item_not_updated": "артикул не обновлён", "value_mismatch": "значения расходятся"},
}
STEPS = {
    "en": {"source": "Source", "target": "Target", "moved_out": "Moved to another month",
           "moved_in": "Moved in from another month"},
    "ru": {"source": "Источник", "target": "Цель", "moved_out": "Ушли в другой месяц",
           "moved_in": "Пришли из другого месяца"},
}
RU_TABLES = {"customers": "клиенты", "invoices": "счета", "lines": "строки счетов", "payments": "платежи"}
# Keyed by the exact English text of load_explanation in dbt/macros/load_check/classify.sql; a test checks that
# every explanation of the Russian dataset has one.
RU_EXPLANATIONS = {
    "Skipped at a batch boundary: the next batch started after this row's time.":
        "Пропущена на границе пачки: следующая пачка началась после времени этой строки.",
    "Deleted in the source after the export; still in the target.": "Удалена в источнике после выгрузки, в цели осталась.",
    "Loaded twice: a re-run of the export wrote it again.": "Записана дважды: перезапуск выгрузки записал её снова.",
    "In the source, not in the target.": "Есть в источнике, нет в цели.",
    "In the target, not in the source.": "Есть в цели, нет в источнике.",
    "In the target more than once.": "В цели больше одного раза.",
    "Amount cut to the target's decimals.": "Сумма урезана до знаков цели.",
    "Time moved by whole hours: local time loaded as UTC.": "Время сдвинуто на целые часы: местное время загружено как UTC.",
    "A value of spaces became NULL.": "Значение из пробелов стало NULL.",
    "Code missing from the migration map; the target has NULL.": "Кода нет в справочнике миграции, в цели NULL.",
    "Linked to an older invoice with the same number.": "Привязан к старому счёту с тем же номером.",
    "Changed in the source after it was exported.": "Изменено в источнике после выгрузки.",
    "Item code renamed in the source; the target kept the old code.": "Артикул переименован в источнике, в цели остался старый.",
    "Values differ; no other cause found.": "Значения расходятся, другой причины не найдено.",
}


def ru_plural(n: int, forms: tuple[str, str, str]) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def summary_line(rows, lang: str) -> str:
    """One line: how many differences in how many tables, then each cause with its count. `rows` holds
    (entity, cause, ...) per difference."""
    counts = {cause: sum(1 for r in rows if r[1] == cause) for cause in ORDER}
    tables = len({r[0] for r in rows})
    if lang == "ru":
        parts = ", ".join(f"{n} {ru_plural(n, RU_SUMMARY[c])}" for c, n in counts.items() if n)
        where = "таблице" if tables % 10 == 1 and tables % 100 != 11 else "таблицах"
        return f"{len(rows)} {report.plural_ru(len(rows))} в {tables} {where}: {parts}"
    parts = ", ".join(f"{n} {EN_SUMMARY[c][0 if n == 1 else 1]}" for c, n in counts.items() if n)
    return (f"{len(rows)} difference{'' if len(rows) == 1 else 's'} in {tables} table{'' if tables == 1 else 's'}: "
            f"{parts}")


def up_of(slug: str) -> str:
    return "../" * (slug.count("/") + 1)


def start_block(lang: str) -> str:
    """The load check's block for a start page: a heading and one card per dataset, from load_datasets.csv only."""
    e, t = html.escape, TEXTS[lang]
    up = "../" if report.TEXTS[lang]["index_href"] else ""
    cards = "".join(
        f'<li><a href="{up}{d["slug"]}/">{e(d["title_ru"] if lang == "ru" else d["title"])}</a> '
        f'<small>{e(report.LANG_TAGS.get(d["lang"], d["lang"]))}</small><p>{e(d["page_description"])}</p></li>'
        for d in load_tasks.datasets())
    return f'<h2>{e(t["start"])}</h2><p class="lead">{e(t["start_lead"])}</p><ul class="companies">{cards}</ul>'


def page_paths() -> list[str]:
    return [d["slug"] + "/" for d in load_tasks.datasets()]


def load(dataset: str) -> dict:
    con = duckdb.connect(str(ROOT / "data" / dataset / "recon.duckdb"), read_only=True)
    try:
        bridge = con.execute("select entity, period, step, label, rows, amount from main.load_bridge "
                             "order by entity, period nulls first, step, label").fetchall()
        rows = con.execute("select entity, cause, key, column_name, source_value, target_value, difference, "
                           "explanation from main.load_discrepancies order by entity, cause, key, column_name").fetchall()
    finally:
        con.close()
    return {"bridge": bridge, "discrepancies": rows}


def number(value: Decimal, lang: str, signed: bool = False) -> str:
    sign = "−" if value < 0 else ("+" if signed and value > 0 else "")
    text = f"{abs(value):,.4f}"
    if lang == "ru":
        text = text.replace(",", report.NBSP).replace(".", ",")
    return sign + text


def count(value: int, lang: str, signed: bool = False) -> str:
    text = f"{abs(value):,}"
    if lang == "ru":
        text = text.replace(",", report.NBSP)
    return ("−" if value < 0 else ("+" if signed and value > 0 else "")) + text


def shown(value: str | None) -> str:
    if value is None:
        return "NULL"
    return f"'{value}'" if not value.strip() else value


def month(period: dt.date | None, dataset: dict, lang: str) -> str:
    t = TEXTS[lang]
    if period is None:
        return t["all_rows"]
    name = f"{MONTHS[lang][period.month - 1]} {period.year}"
    first = dt.date.fromisoformat(dataset["period_start"]).replace(day=1)
    last = dt.date.fromisoformat(dataset["period_end"]).replace(day=1)
    return name if first <= period <= last else t["outside"].format(month=name)


def dag_svg(task_ids: list[str]) -> str:
    """The Dag's tasks left to right, each arrow to the next. Its own background: shown as an image, it cannot
    follow the page's light or dark theme."""
    e = html.escape
    box_w, box_h, gap, pad = 210, 48, 46, 20
    width, height = pad * 2 + len(task_ids) * box_w + (len(task_ids) - 1) * gap, box_h + pad * 2
    middle = pad + box_h // 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
             f'height="{height}" role="img" aria-label="{e(" → ".join(task_ids))}">',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
             'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#4a5368"/></marker></defs>',
             f'<rect width="{width}" height="{height}" fill="#fbfaf7"/>']
    for n, task in enumerate(task_ids):
        x = pad + n * (box_w + gap)
        if n:
            parts.append(f'<line x1="{x - gap + 4}" y1="{middle}" x2="{x - 6}" y2="{middle}" stroke="#4a5368" '
                         f'stroke-width="2" marker-end="url(#arrow)"/>')
        parts.append(f'<rect x="{x}" y="{pad}" width="{box_w}" height="{box_h}" rx="8" fill="#ffffff" '
                     f'stroke="#1f4fd8" stroke-width="2"/>')
        parts.append(f'<text x="{x + box_w // 2}" y="{middle + 5}" text-anchor="middle" '
                     f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="14" '
                     f'fill="#1d2433">{e(task)}</text>')
    return "".join(parts) + "</svg>\n"


def dag_folder() -> str:
    return load_tasks.datasets()[0]["slug"]


def render_page(dataset: dict) -> str:
    lang, slug = dataset["lang"], dataset["slug"]
    e, t, up, ru = html.escape, TEXTS[lang], up_of(slug), lang == "ru"
    data = load(dataset["dataset"])
    rows = data["discrepancies"]

    def table(entity: str) -> str:
        return RU_TABLES.get(entity, entity) if ru else entity

    def step(label: str) -> str:
        text = STEPS[lang].get(label) or CAUSES[lang].get(label, label)
        return text[:1].upper() + text[1:]

    bridge = ""
    for entity in dict.fromkeys(r[0] for r in data["bridge"]):
        steps = [r for r in data["bridge"] if r[0] == entity]
        amounts = any(amount for *_, amount in steps)  # an entity without a measure shows rows only
        body = "".join(
            f'<tr class="{"total" if label == "target" else ""}"><td>{e(month(period, dataset, lang))}</td>'
            f'<td>{e(step(label))}</td>'
            f'<td class="num">{e(count(n, lang, label not in ("source", "target")))}</td>'
            f'<td class="num">{e(number(amount, lang, label not in ("source", "target")) if amounts else "")}</td></tr>'
            for _, period, _, label, n, amount in steps)
        head = "".join(f'<th class="num">{e(h)}</th>' if i >= 2 else f"<th>{e(h)}</th>"
                       for i, h in enumerate(t["bridge_head"]))
        bridge += (f'<h3>{e(table(entity))}</h3><div class="wrap"><table class="bridge"><tr>{head}</tr>{body}'
                   f"</table></div>")
    found = "".join(
        f"<tr><td>{e(table(entity))}</td><td>{e(CAUSES[lang].get(cause, cause))}</td><td>{e(key)}</td>"
        f"<td>{e(column or '')}</td><td>{e(shown(source) if column else '')}</td>"
        f"<td>{e(shown(target) if column else '')}</td>"
        f'<td class="num">{e("" if diff is None else number(diff, lang, True))}</td>'
        f"<td>{e(RU_EXPLANATIONS.get(text, text) if ru else text)}</td></tr>"
        for entity, cause, key, column, source, target, diff, text in rows)
    rows_head = "".join(f'<th class="num">{e(h)}</th>' if i == 6 else f"<th>{e(h)}</th>"
                        for i, h in enumerate(t["rows_head"]))
    preview = (f"{report.SITE}preview-load-{lang}.png", 1200, 627, t["preview_alt"])
    models = f'<a href="{MODELS}">dbt/models/load</a>'
    start = up + report.TEXTS[lang]["index_href"]
    return (report.head(lang, dataset["page_title"], dataset["page_description"], up, slug + "/", preview=preview)
            + f'<nav class="top"><a href="https://minihub.app">minihub.app</a><a href="{start}">{e(t["all"])}</a></nav>'
            + f'<h1>{e(dataset["title_ru"] if ru else dataset["title"])}</h1>'
              f'<p class="lead">{e(dataset["page_description"])}</p>'
              f'<p class="lead"><b>{e(summary_line(rows, lang))}</b></p>'
              f'<h2>{e(t["bridge"])}</h2>{bridge}'
              f'<h2>{e(t["dag"])}</h2><p><img src="{up}{dag_folder()}/dag.svg" alt="{e(t["dag"])}" '
              f'style="max-width: 100%; height: auto"></p>'
              f'<h2>{e(t["differences"])}</h2><div class="wrap"><table><tr>{rows_head}</tr>{found}</table></div>'
              f'<h2>{e(t["run"])}</h2><p class="lead">{t["run_text"]}</p>'
              f'<p class="author">{report.TEXTS[lang]["author"]}</p>'
              f'<footer><p>{t["footer"].format(models=models)}</p></footer></main></body></html>\n')


def main() -> None:
    site = ROOT / "site"
    for dataset in load_tasks.datasets():
        path = site / dataset["slug"] / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_page(dataset), encoding="utf-8")
        print(f"written {path}")
    (site / dag_folder() / "dag.svg").write_text(dag_svg([task for task, _ in load_tasks.dag_tasks()]), encoding="utf-8")
    for lang in TEXTS:
        shutil.copyfile(ROOT / "preview" / f"load-{lang}.png", site / f"preview-load-{lang}.png")


if __name__ == "__main__":
    main()

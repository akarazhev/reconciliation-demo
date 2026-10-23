import re
from pathlib import Path

import duckdb
import pytest

import load_tasks
import report
import report_load
from test_report import ALL

ROOT = Path(__file__).resolve().parents[1]
EN_ROWS = ([("customers", "whitespace_to_null")] * 10 + [("invoices", "truncated_decimal")] * 40
           + [("invoices", "schema_drift")] * 30 + [("payments", "timezone_shift")] * 25
           + [("payments", "batch_boundary_loss")] * 7)
RU_ROWS = ([("lines", "deleted_left_behind")] * 12 + [("lines", "changed_not_exported")] * 30
           + [("invoices", "changed_not_exported")] * 15 + [("lines", "late_item_not_updated")] * 8
           + [("payments", "payment_wrong_invoice")] * 6 + [("lines", "duplicate_after_rerun")] * 20)


def database(dataset):
    path = ROOT / "data" / dataset / "recon.duckdb"
    if not path.exists():
        pytest.skip("run ./run.sh first")
    return path


def test_summary_line_names_causes_in_words():
    en = report_load.summary_line(EN_ROWS, "en")
    assert en.startswith("112 differences in 3 tables: ")
    assert set(map(int, re.findall(r"\d+", en))) == {112, 3, 7, 40, 25, 30, 10}
    ru = report_load.summary_line(RU_ROWS, "ru")
    assert ru.startswith("91 расхождение в 3 таблицах: ")
    assert set(map(int, re.findall(r"\d+", ru))) == {91, 3, 12, 45, 8, 6, 20}


def test_dag_svg_lists_every_task_in_order():
    ids = [task_id for task_id, _ in load_tasks.dag_tasks()]
    assert ids == ["generate", "dbt_build_subscribe_co", "dbt_build_opt_torg", "report"]
    assert re.findall(r"<text[^>]*>([^<]+)</text>", report_load.dag_svg(ids)) == ids


def test_start_pages_link_to_demo_2():
    en = report.render_index(ALL, "en", extra=report_load.start_block("en"))
    assert 'href="migration/"' in en and 'href="ru/vygruzka/"' in en
    assert 'href="../migration/"' in report.render_index(ALL, "ru", extra=report_load.start_block("ru"))


def test_sitemap_lists_demo_2_pages():
    with_pages = report.sitemap(ALL, extra=report_load.page_paths())
    assert f"<loc>{report.SITE}migration/</loc>" in with_pages
    assert f"<loc>{report.SITE}ru/vygruzka/</loc>" in with_pages
    assert "migration" not in report.sitemap(ALL)


@pytest.mark.parametrize("dataset", load_tasks.datasets(), ids=lambda d: d["dataset"])
def test_load_pages_have_no_script_and_a_summary(dataset):
    database(dataset["dataset"])
    page = report_load.render_page(dataset)
    assert "<script" not in page.lower()
    assert "—" not in page
    assert ("112 differences in 3 tables: " if dataset["lang"] == "en" else "91 расхождение в 3 таблицах: ") in page


def test_every_explanation_has_russian_text():
    con = duckdb.connect(str(database("opt_torg")), read_only=True)
    try:
        texts = {row[0] for row in con.execute("select distinct explanation from main.load_discrepancies").fetchall()}
    finally:
        con.close()
    assert texts and texts <= set(report_load.RU_EXPLANATIONS)


def test_start_blocks_speak_their_language():
    assert not re.search("[А-Яа-яЁё]", report_load.start_block("en"))
    assert "Оптовая компания" in report_load.start_block("ru")

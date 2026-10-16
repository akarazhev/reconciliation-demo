import html
import re
from decimal import Decimal

import report

ROWS = [
    ("operation", "duplicate", "EU-1", "sale", Decimal("-50.00"), "short", "Booked twice."),
    ("operation", "partial", "EU-2", "refund", Decimal("70.00"), "over", "Refunded <less>."),
    ("bank", "in_transit", "po_1", "payout", Decimal("-600.00"), "timing", "October."),
]
RU_ROWS = [("operation", "duplicate", "123-1", "sale", Decimal("-50.00"), "short",
            "Booked twice in the ledger; the platform has it once.")]


def company(slug, lang, tab, rows, currency="EUR"):
    return {"dataset": slug + "_set", "slug": slug, "tab": tab, "lang": lang, "currency": currency,
            "title": f"{tab} title", "title_ru": f"{tab} заголовок",
            "page_title": f"{tab} page title", "page_description": f"{tab} page description",
            "bridge": [(1, "total", None, "ledger", Decimal("100.00"))], "discrepancies": rows}


EU = company("shop", "en", "Shop A", ROWS)
RU = company("seller", "ru", "Seller B", RU_ROWS, "RUB")
ALL = [EU, RU]


def test_summary_names_count_and_amounts():
    assert report.summary(ROWS, "EUR") == (
        "September 2026: 3 discrepancies, €50.00 short, €70.00 over, €600.00 in transit"
    )


def test_company_page_escapes_text_and_has_no_script():
    page = report.render_company_page(EU, ALL)
    assert '<html lang="en">' in page
    assert "Refunded &lt;less&gt;." in page
    assert "<script" not in page.lower()


SQL = (report.ROOT / "dbt" / "models" / "recon" / "discrepancies.sql").read_text(encoding="utf-8")


def test_every_sql_explanation_has_a_russian_translation():
    block = SQL[SQL.index("case cause"):SQL.index("as explanation")]
    explanations = set(re.findall(r"'([A-Z][^']*\.)'", block))
    assert len(explanations) == 16
    assert explanations <= set(report.RU_EXPLANATIONS), explanations - set(report.RU_EXPLANATIONS)


def test_every_cause_has_words_in_both_languages():
    block = SQL[SQL.index("case cause"):SQL.index("as explanation")]
    causes = set(re.findall(r"when '([a-z_]+)'", block))
    assert causes and causes <= set(report.RU_CAUSES) and causes <= set(report.EN_CAUSES)


def test_russian_amounts_use_a_decimal_comma_and_a_space_between_thousands():
    assert report.fmt(Decimal("-12491.34"), "RUB", "ru") == "−12 491,34 ₽"
    assert report.fmt(Decimal("684.51"), "EUR", "ru") == "684,51 €"
    assert report.fmt(Decimal("684.51"), "EUR") == "€684.51"


def test_russian_summary_counts_with_the_right_plural():
    assert report.summary(ROWS, "EUR", "ru") == (
        "Сентябрь 2026: 3 расхождения; недостача 50,00 €, излишек 70,00 €, в пути 600,00 €"
    )
    assert report.plural_ru(1) == "расхождение"
    assert report.plural_ru(11) == "расхождений"
    assert report.plural_ru(17) == "расхождений"
    assert report.plural_ru(22) == "расхождения"


def test_company_page_speaks_its_own_language():
    page = report.render_company_page(RU, ALL)
    assert '<html lang="ru">' in page
    assert "<h1>Seller B заголовок</h1>" in page and "Выдуманная компания, сентябрь 2026." in page
    assert "дубль в учёте" in page and "продажа" in page and "учёт" in page
    assert "В учёте проведено дважды, на площадке — один раз." in page
    assert 'href="../docs/"' in page


def test_english_page_names_causes_in_words_not_codes():
    page = report.render_company_page(EU, ALL)
    assert "duplicate in the ledger" in page and "partial refund" in page and "in transit" in page
    assert "in_transit" not in page and ">duplicate<" not in page


def test_every_page_carries_the_same_tabs_and_marks_its_own():
    pages = {
        "index_en": (report.render_index(ALL, "en"), ""),
        "index_ru": (report.render_index(ALL, "ru"), "../"),
        "shop": (report.render_company_page(EU, ALL), "../"),
        "seller": (report.render_company_page(RU, ALL), "../"),
    }
    for name, (page, up) in pages.items():
        assert f'href="{up}shop/"' in page and f'href="{up}seller/"' in page, name
        current = re.findall(r'<a href="([^"]*)" aria-current="page">', page)
        assert len(current) == 1, name
    assert re.search(r'<a href="../shop/" aria-current="page">', pages["shop"][0])
    assert re.search(r'<a href="../seller/" aria-current="page">', pages["seller"][0])
    assert re.search(r'<a href="./" aria-current="page">', pages["index_en"][0])


def test_index_lists_every_company_with_its_figures():
    en = report.render_index(ALL, "en")
    ru = report.render_index(ALL, "ru")
    assert "September 2026: 3 discrepancies, €50.00 short, €70.00 over, €600.00 in transit" in en
    assert "Сентябрь 2026: 3 расхождения" in ru
    assert '<a href="ru/">Русская версия</a>' in en and '<a href="../">English version</a>' in ru


def test_company_page_shows_the_key_figures():
    page = report.render_company_page(EU, ALL)
    start = page.index('<div class="figures">')
    figures = page[start:page.index("<h2>", start)]
    for value in ("3", "€50.00", "€70.00", "€600.00"):
        assert f"<b>{value}</b>" in figures, value


def test_each_page_says_who_made_it_and_where_to_write():
    mail = '<a href="mailto:hello@minihub.app">hello@minihub.app</a>'
    en = report.render_company_page(EU, ALL)
    ru = report.render_company_page(RU, ALL)
    assert "Made by Andrey Karazhev as a side project" in en and mail in en and "Минск" not in en
    assert "Сделал Андрей Каражев, Минск, — свой проект" in ru and mail in ru
    assert "fix it" not in en and "чиню" not in ru      # a side project, not an offer (16 Oct)
    assert en.index("<table") < en.index(mail) < en.index("<footer>")
    for page in (report.render_index(ALL, "en"), report.render_index(ALL, "ru")):
        assert mail in page


def test_titles_and_descriptions_for_search():
    def head(page):
        title = html.unescape(re.search(r"<title>(.*?)</title>", page).group(1))
        description = html.unescape(re.search(r'<meta name="description" content="([^"]*)">', page).group(1))
        return title, description

    assert head(report.render_company_page(EU, ALL)) == ("Shop A page title", "Shop A page description")
    assert head(report.render_company_page(RU, ALL)) == ("Seller B page title", "Seller B page description")
    title, description = head(report.render_index(ALL, "en"))
    assert title == "Why payouts don't match the books — reconciliation demo"
    assert "two made-up companies (Shop A, Seller B)" in description
    title, description = head(report.render_index(ALL, "ru"))
    assert title == "Почему выплата не сходится с учётом — демо сверки"
    assert "двух выдуманных компаний (Shop A, Seller B)" in description


def test_pages_share_the_site_icon_and_link_home():
    for page in (report.render_index(ALL, "en"), report.render_company_page(RU, ALL)):
        assert 'rel="icon"' in page and "favicon.svg" in page
        assert '<a href="https://minihub.app">minihub.app</a>' in page


def test_report_names_no_platform():
    # A new company is a row in dbt/seeds/datasets.csv, not a change here.
    source = (report.ROOT / "report.py").read_text(encoding="utf-8")
    for name in ("Stripe", "Ozon", "Wildberries", "Озон"):
        assert name not in source, name

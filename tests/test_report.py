from decimal import Decimal

import report

ROWS = [
    ("operation", "duplicate", "EU-1", "sale", Decimal("-50.00"), "short", "Booked twice."),
    ("operation", "partial", "EU-2", "refund", Decimal("70.00"), "over", "Refunded <less>."),
    ("bank", "in_transit", "po_1", "payout", Decimal("-600.00"), "timing", "October."),
]


def test_summary_names_count_and_amounts():
    assert report.summary(ROWS, "EUR") == (
        "September 2026: 3 discrepancies, €50.00 short, €70.00 over, €600.00 in transit"
    )


def test_page_escapes_text_and_has_no_script():
    section = {"title": "EU web shop", "currency": "EUR", "bridge": [], "discrepancies": ROWS}
    page = report.render_page([section])
    assert "Refunded &lt;less&gt;." in page
    assert "<script" not in page.lower()
    assert "September 2026: 3 discrepancies" in page


SQL = (report.ROOT / "dbt" / "models" / "recon" / "discrepancies.sql").read_text(encoding="utf-8")


def test_every_sql_explanation_has_a_russian_translation():
    import re
    block = SQL[SQL.index("case cause"):SQL.index("as explanation")]
    explanations = set(re.findall(r"'([A-Z][^']*\.)'", block))
    assert len(explanations) == 16
    assert explanations <= set(report.RU_EXPLANATIONS), explanations - set(report.RU_EXPLANATIONS)


def test_russian_amounts_use_a_decimal_comma_and_a_space_between_thousands():
    assert report.fmt(Decimal("-12491.34"), "RUB", "ru") == "−12 491,34 ₽"
    assert report.fmt(Decimal("684.51"), "EUR", "ru") == "684,51 €"
    assert report.fmt(Decimal("684.51"), "EUR") == "€684.51"


def test_russian_summary_counts_with_the_right_plural():
    assert report.summary(ROWS, "EUR", "ru") == (
        "Сентябрь 2026: 3 расхождения; недостача 50,00 €, излишек 70,00 €, в пути 600,00 €"
    )
    assert report.plural_ru(1) == "расхождение"
    assert report.plural_ru(11) == "расхождений"
    assert report.plural_ru(17) == "расхождений"
    assert report.plural_ru(22) == "расхождения"


def test_russian_page_translates_codes_and_links_back():
    rows = [("operation", "duplicate", "123-1", "sale", Decimal("-50.00"), "short",
             "Booked twice in the ledger; the platform has it once.")]
    section = {"title": "EU web shop", "title_ru": "Продавец", "currency": "RUB", "lead_lang": "ru",
               "bridge": [(1, "total", None, "ledger", Decimal("100.00"))], "discrepancies": rows}
    page = report.render_page([section], "ru")
    assert '<html lang="ru">' in page
    assert "<script" not in page.lower()
    assert "Продавец" in page and "дубль в учёте" in page and "продажа" in page and "учёт" in page
    assert "В учёте проведено дважды, на площадке — один раз." in page
    assert 'href="../"' in page and 'href="../docs/"' in page


def test_each_page_puts_its_own_audience_first():
    eu = {"title": "EU", "title_ru": "ЕС", "currency": "EUR", "lead_lang": "en", "bridge": [], "discrepancies": []}
    oz = {"title": "Ozon", "title_ru": "Озон", "currency": "RUB", "lead_lang": "ru", "bridge": [], "discrepancies": []}
    en_page = report.render_page([eu, oz], "en")
    ru_page = report.render_page([eu, oz], "ru")
    assert en_page.index("<h2>EU</h2>") < en_page.index("<h2>Ozon</h2>")
    assert ru_page.index("<h2>Озон</h2>") < ru_page.index("<h2>ЕС</h2>")


def test_each_page_says_who_made_it_and_where_to_write():
    eu = {"title": "EU", "title_ru": "ЕС", "currency": "EUR", "lead_lang": "en", "bridge": [], "discrepancies": []}
    en_page = report.render_page([eu], "en")
    ru_page = report.render_page([eu], "ru")
    mail = '<a href="mailto:hello@minihub.app">hello@minihub.app</a>'
    assert "Made by Andrey Karazhev." in en_page and mail in en_page and "Минск" not in en_page
    assert "Сделал Андрей Каражев, Минск." in ru_page and mail in ru_page
    assert en_page.index("<h2>EU</h2>") < en_page.index(mail) < en_page.index("<footer>")


def test_each_page_has_a_title_and_a_description_for_search():
    import html
    import re

    eu = {"title": "EU", "title_ru": "ЕС", "currency": "EUR", "lead_lang": "en", "bridge": [], "discrepancies": []}
    for lang, title, description in (
        ("en", "Why payouts don't match the books — reconciliation demo",
         "Ledger, platform payouts and bank reconciled to the cent for three made-up sellers"),
        ("ru", "Почему выплата маркетплейса не сходится с учётом — демо сверки",
         "Учёт, выплаты маркетплейса и банк сверены до копейки у трёх выдуманных продавцов"),
    ):
        page = report.render_page([eu], lang)
        assert html.unescape(re.search(r"<title>(.*?)</title>", page).group(1)) == title
        meta = re.search(r'<meta name="description" content="([^"]*)">', page)
        assert meta and html.unescape(meta.group(1)).startswith(description)

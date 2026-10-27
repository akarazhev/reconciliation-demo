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
    assert len(explanations) == 19
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


def test_english_page_calls_money_the_platform_took_a_deduction():
    rows = [("operation", "unbooked", "du_1", "charge", Decimal("-45.85"), "short",
             "Platform charge not booked in the ledger.")]
    en = report.render_company_page(company("shop", "en", "Shop A", rows), ALL)
    ru = report.render_company_page(company("seller", "ru", "Seller B", rows, "RUB"), ALL)
    assert "deduction not booked" in en and "<td>deduction</td>" in en and "Platform deduction not booked" in en
    assert "charge" not in en[en.index("<table>"):]
    assert "удержание не проведено" in ru and "<td>удержание</td>" in ru


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
    assert "Сделал Андрей Каражев из Минска. Это мой проект" in ru and mail in ru
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


def test_pages_carry_a_link_preview_with_their_own_address():
    def meta(page, prop):
        return html.unescape(re.search(rf'<meta property="{prop}" content="([^"]*)">', page).group(1))

    pages = {"": report.render_index(ALL, "en"), "ru/": report.render_index(ALL, "ru"),
             f'{EU["slug"]}/': report.render_company_page(EU, ALL), f'{RU["slug"]}/': report.render_company_page(RU, ALL)}
    for path, page in pages.items():
        url = "https://reconciliation.minihub.app/" + path
        assert meta(page, "og:url") == url and f'<link rel="canonical" href="{url}">' in page
        title = html.unescape(re.search(r"<title>(.*?)</title>", page).group(1))
        assert meta(page, "og:title") == title
    for paths, lang in (("", f'{EU["slug"]}/'), "en"), (("ru/", f'{RU["slug"]}/'), "ru"):
        for path in paths:
            assert meta(pages[path], "og:image") == f"https://reconciliation.minihub.app/preview-{lang}.png"
            assert (meta(pages[path], "og:image:width"), meta(pages[path], "og:image:height")) == ("1200", "627")
    assert meta(pages[""], "og:image:alt").startswith("Why payouts don't match")
    assert meta(pages["ru/"], "og:image:alt").startswith("Почему выплаты маркетплейсов")


def test_sitemap_lists_every_page_once():
    import xml.etree.ElementTree as ET
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}
    root = ET.fromstring(report.sitemap(ALL))
    locs = [u.find("s:loc", ns).text for u in root.findall("s:url", ns)]
    site = "https://reconciliation.minihub.app/"
    assert locs == [site, site + "ru/", site + "shop/", site + "seller/"]
    start = root.findall("s:url", ns)[0]
    assert {(link.get("hreflang"), link.get("href")) for link in start.findall("x:link", ns)} == {
        ("en", site), ("ru", site + "ru/"), ("x-default", site)}
    assert root.findall("s:url", ns)[2].findall("x:link", ns) == []


def test_robots_allows_everything_and_names_the_sitemap():
    assert report.ROBOTS == ("User-agent: *\nAllow: /\n\n"
                             "Sitemap: https://reconciliation.minihub.app/sitemap.xml\n")


def test_start_pages_name_each_other_as_language_versions():
    site = "https://reconciliation.minihub.app/"
    for page in (report.render_index(ALL, "en"), report.render_index(ALL, "ru")):
        assert f'<link rel="alternate" hreflang="en" href="{site}">' in page
        assert f'<link rel="alternate" hreflang="ru" href="{site}ru/">' in page
        assert f'<link rel="alternate" hreflang="x-default" href="{site}">' in page
    assert 'hreflang=' not in report.render_company_page(EU, ALL)


def test_each_preview_is_a_1200_by_627_png():
    for lang in report.LANG_TAGS:
        png = (report.ROOT / "preview" / f"{lang}.png").read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n", lang
        assert (int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")) == (1200, 627), lang


def test_pages_share_the_site_icon_and_link_home():
    for page in (report.render_index(ALL, "en"), report.render_company_page(RU, ALL)):
        assert 'rel="icon"' in page and "favicon.svg" in page
        assert '<a href="https://minihub.app">minihub.app</a>' in page


def test_report_names_no_platform():
    # A new company is a row in dbt/seeds/datasets.csv, not a change here.
    source = (report.ROOT / "report.py").read_text(encoding="utf-8")
    for name in ("Stripe", "Ozon", "Wildberries", "Озон"):
        assert name not in source, name


MONTH = {**company("shop/october", "en", "Shop A", ROWS), "opening_from": "shop_set",
         "period_start": "2026-10-01", "period_end": "2026-10-31",
         "rollforward": [
             ("EU-1", "sale", "duplicate", None, "2026-09", Decimal("-50.00"), Decimal("0.00"), Decimal("-50.00"), 2),
             ("du_1", "charge", "unbooked", "unbooked", "2026-09", Decimal("-45.85"), Decimal("30.85"),
              Decimal("-15.00"), 2),
             ("EU-9", "refund", None, "fx", "2026-10", Decimal("0.00"), Decimal("6.59"), Decimal("6.59"), 1),
             ("EU-0", "sale", "duplicate", "missing_at_platform", "2026-09", Decimal("-10.00"), Decimal("10.00"),
              Decimal("0.00"), None)],
         "totals": {"opening": Decimal("-95.85"), "period": Decimal("37.44"), "closing": Decimal("-58.41"),
                    "in_transit_opening": Decimal("3347.78"), "in_transit_closing": Decimal("8598.59")}}


def test_rows_that_continue_a_dataset_become_its_month_pages():
    rows = [{"dataset": "a", "opening_from": "", "slug": "a"},
            {"dataset": "a_oct", "opening_from": "a", "slug": "a/october"},
            {"dataset": "b", "opening_from": "", "slug": "b"}]
    companies, months = report.split_months(rows)
    assert [c["dataset"] for c in companies] == ["a", "b"]
    assert [m["dataset"] for m in months] == ["a_oct"] and companies[0]["months"] == months
    assert companies[1]["months"] == []
    import pytest
    with pytest.raises(ValueError, match="missing"):
        report.split_months([{"dataset": "x", "opening_from": "missing", "slug": "x/october"}])


def test_month_page_rolls_the_last_month_forward():
    page = report.render_month_page(MONTH, ALL)
    for text in ("Open at 30 September", "−€95.85", "Changes in October", "€37.44", "Open at 31 October", "−€58.41",
                 "€3,347.78", "€8,598.59", "currency rate", "deduction", "September", "−€15.00"):
        assert text in page, text
    start = page.index('<table class="rollforward">')
    rollforward = page[start:page.index("</table>", start)]
    # EU-0 closed in October: it counts at the start and among the changes, not at the end
    assert [int(n) for n in re.findall(r'<td class="num">(\d+)</td>', rollforward)] == [3, 3, 3]
    assert "<script" not in page.lower() and '<html lang="en">' in page


def test_month_page_sits_under_its_company():
    page = report.render_month_page(MONTH, ALL)
    assert re.search(r'<a href="../../shop/" aria-current="page">', page)
    assert 'href="../../favicon.svg"' in page
    assert '<link rel="canonical" href="https://reconciliation.minihub.app/shop/october/">' in page
    parent = report.render_company_page({**EU, "months": [MONTH]}, ALL)
    assert 'href="../shop/october/"' in parent
    assert 'october/' not in report.render_company_page(RU, ALL)


def test_month_page_shows_how_long_each_line_is_open():
    page = report.render_month_page(MONTH, ALL)
    start = page.index("<h2>Lines</h2>")
    table = page[start:page.index("</table>", start)]
    assert '<th class="num">Months open</th>' in table
    rows = re.findall(r"<tr><td>(EU-[019]|du_1)</td>.*?</tr>", table)
    assert rows == ["EU-1", "du_1", "EU-9", "EU-0"]
    cells = {key: re.search(rf"<tr><td>{key}</td>(.*?)</tr>", table).group(1) for key in rows}
    assert '<td class="num">2</td>' in cells["EU-1"] and '<td class="num">1</td>' in cells["EU-9"]
    assert '<td class="num"></td>' in cells["EU-0"]


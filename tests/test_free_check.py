import re
import xml.etree.ElementTree as ET

import free_check
import report

from test_report import ALL


def visible_text(page: str) -> str:
    body = page.split("<main>", 1)[1]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


def test_page_is_russian_at_its_own_address():
    page = free_check.render()
    assert page.startswith('<!doctype html><html lang="ru">')
    assert '<link rel="canonical" href="https://reconciliation.minihub.app/ru/proverka/">' in page
    assert "<h1>Проверка выплат Wildberries и Ozon за месяц</h1>" in page


def test_page_says_when_checks_start_and_where_to_write():
    text = visible_text(free_check.render())
    assert "проверки делаю с 19 ноября" in text
    assert "hello@minihub.app" in text
    assert "Минск, удалённо" in text


def test_page_links_the_demo_but_the_demo_does_not_link_back():
    page = free_check.render()
    assert 'href="https://reconciliation.minihub.app/ru/"' in page
    assert "proverka" not in report.render_index(ALL, "ru")


def test_page_has_no_long_dashes():
    assert "—" not in visible_text(free_check.render())


def test_sitemap_lists_the_page():
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(report.sitemap(ALL, extra=free_check.page_paths()))
    locs = [u.find("s:loc", ns).text for u in root.findall("s:url", ns)]
    assert "https://reconciliation.minihub.app/ru/proverka/" in locs

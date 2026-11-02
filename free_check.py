"""Write the free payout check page, in Russian, no JavaScript:

    site/ru/proverka/index.html   what a Wildberries or Ozon seller sends, what comes back, how the files are handled

report.py lists the page in sitemap.xml (page_paths). The start pages do not link here: the page is shared only where
sellers ask about payouts, and it links to the demo, not the other way round.
"""
import html

import report

ROOT = report.ROOT
PATH = "ru/proverka/"
TITLE = "Проверка выплат Wildberries и Ozon за месяц"
DESCRIPTION = ("Бесплатно сверю отчёт Wildberries или Ozon за месяц с поступлениями в банке и учётом и скажу, сколько "
               "не сходится и из-за чего.")
DEMO = report.SITE + "ru/"
PARAGRAPHS = (
    "Если деньги от маркетплейса не сходятся с тем, что видно в учёте и в банке, пришлите выгрузки за один месяц. "
    "Я сверю отчёт площадки, поступления на счёт и учёт и скажу, сколько не сходится и из-за чего. Бесплатно.",
    "Заявки принимаю сейчас, проверки делаю с 19 ноября.",
    "<b>Что прислать.</b> Отчёт площадки за месяц так, как он скачивается из кабинета: у Wildberries еженедельные "
    "отчёты о реализации с детализацией, у Ozon начисления и отчёт о реализации. Выписку банка за тот же месяц и ещё "
    "неделю после, в любом формате. Если учёт ведёте в МоемСкладе или 1С, выгрузку продаж и поступлений за этот "
    "месяц. Можно и без учёта, тогда сверю площадку с банком.",
    "<b>Что получите.</b> Общую разницу и то, из чего она складывается: удержания за прошлые периоды, возвраты, "
    "комиссии и логистика, выплаты, которые ещё не дошли до банка, ошибки в учёте. По каждой причине сумму и число "
    "случаев. Без списка строк, это уже платная работа. Обычно за несколько дней. Беру не больше двух проверок в "
    "неделю.",
    "<b>Как обращаюсь с данными.</b> Только читаю. Никому не передаю. Файлы удаляю после проверки. Обезличенный "
    "итог показываю другим только с вашего согласия.",
    "<b>Что дальше.</b> Если нужно разобрать каждую строку и поправить обмен или учёт, это работа по фиксированной "
    "цене от 15&nbsp;000&nbsp;₽, оплата после результата. Ежемесячная проверка отдельно, после первой работы.",
    f'Как это выглядит, можно посмотреть <a href="{DEMO}">в демо на выдуманных данных</a>.',
)
CONTACT = 'Андрей Каражев, Минск, удалённо. <a href="mailto:hello@minihub.app">hello@minihub.app</a>'


def page_paths() -> list[str]:
    return [PATH]


def render() -> str:
    body = "".join(f"<p>{p}</p>" for p in PARAGRAPHS)
    return (report.head("ru", TITLE, DESCRIPTION, "../../", PATH)
            + f"<h1>{html.escape(TITLE)}</h1>{body}<p class=\"author\">{CONTACT}</p></main></body></html>\n")


def main() -> None:
    path = ROOT / "site" / PATH / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(), encoding="utf-8")
    print(f"written {path}")


if __name__ == "__main__":
    main()

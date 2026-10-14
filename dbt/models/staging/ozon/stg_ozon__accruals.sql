{{ config(enabled = var('platform') == 'ozon') }}
-- The report has no line id: a surrogate from the line's own fields, numbered among identical lines.
with raw as (
    select
        "Дата начисления" as accrued_on,
        trim("Тип начисления") as accrual_type,
        nullif(trim("Номер отправления"), '') as posting_number,
        nullif(trim("Артикул"), '') as article,
        "Количество" as quantity,
        "Сумма итого, руб." as amount
    from read_csv('{{ data_file("ozon_report.csv") }}', header = true, delim = ';', decimal_separator = ',',
                  dateformat = '%d.%m.%Y', columns = {
        'Дата начисления': 'DATE', 'Тип начисления': 'VARCHAR', 'Номер отправления': 'VARCHAR',
        'Артикул': 'VARCHAR', 'Количество': 'INTEGER', 'Сумма итого, руб.': 'DECIMAL(18,2)'})
)
select
    'oz-' || md5(concat_ws('|', accrued_on, accrual_type, coalesce(posting_number, ''), coalesce(article, ''), amount))
        || '-' || row_number() over (
            partition by accrued_on, accrual_type, posting_number, article, amount order by accrued_on) as line_id,
    *
from raw

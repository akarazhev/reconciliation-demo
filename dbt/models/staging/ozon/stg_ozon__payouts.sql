{{ config(enabled = var('platform') == 'ozon') }}
select
    "Номер выплаты" as payout_id,
    "Дата выплаты" as paid_on,
    "Период с" as period_from,
    "Период по" as period_to,
    "Сумма, руб." as amount,
    'RUB' as currency
from read_csv('{{ data_file("ozon_payouts.csv") }}', header = true, delim = ';', decimal_separator = ',',
              dateformat = '%d.%m.%Y', columns = {
    'Номер выплаты': 'VARCHAR', 'Период с': 'DATE', 'Период по': 'DATE', 'Дата выплаты': 'DATE',
    'Сумма, руб.': 'DECIMAL(18,2)'})

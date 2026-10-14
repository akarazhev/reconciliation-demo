{{ config(enabled = var('platform') == 'wb') }}
-- One weekly realization report is one payout: its total payable, paid on the payment date.
select
    realizationreport_id as payout_id,
    payment_date as paid_on,
    date_from as period_from,
    date_to as period_to,
    total_payable as amount,
    'RUB' as currency
from read_csv('{{ data_file("wb_reports.csv") }}', header = true, columns = {
    'realizationreport_id': 'VARCHAR', 'date_from': 'DATE', 'date_to': 'DATE', 'create_dt': 'DATE',
    'payment_date': 'DATE', 'total_payable': 'DECIMAL(18,2)'})

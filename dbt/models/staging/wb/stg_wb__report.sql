{{ config(enabled = var('platform') == 'wb') }}
select
    rrd_id,
    realizationreport_id,
    date_from,
    date_to,
    rr_dt,
    nullif(trim(srid), '') as srid,
    nm_id,
    nullif(trim(sa_name), '') as sa_name,
    nullif(trim(doc_type_name), '') as doc_type_name,
    trim(supplier_oper_name) as supplier_oper_name,
    quantity,
    retail_price_withdisc_rub,
    ppvz_for_pay,
    delivery_rub,
    storage_fee,
    penalty,
    deduction,
    currency_name
from read_csv('{{ data_file("wb_report.csv") }}', header = true, columns = {
    'rrd_id': 'VARCHAR', 'realizationreport_id': 'VARCHAR', 'date_from': 'DATE', 'date_to': 'DATE',
    'rr_dt': 'DATE', 'srid': 'VARCHAR', 'nm_id': 'BIGINT', 'sa_name': 'VARCHAR', 'doc_type_name': 'VARCHAR',
    'supplier_oper_name': 'VARCHAR', 'quantity': 'INTEGER', 'retail_price_withdisc_rub': 'DECIMAL(18,2)',
    'ppvz_for_pay': 'DECIMAL(18,2)', 'delivery_rub': 'DECIMAL(18,2)', 'storage_fee': 'DECIMAL(18,2)',
    'penalty': 'DECIMAL(18,2)', 'deduction': 'DECIMAL(18,2)', 'currency_name': 'VARCHAR'})

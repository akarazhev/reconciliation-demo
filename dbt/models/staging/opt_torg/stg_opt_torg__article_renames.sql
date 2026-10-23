{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
-- Article codes renamed in 1C, under the generic names the shared checks read.
select
    old_article as old_value,
    new_article as new_value,
    timezone('UTC', renamed_at) as renamed_at
from read_csv('{{ data_file("source_article_renames.csv") }}', header = true, columns = {
    'old_article': 'VARCHAR', 'new_article': 'VARCHAR', 'renamed_at': 'TIMESTAMPTZ'})

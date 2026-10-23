{{ config(enabled = var('suite', 'recon') == 'load' and var('dataset') == 'opt_torg', tags = ['load_check']) }}
-- When each export run started: a row of the target got the time of the run that last wrote it.
select
    export_night,
    run as export_run,
    timezone('UTC', started_at) as exported_at
from read_csv('{{ data_file("export_runs.csv") }}', header = true, columns = {
    'export_night': 'DATE', 'run': 'INTEGER', 'started_at': 'TIMESTAMPTZ'})

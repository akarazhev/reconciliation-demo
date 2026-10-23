# Money reconciliation demo

[![check](https://github.com/akarazhev/reconciliation-demo/actions/workflows/check.yml/badge.svg)](https://github.com/akarazhev/reconciliation-demo/actions/workflows/check.yml)

Three made-up companies close September 2026, and their books don't match what the payment platform paid
out or what reached the bank. The demo walks each gap level by level until every difference has a cause and
an amount, down to the cent.

- an EU web shop selling through Stripe
- an Ozon seller
- a Wildberries seller

I planted the discrepancies myself and listed them in `data/<company>/truth.csv`. The run fails unless the
SQL finds exactly those, each once. The data is fictional, and the demo isn't affiliated with Stripe, Ozon
or Wildberries.

Live: https://reconciliation.minihub.app · Write-up: https://dev.to/akarazhev/why-stripe-payouts-dont-match-your-books-3aoa

A second demo, the load check, is described [below](#load-check): https://reconciliation.minihub.app/migration/ · https://reconciliation.minihub.app/ru/vygruzka/

## Run it

```sh
./run.sh
```

You need `uv`; it installs Python and dbt. The script generates the data, runs one dbt build per company and
writes a static site to `site/`: English and Russian start pages, one page per company and the dbt docs.
Cloudflare serves `site/` straight from `main`.

## How it works

Everything is SQL in dbt on DuckDB, amounts are `DECIMAL(18,2)`. There are four levels:

1. **Operation.** Ledger lines against platform lines, matched by key and kind. Whatever doesn't pair up
   gets a cause: duplicate, missing on one side, unbooked deduction, fee, partial refund, and two hypotheses
   that need a human look, FX and amount mismatch.
2. **Payout.** Each payout against the lines it says it contains.
3. **Bank.** Each payout against the bank statement, by the payout id in the reference or by a unique amount
   within five days. A September payout that lands in October is "in transit".
4. **Bridge.** The differences found on each level must add up exactly from the ledger to the bank. If they
   don't, the run fails.

## What it finds

| Company | Discrepancies | Short | Over | In transit |
|---|---:|---:|---:|---:|
| EU web shop (Stripe) | 18 | €684.51 | €535.30 | €3,347.78 |
| Ozon seller | 17 | ₽3,727.75 | ₽12,491.34 | ₽233,374.32 |
| Wildberries seller | 15 | ₽9,559.65 | ₽8,158.07 | ₽81,521.28 |

## Adding a format

Ozon and Wildberries were added without touching the shared logic. Each got its own staging folder and a
small table that maps its operations to the common kinds. To see it, compare the commits before and after
each addition:

```sh
./check_repeatability.sh
./check_repeatability.sh wb-baseline wb-added
```

## What is assumed

- Stripe columns follow its public itemized payout reconciliation report and Payout object. Schedules, fees
  and rates are made up.
- The Ozon and Wildberries formats are my assumptions. I couldn't read their seller documentation in October
  2026, so field names, operation types and payout dates still need checking against real exports:
  - Ozon, six columns: accrual date, accrual type, posting number, article, quantity, amount in RUB.
  - Wildberries, fields of the seller API realization report: `rrd_id`, `realizationreport_id`, `srid`,
    `supplier_oper_name`, `retail_price_withdisc_rub`, `ppvz_for_pay`, `delivery_rub`, `storage_fee`,
    `penalty`, `deduction`.
- One month and one currency per company, and nothing is on the platform balance on 1 September.

## Load check

The second demo checks a load after it ran, in two made-up cases:

- a subscription company moves customers, invoices and payments for July to September 2026 to a new billing
  database, in batches of 500 payments;
- a wholesale company exports invoices, their lines and payments from 1C to MySQL every night.

Shared dbt macros in `dbt/macros/load_check` compare the two sides table by table, as
`dbt/seeds/load/load_config.csv` describes them: rows on one side only, values that differ, control totals by
month. Each difference gets the first cause that fits, and a bridge walks the source to the target month by
month. I planted the differences myself, 112 in the migration and 91 in the export, and the run fails unless the
SQL finds exactly those, listed in `data/<dataset>/truth.csv`.

`./run.sh` builds this demo too. It also runs as an Airflow Dag, in its own environment:

```sh
uv venv .venv-airflow --python 3.13
uv pip install --python .venv-airflow/bin/python -r airflow/requirements.txt --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.3.2/constraints-3.13.txt
export TZ=UTC AIRFLOW_HOME=$PWD/.airflow AIRFLOW__CORE__DAGS_FOLDER=$PWD/airflow/dags AIRFLOW__CORE__LOAD_EXAMPLES=False
.venv-airflow/bin/airflow db migrate
.venv-airflow/bin/airflow dags test load_check
```

What is assumed: one DuckDB database stands in for both systems in each case. The old billing database, 1C and
MySQL are imitated by how they behave, not by their real files: manual payments kept in local time without an
offset, an export that picks documents by date, a lines table without a unique key.

## Adding a dataset to the load check

The 1C export was added as configuration rows and its own staging models, with one change to the shared code: a
line inside a document read the document's modification time on both sides, while only the source keeps it. To
see what the second dataset changed in the shared folders:

```sh
git diff --stat load-en-only load-ru-added -- dbt/macros/load_check dbt/models/load dbt/tests/load
```

## Tests

`uv run pytest -q` covers both demos: the generators, the planted causes and the pages. The dbt build runs its own unit
tests, and the self-check compares what was found with `truth.csv`. CI runs the build, the tests and the Dag on
every push and checks that they write exactly the files in the repository.

## License

MIT. The data is fictional.

I built this as a side project about data that moves between systems and quietly stops matching.
Questions: hello@minihub.app

# Money reconciliation demo

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

## Tests

`uv run pytest -q` covers the generator, the planted causes and the page. The dbt build runs its own unit
tests, and the self-check compares what was found with `truth.csv`.

## License

MIT. The data is fictional.

I built this as a side project about data that moves between systems and quietly stops matching.
Questions: hello@minihub.app

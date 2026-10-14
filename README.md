# Money reconciliation demo

Two made-up companies, September 2026. The books (ledger) are reconciled against a payment platform,
its payouts and the bank statement, and every difference gets a cause and an amount to the cent.

- **EU web shop** — card payments through Stripe; the platform file follows Stripe's
  "Itemized payout reconciliation" report and the Payout object.
- **Ozon seller** — a marketplace seller using a simplified accrual detail layout. Its exact fields
  and payout schedule remain demo assumptions pending documentation verification.

The discrepancies were planted on purpose and listed in `data/<company>/truth.csv`; the run fails unless SQL
finds exactly those, once each. Data is fictional; Stripe columns follow public documentation, Ozon uses the assumptions below, and the demo is
not affiliated with Stripe or Ozon. It shows a method, not industry experience.

## Run

```sh
./run.sh
```

Needs `uv`; Python 3.13 and dbt are installed by `uv sync`. The result is `site/index.html` (no JavaScript)
and `site/docs/` (dbt docs).

## How it works

Four levels, all in SQL (dbt + DuckDB), amounts as `DECIMAL(18,2)`:

1. **Operation** — ledger lines against platform lines inside a pair (key, kind). Exact pairs are taken by
   count first; the cause comes from the whole remainder: duplicate, missing in the ledger or on the
   platform, unbooked charge, fee, partial refund, FX (a hypothesis), amount mismatch (a hypothesis, with a
   hint when the digits are transposed).
2. **Payout** — the declared payout against the sum of its lines.
3. **Bank** — by the payout id in the reference, or by a unique amount within five days; ambiguous pairs are
   not matched automatically. A September payout booked in October is "in transit".
4. **Bridge** — ledger + operation differences = platform; + payout differences = payouts; + bank
   differences = bank.

Checks: the customer checks warn and store what they found; the bridge, payout totals and causes are
invariants and fail the run; the self-check compares every found discrepancy with `truth.csv`.

## Results

- **EU web shop, Stripe payouts** — September 2026: 18 discrepancies, €684.51 short, €535.30 over, €3,347.78 in transit
- **Ozon seller, marketplace payouts** — September 2026: 17 discrepancies, ₽3,727.75 short, ₽12,491.34 over, ₽233,374.32 in transit

## Repeatability

The second company was added as one staging folder and one mapping table; `core` and `recon` did not change.
`./check_repeatability.sh` proves it against the tag `stripe-only`.

Added/deleted lines measured immediately after adding Ozon (Task 10):

```text
21	0	check_repeatability.sh
13	0	dbt/models/staging/ozon/_ozon.yml
21	0	dbt/models/staging/ozon/stg_ozon__accruals.sql
14	0	dbt/models/staging/ozon/stg_ozon__lines.sql
12	0	dbt/models/staging/ozon/stg_ozon__payouts.sql
1	0	dbt/seeds/datasets.csv
7	0	dbt/seeds/kind_map_ozon.csv
2	2	generate.py
181	0	generator/ozon_seller.py
37	0	tests/test_generator.py
```

Measured dbt build times from the first full two-company run:

```text
eu_shop: 14 s
ozon_seller: 4 s
```

Manual exceptions to the shared logic: **0**. These timings include both datasets' unit tests and
structural checks. The generator, HTML renderer and dbt documentation build run once outside those timings.
Two consecutive `./run.sh` runs produced identical SHA-256 hashes for the HTML report and all ten CSV files.

## Assumptions

- Each payout carries operations of one month; nothing is on the platform balance on 1 September.
- Stripe's report columns and monetary units were checked against the [itemized payout reconciliation
  report](https://docs.stripe.com/reports/payout-reconciliation); the payout CSV is a projection of the
  [Payout object](https://docs.stripe.com/api/payouts/object), with amounts in integer cents and UTC epoch
  timestamps. The daily payout schedule, settlement timing, fee rates and USD conversion rate are fictional.
- Ozon documentation was not confirmed on 14 October 2026: [robots.txt](https://docs.ozon.ru/robots.txt)
  returned HTTP 307 to the same URL with `__rr=1`; the web reader reported a redirect loop. Reading stopped.
  None of the exact layout, type names, line ID availability or payout dates below is presented as verified:
  - The six columns are accrual date, accrual type, posting number, article, quantity and total RUB amount.
    Semicolon separation, decimal commas and `dd.mm.yyyy` dates are chosen for this demo.
  - Types are sale, return, sales commission, logistics, storage and fine; their Russian labels and the
    fixed 15%/17% commission rates are assumptions.
  - There is no source line ID in the synthetic file. Staging hashes the date, type, posting, article and
    amount, then numbers identical rows; storage and fines use `code:date` in the books.
  - Payouts on 16 September and 1 October cover 1–15 and 16–30 September; bank posting is on the next day.
  These fields and dates need manual checking against [Ozon Seller documentation](https://docs.ozon.ru/).
- SQL is tested on DuckDB; it is written to stay close to standard SQL.

## Validation

`uv run pytest -q` checks deterministic generation, report escaping, exact discovered/planted causes,
Ozon decimal parsing, and rejection of unknown Stripe categories even at zero amount. The full build
also runs five dbt unit tests, including `[100, 100]` versus `[100, 90]`, all operation and bank rules,
the transposition explanation and full payout identifier matching (`po_1` cannot match `po_10`).

Customer warnings are intentional: Stripe has 12 ledger exceptions, 5 charge/fee exceptions and 1 payout
in transit; Ozon has 8, 8 and 1. Structural checks, truth uniqueness/counts/row comparison and all three
bridge equations must pass with no errors. A duplicated truth row fails the self-check.

Before the `stripe-only` baseline, two defects in the supplied implementation were reproduced and fixed:
zero-amount unknown categories must fail before filtering, and payout IDs in bank references must match
a full token. This adds two pytest cases and one dbt unit test; the planned reconciliation rules are retained.

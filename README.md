# Money reconciliation demo

Three made-up companies, September 2026. The books (ledger) are reconciled against a payment platform,
its payouts and the bank statement, and every difference gets a cause and an amount to the cent.

- **EU web shop** — card payments through Stripe; the platform file follows Stripe's
  "Itemized payout reconciliation" report and the Payout object.
- **Ozon seller** — a marketplace seller using a simplified accrual detail layout. Its exact fields
  and payout schedule remain demo assumptions pending documentation verification.
- **Wildberries seller** — a marketplace seller whose file follows the field names of the realization
  report in the seller API (one row, several amounts); weekly reports are cut at month end, and the exact
  fields remain demo assumptions pending documentation verification.

The discrepancies were planted on purpose and listed in `data/<company>/truth.csv`; the run fails unless SQL
finds exactly those, once each. Data is fictional; Stripe columns follow public documentation, Ozon and
Wildberries use the assumptions below, and the demo is not affiliated with Stripe, Ozon or Wildberries.
It shows a method, not industry experience.

Made by Andrey Karazhev as a side project about data that moves between systems and quietly stops
matching. Contact: hello@minihub.app

## Run

```sh
./run.sh
```

Needs `uv`; Python 3.13 and dbt are installed by `uv sync`. The result is a static site without JavaScript:
start pages `site/index.html` (English) and `site/ru/index.html` (Russian), one page per company in its
audience's language — `site/stripe/` (English), `site/ozon/` and `site/wb/` (Russian) — joined by the same tabs
on every page, and `site/docs/` (dbt docs). A company's address, tab, language, headings and search description
come from `dbt/seeds/datasets.csv`.

`site/` is committed: Cloudflare serves it as static files from `main` (`wrangler.jsonc`), with no build
step. To update the published page, run `./run.sh` and commit `site/`.

The link preview of the English pages is `preview/en.png`, a 1200×627 screenshot of `preview/en.html`;
its figures are typed in by hand, so a change in the EU web shop data means a new screenshot.
`report.py` copies it to `site/preview-en.png`.

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
- **Wildberries seller, weekly reports cut at month end (demo assumption)** — September 2026: 15 discrepancies, ₽9,559.65 short, ₽8,158.07 over, ₽81,521.28 in transit

## Repeatability

Adding Ozon required no changes to shared logic. At the Ozon commit (`dc9bb5f`), `core`, `recon`,
macros, SQL tests, `run.sh` and `report.py` are identical to the original Stripe baseline,
`stripe-only-initial`. Ozon adds its own staging folder and type mapping; the generator, dataset
registration and other additions are listed below.

After Ozon was added, review found two shared matching bugs: bank references needed uniqueness on both
sides, and FX evidence needed to come from the unmatched remainder. Commit `3106770` fixed them in
shared `recon` for both companies. The same fixes were tested on a separate Stripe-only branch,
now tagged `stripe-only` (`eec2435`). Neither bug is exercised by the synthetic Ozon dataset: its bank
references contain no payout IDs, and its payments use one currency.

`./check_repeatability.sh` compares two commits, not the working tree: by default `stripe-only-initial`
with `ozon-added` (`dc9bb5f`), and it passes. Shared code that changed later is listed by
`./check_repeatability.sh stripe-only-initial HEAD`: the review fixes above (three `recon` files, +54 / -7
lines, including regression tests) and the Russian page in `report.py`, which also made the page texts
platform-neutral so that a further company needs no change there. On 15 October `report.py` gained an
author line, page titles and search descriptions, and `run.sh` began building the published dbt docs with
a relative root, so that no local path ends up in them; neither change touches reconciliation. On 16 October
the site was split into one page per company with tabs, and the per-company texts moved to `datasets.csv`, so
`report.py` again names no platform (a test checks it).

Added/deleted lines measured immediately after adding Ozon (Task 10), against the initial Stripe baseline:

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

The third company, Wildberries, was added the same way and checked the same way: `wb-baseline` is the commit
just before it (`018d99a`, after the Russian page), `wb-added` the commit that adds it (`732a2ba`).
`./check_repeatability.sh wb-baseline wb-added` passes. Its format differs from both earlier ones — one row
carries several amounts, split into lines by the mapping table, as Stripe's gross and fee are — and still
needed no change in shared logic (measured at `wb-added`; a later review added two mapping rows and a guard
in Wildberries staging, commit `052f3c4`, and `./check_repeatability.sh wb-baseline 052f3c4` still passes;
the page and docs changes of 15 October, listed above, come after it):

```text
42	0	dbt/models/staging/wb/_wb.yml
37	0	dbt/models/staging/wb/stg_wb__lines.sql
12	0	dbt/models/staging/wb/stg_wb__payouts.sql
26	0	dbt/models/staging/wb/stg_wb__report.sql
1	0	dbt/seeds/datasets.csv
8	0	dbt/seeds/kind_map_wb.csv
6	2	generate.py
204	0	generator/wb_seller.py
59	0	tests/test_generator.py
```

Measured dbt build times, second of two full runs:

```text
eu_shop: 4 s
ozon_seller: 5 s
wb_seller: 4 s
```

Manual exceptions to shared logic for adding Ozon: **0**; for adding Wildberries: **0**. These timings include
each dataset's unit tests and structural checks. The generator, HTML renderer and dbt documentation build run
once outside those timings. Two consecutive `./run.sh` runs produced identical SHA-256 hashes for all five HTML
pages, the icon and all fifteen CSV files (remeasured on 16 October; the dbt docs page carries its build time).

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
- Wildberries documentation was not confirmed on 14 October 2026: `dev.wildberries.ru` answered
  `robots.txt` with HTTP 498 (bot protection), and the former `openapi.wildberries.ru` no longer resolves.
  Reading stopped. None of the following is presented as verified:
  - Field names follow the seller API's realization report (`reportDetailByPeriod`, v5): `rrd_id` (line ID),
    `realizationreport_id` (report = payout), `srid` (order), `supplier_oper_name` (operation),
    `retail_price_withdisc_rub`, `ppvz_for_pay`, `delivery_rub`, `storage_fee`, `penalty`, `deduction`.
  - Operations are sale, return, logistics, storage, fine and deduction. A sale gives the retail price and a
    commission of `ppvz_for_pay` minus retail, and logistics if `delivery_rub` is on the same row; a return
    withholds `ppvz_for_pay`, net: its retail price is shown but moves no money, which the mapping marks
    with sign 0. The 20%/25% commission rates are fictional. Rows without `srid` use `code:date` in the books.
    A non-zero amount that the mapping does not cover for its operation stops the run with the operation and
    the column, so nothing is lost silently.
  - The two planted `partial` returns are a scenario of this demo: the books refund the retail price while
    WB withholds the net `ppvz_for_pay`, so the platform took back less than the books say. It is not a
    measured pattern of real sellers.
  - Real WB weeks run Monday to Sunday and cross months. Here the first report covers 1–6 September and the
    last 28–30 September, paid on 2 October; one report is one payout. The payment date (the Tuesday after a
    week) and a bank reference that names the report number are demo choices. A third-party service says
    storage and paid acceptance do not come in this API report; if so, they need a second source.
  These fields and dates need manual checking against the Wildberries seller documentation.
- SQL is tested on DuckDB; it is written to stay close to standard SQL.

## Validation

`uv run pytest -q` checks deterministic generation, report escaping, exact discovered/planted causes,
Ozon decimal parsing, the Wildberries report totals, and rejection of unknown Stripe categories even at zero
amount. The full build also runs seven shared dbt unit tests, including `[100, 100]` versus `[100, 90]`, all operation and bank rules,
the transposition explanation, full payout identifiers (`po_1` cannot match `po_10`), ambiguous
references and domestic residuals following an exactly matched foreign-currency payment. The Wildberries
build adds two staging unit tests, both fed the real mapping table (a pytest case keeps them equal to the
seed): a sale of 1 000 with 850 for the seller and logistics of 100 gives sale +1000, fee −150 and charge
−100, a payout of 750, whether the logistics comes on its own row or on the sale row itself — the commission
is not subtracted twice and the logistics is not lost.

Customer warnings are intentional: Stripe has 12 ledger exceptions, 5 charge/fee exceptions and 1 payout
in transit; Ozon has 8, 8 and 1; Wildberries has 6, 8 and 1. Structural checks, truth uniqueness/counts/row comparison and all three
bridge equations must pass with no errors. A duplicated truth row fails the self-check.

Before the initial Stripe baseline, two defects in the supplied implementation were reproduced and fixed:
zero-amount unknown categories must fail before filtering, and payout IDs in bank references must match
a full token. This adds two pytest cases and one dbt unit test; the planned reconciliation rules are retained.

The fresh final review found two further shared matching defects: reference candidates needed uniqueness
on both sides, and already matched foreign-currency payments must not label a domestic remainder as FX.
Both were reproduced by failing dbt unit tests, fixed on a separate Stripe-only branch, and applied to
the full demo. Conflicting references stay ambiguous even if one amount matches exactly.

The original Stripe baseline remains at `stripe-only-initial` (`0ef846a`). The `stripe-only` tag now points
to the independently tested, corrected Stripe-only baseline (`eec2435`), which contains no Ozon generator
or staging. No commit history was rewritten. The default repeatability check is historical: it compares
`stripe-only-initial` with the Ozon commit, tagged `ozon-added`:

```sh
./check_repeatability.sh
```

It reports no difference in shared logic. Generic review corrections are recorded separately from
platform-specific additions.

## License

MIT, see [LICENSE](LICENSE). The data is fictional.

## Scope decisions

Bank reference IDs are matched as complete tokens of letters, digits, underscores or hyphens, as used by
the synthetic inputs. A new identifier format would need a parser change. dbt usage statistics are disabled,
and local test/dbt metadata stays out of Git; neither affects reconciliation amounts.

Each dataset uses one settlement currency and one operating month. General multi-month or multi-currency
imports need additional staging and period design. For this September bridge, a matched October receipt
is classified as `in_transit` even if its amount differs: an October amount difference needs checking in
that later period. Exact Ozon and Wildberries export fidelity remains an assumption until the manual source
check; Wildberries weeks that cross a month would need a payout split between periods, which this demo
avoids by cutting the reports.

Automated acceptance passed: 36 pytest cases, seven shared dbt unit tests per dataset plus two Wildberries
staging tests, no build errors, and identical CSV and page hashes across two final rebuilds. The browser runtime had no available browser; the
founder's visual/privacy review, public repository and publishing remain pending.

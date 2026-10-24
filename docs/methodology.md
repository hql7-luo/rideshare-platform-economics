# Methods and table guide

The analytical population is Uber (`HV0003`) and Lyft (`HV0005`) trips in the NYC TLC High Volume FHV files. Each row is a reported trip, not a unique rider. Juno, Via and unknown licenses remain in the raw-row audit but are excluded from business metrics. Market share means share of **Uber plus Lyft** trips. Airport trips may include Newark, outside New York City.

## Cleaning

Keep base fare greater than zero, nonnegative driver pay, distance above zero and no more than 100 miles, reported trip time from 60 through 14,400 seconds, and pickup within the file's calendar month. These are eligibility rules, not proof that every retained row is accurate. No duplicate removal is attempted: there is no reliable trip identifier. All dollars are nominal.

Wait time is pickup minus request. A wait from zero through 60 minutes enters the mean; an invalid or missing wait excludes only that wait observation, not the trip. The public tables preserve `wait_trips` as its separate denominator. Timestamps follow the source's local wall-clock convention; no timezone conversion is applied.

Missing historical optional numeric fee columns are zero-filled. Existing null optional fee values are also zero-filled. Core fare, pay, distance and duration fields must exist. Missing request timestamps produce unavailable waits. The manifest lists zero-filled missing columns for each month.

## Metrics

| Metric | Formula after aggregation |
|---|---|
| Gross platform take | Sum(base fare) − Sum(driver pay) |
| Gross take per trip | Gross take / trip count |
| Gross take rate | Gross take / Sum(base fare) |
| Mean fare or pay | Sum(fare or driver pay) / trip count |
| Fare per mile | Sum(base fare) / Sum(trip miles) |
| Trip speed, mph | 60 × Sum(miles) / Sum(minutes) |
| Mean wait | Sum(valid waits) / count(valid waits) |
| Negative-take trip share | Count(driver pay > base fare) / trip count |
| Recorded passenger total | Base fare + tips + tolls + BCF + sales tax + NYS surcharge + airport fee + CBD fee |

This is a ratio-of-sums take rate, not an average of individual trip percentages. Speed is distance divided by total passenger trip time, not average individual speeds or vehicle-network speed. The recorded passenger total is an additive proxy from reported fields, not a receipt reconciliation. Zero denominators remain missing.

Take excludes tips, tolls, taxes and fees. It is **gross, not profit**: insurance, payment fees, marketing, discounts and incentives are not fully observable. Driver pay excludes tips and tolls and is before drivers' operating costs. A negative fare-minus-pay amount does not establish a net loss or a regulatory violation.

## Segments and periods

Distance bins are `(0,1]`, `(1,2]`, `(2,3]`, `(3,5]`, `(5,10]`, `(10,20]`, and `(20,100]` miles. Airport-linked trips have either endpoint in TLC zones 1, 132 or 138. Weekday is Monday=0 through Sunday=6, and hour is the pickup hour. Recent snapshots pool the most recent 12 complete calendar months; rates are recalculated from totals. Borough and zone summaries refer to pickup locations. Unknown lookup values remain visible.

The monthly builder downloads a single file, runs the SQL, saves small atomic checkpoints and removes that raw file. `data/processed/manifest.json` records observed coverage, URLs, hashes, row counts, missing columns and run time. Completed summaries are reused when rerunning, including after a fresh clone. If projected full-history downloads exceed two hours, historical coverage falls back to one month per quarter in 2019–2022 (February for the first 2019 quarter); all months from 2023 remain. The manifest and README disclose the actual mode. Quarterly samples are never expanded into estimated annual trip counts.

## Congestion comparison

The inferred zone set uses clean pooled Uber/Lyft trips in **February 2025**, the first full charge month. A pickup zone is included only if its official lookup borough is **Manhattan**, it has **at least 1,000** eligible pickups that month, and **more than 95%** have a positive `cbd_congestion_fee`. This fixed zone set is applied to all comparison months from January 2024 onward. Its detailed numerator, denominator and inclusion decision are committed in `inferred_cbd_zones.csv`; the rule and included IDs are also recorded in `data/results/key_numbers.json`. It is an empirical proxy, not a legal boundary map.

Zone-linked means either pickup or drop-off is in that fixed set. Other trips can still pass through the charging area, which contaminates the comparison group. January 2025 is excluded. For each available February–December 2025 month, compare the same 2024 month. Pooled comparisons sum the matched months before calculating means and rates.

The results retain both absolute differences-in-differences and differences in percentage changes. Take-rate changes use percentage points. Other percentage changes equal `100 × (2025 / 2024 − 1)`, and the descriptive gap subtracts Other growth from Zone-linked growth. These are **not causal effects**. Parallel trends are not established, and trip mix, pricing, minimum-pay adjustments, weather, economic conditions and taxi dispatch shifts can change the result. The charge's legal payer is the passenger; ultimate economic burden cannot be identified from this comparison.

## Historical growth and convergence

Fare and pay growth compare each company's mean dollars per trip in February 2019 with the latest month, using each metric's own starting value. Uber's unusually low early gross take makes these endpoint comparisons sensitive to the first month's fare/pay relationship. A low starting take rate does not itself prove later pricing power. The observed take-rate range since January 2024 uses every available monthly company rate, not a pooled multiyear rate. These endpoints and ranges are recorded in `baseline` and `convergence` in `data/results/key_numbers.json`.

## Files

`monthly`, `distance`, `hourly`, `airport`, `pickup_zone`, and `congestion` CSVs in `data/processed/` retain additive numerators at their respective monthly grain. `audit.csv` contains pre-cleaning and retained row counts. `data/results/` contains ready-to-read rates, matched-period comparisons, validation and `key_numbers.json`. The README, memo, figures and embedded explorer are generated from those results.

See [sources and policy definitions](sources.md) for the UCLA comparison, pay rules, charge rules and the external raw-row benchmark.

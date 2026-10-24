# Sources and definition checks

Independent project. Sources checked on **2026-10-23**. The only analytical inputs are NYC TLC high-volume FHV trip files and the TLC taxi-zone lookup. The reports below provide definitions, policy context, and an external validation target; their statistics are not mixed into the trip aggregates.

## Data and fields

- [NYC TLC trip-record page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [Monthly parquet URL pattern](https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2025-12.parquet) — replace the year and month.
- [Taxi-zone lookup](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv)
- [HVFHV data dictionary, March 18, 2025](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf), p. 1.

The dictionary identifies HV0003 as Uber and HV0005 as Lyft. Base passenger fare excludes tips, tolls, taxes, and fees. Driver pay excludes tips and tolls and is net of commission, taxes, and surcharges. Trip time is in seconds. `shared_request_flag` records willingness to pool, even if no match occurs. `cbd_congestion_fee` is distinct from the older NYS `congestion_surcharge`.

This project uses fare minus driver pay as **gross platform take**, not profit. Insurance, processing, marketing, incentives, and discounts cannot be fully reconciled from these records. Missing historical optional fee columns are zero-filled; a missing request timestamp is not a zero-minute wait.

## UCLA comparison

[UCLA Labor Center original report, February 2023](https://www.labor.ucla.edu/wp-content/uploads/2023/02/Taxi-Commission-policy-brief-2.9.23.pdf), pp. 4–8. [Institutional publication record](https://escholarship.org/uc/item/5q09h352).

The reported **9.0% in February 2019** and **20.7% in April 2022** use the same ratio-of-sums formula as this project. They are **not median commission rates**. The project benchmark also pools Uber and Lyft; it should not be compared directly with one company's separate trend. UCLA's **50% fare growth** and **31% pay growth** concern medians; this project's trend compares means. Its sample excludes WAV/outside-NYC trips, shared rides in 2019, and certain invalid records. Full restrictions and Table 4 totals are preserved in the source receipt. This project's broader population and different cleaning make this a cross-check, not a replication.

## Driver minimum-pay rules

- [TLC driver-pay explanation](https://www.nyc.gov/site/tlc/about/driver-pay.page): the rule regulates per-trip driver payment, not passenger prices or a minimum hourly wage.
- [TLC Industry Notice 26-03, February 24, 2026](https://www.nyc.gov/assets/tlc/downloads/pdf/industry-notices/industry_notice_26_03_english.pdf): effective **March 1, 2026**, in-city non-WAV rates including utilization are **$1.283 per mile plus $0.681 per minute**, following a **3.36%** increase. WAV and out-of-town rates differ. These are current policy context, not a rate applied retroactively in this analysis.
- [2025 adopted rule](https://www.nyc.gov/assets/tlc/downloads/pdf/driver_pay_rules_6_6_25.pdf), pp. 1, 7–8, 12, and [official rule page](https://rules.cityofnewyork.us/rule/driver-pay-high-volume-for-hire-vehicles/): adopted **June 25, 2025**, effective **August 1, 2025**. Expense and utilization changes, alongside the March 2025 per-minute inflation adjustment, are relevant confounders for before/after pay comparisons. The adopted text describes a **3.92%** March 2025 per-minute adjustment.

Negative gross take is possible under a driver-payment floor. It does not by itself prove a net platform loss, a subsidy, or a regulatory violation.

## Congestion Relief Zone charge

- [MTA: Taxis and For-Hire Vehicles](https://www.mta.info/fares-tolls/tolls/congestion-relief-zone/taxi-fhv-tolls): participating high-volume FHV bases collect **$1.50 per trip** from passengers and remit it to MTA for travel to, from, within, or through the zone.
- [TLC Industry Notice 24-10, December 5, 2024](https://www.nyc.gov/assets/tlc/downloads/pdf/industry-notices/industry_notice_24_10_english.pdf): implementation began **January 5, 2025**; the zone is Manhattan south of and including 60th Street, with specified highway/tunnel-connection exclusions.
- [March 3, 2026 Opinion and Order, MTA v. Duffy, 25-cv-1413, ECF 195](https://docs.justia.com/cases/federal/district-courts/new-york/nysdce/1:2025cv01413/637159/195): the court vacated the challenged federal termination attempts. [Official New York State statement on the decision](https://www.governor.ny.gov/news/statement-governor-kathy-hochul-148).

The legal payer and ultimate economic incidence are different questions. These trip records show recorded charges, fare, and driver pay; they cannot isolate how much the charge caused each party to absorb. For the empirical comparison, the project selects Manhattan pickup zones with at least 1,000 eligible Uber/Lyft pickups in February 2025, more than 95% of which have a positive CBD fee. That rule is an analytical proxy rather than an official boundary map. The endpoint-based comparison misses through-trips whose endpoints lie outside the inferred set. It is a descriptive difference-in-differences comparison with no established parallel-trends assumption.

## External trip-count check

[TLC February 2026 For-Hire Vehicle License Review, Table 1, p. 2](https://www.nyc.gov/assets/tlc/downloads/pdf/license-pause-report-2026-02.pdf) reports **22,108,438 high-volume FHV trips in December 2025**. The corresponding December 2024 figure is **21,068,851**. All FHV trips, including non-high-volume services, total **24,035,329** in December 2025; that broader total is not the comparison target.

Compare the December parquet's unfiltered raw rows to the high-volume figure, before the project's cleaning exclusions. Any difference is recorded in `data/results/validation.csv`, including its percentage. Public extract revisions and reporting scope can differ from a contemporaneous policy report; an unexplained discrepancy is disclosed rather than silently adjusted.

The same TLC report, p. 3, identifies Uber requests forwarded to yellow taxis as another possible reason for declining Manhattan HVFHV counts. Such trips can move between service categories without a corresponding loss of overall rider demand.

## 中文口径说明

本项目只把 TLC 月度行程和区域对照表作为分析输入。平台抽成是基础车费减司机收入的毛额，并非利润。UCLA 的 9.0% 和 20.7% 同样按总额计算；中位数口径只涉及其车费与司机收入增速。双方清洗范围不同，所以这里只做交叉核对，不声称完整复刻。

拥堵费法定由乘客支付、平台代收代缴，但最终由谁承担成本不能仅凭前后对比确定。项目的区域代理限于 2025 年 2 月有效上车单不少于 1,000、且超过 95% 被收 CBD 费用的曼哈顿区域，任一端在集合内即算关联订单，会漏掉只穿过拥堵区的订单。最低收入调整、车型和线路结构、价格变化、转派出租车等因素都可能影响结果。区内外对比为描述性结果，不作因果结论。

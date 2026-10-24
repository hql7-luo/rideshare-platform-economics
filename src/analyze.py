"""Turn monthly additive summaries into transparent business metrics and narratives."""

from pathlib import Path
import json
import math

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "data" / "results"
COMPANIES = ["Uber", "Lyft"]
DISTANCE_BINS = ["0-1", "1-2", "2-3", "3-5", "5-10", "10-20", "20+"]
SUM_COLUMNS = [
    "trips", "fare", "driver_pay", "take", "miles", "minutes", "wait_minutes",
    "wait_trips", "tips", "tolls", "bcf", "sales_tax", "congestion_surcharge",
    "airport_fee", "cbd_congestion_fee", "negative_take_trips", "shared_trips",
    "charged_trips",
]
PASSENGER_COLUMNS = [
    "fare", "tips", "tolls", "bcf", "sales_tax", "congestion_surcharge",
    "airport_fee", "cbd_congestion_fee",
]


def divide(numerator, denominator):
    """Leave an undefined ratio missing instead of silently treating it as zero."""
    return numerator / denominator.where(denominator != 0)


def read_table(name):
    """Read the small committed summaries, never the original trip files."""
    table = pd.read_csv(PROCESSED / f"{name}.csv")
    for column in SUM_COLUMNS:
        if column not in table:
            table[column] = 0
        table[column] = pd.to_numeric(table[column], errors="raise")
    return table


def add_metrics(table):
    """Calculate ratios after summing so large and small groups get correct weights."""
    table = table.copy()
    for column, total in [
        ("fare_per_trip", "fare"), ("driver_pay_per_trip", "driver_pay"),
        ("take_per_trip", "take"), ("duration_minutes", "minutes"),
        ("negative_take_share", "negative_take_trips"),
        ("shared_share", "shared_trips"), ("charged_share", "charged_trips"),
        ("cbd_fee_per_trip", "cbd_congestion_fee"),
    ]:
        table[column] = divide(table[total], table["trips"])
    table["take_rate"] = divide(table["take"], table["fare"])
    table["avg_wait_minutes"] = divide(table["wait_minutes"], table["wait_trips"])
    table["fare_per_mile"] = divide(table["fare"], table["miles"])
    table["speed_mph"] = 60 * divide(table["miles"], table["minutes"])
    table["passenger_total_per_trip"] = divide(table[PASSENGER_COLUMNS].sum(axis=1), table["trips"])
    return table


def sum_groups(table, groups):
    """Keep every aggregation visible in a short group-by statement."""
    return add_metrics(table.groupby(groups, as_index=False, dropna=False)[SUM_COLUMNS].sum())


def add_share(table, groups):
    table = table.copy()
    total = table.groupby(groups)["trips"].transform("sum") if groups else pd.Series(table["trips"].sum(), index=table.index)
    table["share"] = divide(table["trips"], total)
    return table


def write_table(table, name):
    table.to_csv(RESULTS / f"{name}.csv", index=False, float_format="%.10g")


def load_source_context():
    """Keep verified external references available after a fresh repository clone."""
    source_receipt = ROOT / "work" / "source_receipts.json"
    source_context = RESULTS / "source_context.json"
    if source_receipt.exists():
        source_context.write_text(source_receipt.read_text(), encoding="utf-8")
    if not source_context.exists():
        raise FileNotFoundError("Missing data/results/source_context.json with verified policy and UCLA sources.")
    return json.loads(source_context.read_text())


def build_external_validation(audit, source_context):
    """Compare the report with unfiltered rows, including all reported platforms."""
    reference = next(source for source in source_context["sources"] if source["id"] == "tlc_official_trip_count")
    selected = audit[audit["month"] == reference["month"]]
    if selected.empty:
        raise ValueError(f"Missing raw-row audit for official comparison month {reference['month']}.")
    raw_rows = int(selected["raw_rows"].sum())
    official_rows = int(reference["raw_trips"])
    if official_rows <= 0:
        raise ValueError("The official row-count reference must be positive.")
    difference = raw_rows - official_rows
    return pd.DataFrame([{
        "month": reference["month"], "raw_rows": raw_rows, "official_rows": official_rows,
        "difference_rows": difference, "difference_pct": 100 * difference / official_rows,
        "source_url": reference["url"],
        "scope": "All unfiltered HVFHV parquet rows; before cleaning",
    }])


def filter_recent(table, recent_months):
    return table[table["month"].isin(recent_months)].copy()


def calculate_change(before, after, metric):
    if pd.isna(before) or pd.isna(after):
        return float("nan")
    if metric == "take_rate":
        return 100 * (after - before)
    return 100 * (after / before - 1) if before != 0 else float("nan")


def build_congestion_comparison(congestion, months):
    """Use matched calendar months and pooled ratios; this is a descriptive comparison."""
    matched = [month for month in months if month.startswith("2025-") and month[5:] != "01" and "2024-" + month[5:] in months]
    selected = congestion[congestion["month"].isin(matched + ["2024-" + month[5:] for month in matched])].copy()
    metrics = ["trips", "fare_per_trip", "driver_pay_per_trip", "take_per_trip", "take_rate", "speed_mph", "duration_minutes", "avg_wait_minutes", "passenger_total_per_trip", "cbd_fee_per_trip"]
    rows = []
    for period in ["pooled"] + matched:
        selected_months = matched if period == "pooled" else [period]
        period_table = selected[selected["month"].isin(selected_months + ["2024-" + month[5:] for month in selected_months])].copy()
        period_table["year"] = period_table["month"].str[:4].astype(int)
        pooled = sum_groups(period_table, ["company", "year", "zone_group"])
        for company in COMPANIES:
            for metric in metrics:
                values = {}
                for group, prefix in [("Zone-linked", "zone"), ("Other", "other")]:
                    for year in [2024, 2025]:
                        match = pooled[(pooled["company"] == company) & (pooled["year"] == year) & (pooled["zone_group"] == group)]
                        values[f"{prefix}_{year}"] = float(match.iloc[0][metric]) if len(match) else float("nan")
                zone_change = calculate_change(values["zone_2024"], values["zone_2025"], metric)
                other_change = calculate_change(values["other_2024"], values["other_2025"], metric)
                zone_absolute = values["zone_2025"] - values["zone_2024"]
                other_absolute = values["other_2025"] - values["other_2024"]
                rows.append({"company": company, "period": period, "metric": metric, **values,
                             "zone_change": zone_change, "other_change": other_change,
                             "difference_in_changes": zone_change - other_change,
                             "zone_absolute_change": zone_absolute, "other_absolute_change": other_absolute,
                             "absolute_difference_in_changes": zone_absolute - other_absolute})
    comparison = pd.DataFrame(rows)
    if len(selected):
        selected["year"] = selected["month"].str[:4].astype(int)
        fees = sum_groups(selected, ["company", "year", "zone_group"])
        fees["charged_fee_per_charged_trip"] = divide(fees["cbd_congestion_fee"], fees["charged_trips"])
    else:
        fees = pd.DataFrame()
    return comparison, fees, matched


def clean_json(value):
    """Use standard JSON null for missing values so the standalone page can load it."""
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return clean_json(value.item())
    return value


def format_money(value):
    return f"${value:,.2f}"


def format_pct(value):
    return f"{100 * value:.1f}%"


def format_change(value):
    return f"{value:+.1f}%"


def build_narratives(numbers, distance, airport):
    """Write the same result-backed numbers to every public-facing narrative."""
    latest = numbers["latest_month"]
    recent = numbers["recent12"]
    baseline = {row["company"]: row for row in numbers["baseline"]}
    short = sum_groups(distance[distance["distance_bin"].isin(["0-1", "1-2"])], ["company"])
    short = short.set_index("company").to_dict("index")
    congestion = numbers["congestion"]["pooled"]["Uber"]
    speed = congestion["speed_mph"]
    fare = congestion["fare_per_trip"]
    driver = congestion["driver_pay_per_trip"]
    take = congestion["take_per_trip"]
    fee = numbers["congestion"]["fee_metrics"]["Uber"]
    airport_uber = airport[(airport["company"] == "Uber") & (airport["is_airport"] == 1)].iloc[0]
    current_month = numbers["data"]["latest_month"]
    u = latest["Uber"]
    l = latest["Lyft"]
    b = baseline["Uber"]
    s = short["Uber"]
    findings = [
        {"id": "take", "en": f"In {current_month}, Uber's gross take rate was {format_pct(u['take_rate'])} ({format_money(u['take_per_trip'])}/trip), versus Lyft's {format_pct(l['take_rate'])} ({format_money(l['take_per_trip'])}/trip).",
         "zh": f"{current_month}，Uber 毛额抽成率为 {format_pct(u['take_rate'])}（每单 {format_money(u['take_per_trip'])}），Lyft 为 {format_pct(l['take_rate'])}（每单 {format_money(l['take_per_trip'])}）。"},
        {"id": "growth", "en": f"From {b['baseline_month']} to {current_month}, Uber's mean base fare per trip changed {format_change(b['fare_growth_pct'])}, while mean driver pay changed {format_change(b['driver_pay_growth_pct'])}; its take rate moved {b['take_rate_change_pp']:+.1f} percentage points.",
         "zh": f"从 {b['baseline_month']} 到 {current_month}，Uber 平均每单基础车费变动 {format_change(b['fare_growth_pct'])}，司机收入变动 {format_change(b['driver_pay_growth_pct'])}；抽成率变动 {b['take_rate_change_pp']:+.1f} 个百分点。"},
        {"id": "share", "en": f"Over the latest 12 months, Lyft handled {format_pct(recent['Lyft']['share'])} of Uber/Lyft trips; its mean gross take was {format_money(recent['Lyft']['take_per_trip'])}/trip versus Uber's {format_money(recent['Uber']['take_per_trip'])}.",
         "zh": f"最近 12 个月，Lyft 占 Uber/Lyft 合计订单的 {format_pct(recent['Lyft']['share'])}；平均每单毛额抽成为 {format_money(recent['Lyft']['take_per_trip'])}，Uber 为 {format_money(recent['Uber']['take_per_trip'])}。"},
        {"id": "short", "en": f"For Uber trips up to 2 miles in the latest 12 months, gross take rate was {format_pct(s['take_rate'])}; driver pay exceeded base fare on {format_pct(s['negative_take_share'])} of trips.",
         "zh": f"最近 12 个月，Uber 不超过 2 英里的订单毛额抽成率为 {format_pct(s['take_rate'])}；{format_pct(s['negative_take_share'])} 的订单司机收入高于基础车费。"},
        {"id": "congestion", "en": f"In matched Feb-Dec 2025 versus 2024 months, Uber's zone-linked speed changed {format_change(speed['zone_change'])}, versus {format_change(speed['other_change'])} elsewhere: a {speed['difference_in_changes']:+.1f} percentage-point descriptive gap.",
         "zh": f"2025 年与 2024 年匹配的 2—12 月相比，Uber 区内关联订单速度变动 {format_change(speed['zone_change'])}，其他订单变动 {format_change(speed['other_change'])}，描述性差距为 {speed['difference_in_changes']:+.1f} 个百分点。"},
    ]
    memo = [
        {"title_en": "Test price changes against driver pay and retention", "title_zh": "定价试验同时看司机收入与留存",
         "evidence_en": f"Uber's mean fare changed {format_change(b['fare_growth_pct'])} since {b['baseline_month']}, versus {format_change(b['driver_pay_growth_pct'])} for driver pay; latest take rate is {format_pct(u['take_rate'])}.",
         "evidence_zh": f"自 {b['baseline_month']}，Uber 平均车费变动 {format_change(b['fare_growth_pct'])}，司机收入变动 {format_change(b['driver_pay_growth_pct'])}；最新抽成率为 {format_pct(u['take_rate'])}。",
         "action_en": "Test by zone and hour; track completions, repeat usage and driver supply alongside gross take. This historical gap does not establish pricing power.",
         "action_zh": "按区域与时段做小规模定价试验，同时看完成单量、复购、司机供给和毛额抽成；历史增速差不能直接证明提价空间。"},
        {"title_en": "Allocate supply by wait time, including airport trips", "title_zh": "按等待时间配置运力，单独看机场",
         "evidence_en": f"Airport-linked trips were {format_pct(recent['Uber']['airport_share'])} of Uber trips in the latest 12 months, with {airport_uber['avg_wait_minutes']:.1f}-minute valid mean waits and {format_pct(airport_uber['take_rate'])} gross take rate.",
         "evidence_zh": f"最近 12 个月，机场关联订单占 Uber 的 {format_pct(recent['Uber']['airport_share'])}，有效平均等待 {airport_uber['avg_wait_minutes']:.1f} 分钟，毛额抽成率 {format_pct(airport_uber['take_rate'])}。",
         "action_en": "Pilot supply incentives where waits persist. Measure completions, driver pay including incentives, and platform contribution after incentives using internal data.",
         "action_zh": "按区域和时段的等待情况试验运力激励；衡量完成率、计入激励后的司机收入，并用内部数据核对扣除激励后的平台贡献。"},
        {"title_en": "Evaluate short trips in dollars as well as take rates", "title_zh": "短途单同时看比例与每单金额",
         "evidence_en": f"Uber trips up to 2 miles had a {format_pct(s['take_rate'])} gross take rate, but just {format_money(s['take_per_trip'])}/trip versus {format_money(recent['Uber']['take_per_trip'])} overall; {format_pct(s['negative_take_share'])} paid drivers above base fare.",
         "evidence_zh": f"Uber 不超过 2 英里的订单抽成率 {format_pct(s['take_rate'])}，但每单仅 {format_money(s['take_per_trip'])}，整体为 {format_money(recent['Uber']['take_per_trip'])}；{format_pct(s['negative_take_share'])} 的订单司机收入高于基础车费。",
         "action_en": "Prioritize pickup efficiency before broad minimum-fare increases. Test rider retention and driver pay; negative gross take alone does not establish a net loss.",
         "action_zh": "优先缩短接驾，再考虑广泛调高最低车费；测试留存并遵守司机支付要求。负抽成不能直接当作净亏损。"},
        {"title_en": "Separate the congestion fee from platform pricing", "title_zh": "把拥堵费和平台定价分开评估",
         "evidence_en": f"Uber zone-linked fare/trip changed {format_change(fare['zone_change'])}, pay/trip {format_change(driver['zone_change'])}, and take/trip {format_change(take['zone_change'])}. The recorded CBD charge averaged {format_money(fee['charged_fee_per_charged_trip'])} per charged trip.",
         "evidence_zh": f"Uber 区内关联订单每单车费变动 {format_change(fare['zone_change'])}，司机收入 {format_change(driver['zone_change'])}，毛额抽成 {format_change(take['zone_change'])}；被收费订单平均记录 CBD 费用 {format_money(fee['charged_fee_per_charged_trip'])}。",
         "action_en": "Itemize the passenger fee and monitor demand, pay and take separately. Controlled tests are needed to identify economic incidence.",
         "action_zh": "清晰列出乘客附加费，分开监测需求、司机收入与抽成；用对照试验识别经济负担归属。"},
    ]
    return findings, memo


def write_narratives(numbers):
    """Generate bilingual portfolio documents directly from the result dictionary."""
    data = numbers["data"]
    latest = data["latest_month"]
    sample = data["sampling"]
    sample_text = json.dumps(sample, ensure_ascii=False) if not isinstance(sample, str) else sample
    findings_en = "\n".join(f"- {row['en']}" for row in numbers["findings"])
    findings_zh = "\n".join(f"- {row['zh']}" for row in numbers["findings"])
    warning_en = "; ".join(f"zone {row['location_id']} ({row['zone']}): {row['training_trips']} training pickup(s)" for row in data["inferred_zone_warnings"])
    warning_zh = "；".join(f"区域 {row['location_id']}（{row['zone']}）：训练月仅 {row['training_trips']} 单上车" for row in data["inferred_zone_warnings"])
    ucla = "; ".join(f"{row['month']}: project {format_pct(row['project_take_rate'])}, UCLA {format_pct(row['reported_take_rate'])}" for row in numbers["ucla_check"])
    run = "python src/build_data.py && python src/analyze.py && python src/make_charts.py && python src/build_explorer.py"
    page = "https://hql7-luo.github.io/rideshare-platform-economics/"
    validation = ""
    validation_path = RESULTS / "validation.csv"
    if validation_path.exists():
        validation_table = pd.read_csv(validation_path)
        if {"month", "raw_rows", "official_rows", "difference_rows", "difference_pct"}.issubset(validation_table.columns):
            row = validation_table.iloc[0]
            validation = f" Raw-file check for {row['month']}: {int(row['raw_rows']):,} rows versus TLC's {int(row['official_rows']):,}; difference {int(row['difference_rows']):+,} ({row['difference_pct']:+.2f}%)."
    readme = f"""# NYC Rideshare Economics: Uber vs Lyft

**Independent project · NYC TLC public data · Python, DuckDB, SQL, pandas, matplotlib**

How much of each NYC Uber/Lyft base fare remains after driver pay, and how did fares, pay and travel conditions change around congestion pricing?

## Key findings

{findings_en}

## Charts

![Gross take rates](charts/01_take_rate_trend.png)
![Fares and driver pay](charts/02_fare_driver_pay.png)
![Lyft trip share](charts/03_lyft_share.png)
![Distance and take rates](charts/04_distance_take_rate.png)
![Weekday and hour take rates](charts/05_hourly_take_rate.png)
![Weekday and hour waits](charts/06_hourly_wait.png)
![Matched-month congestion comparison](charts/07_congestion_comparison.png)
![Speeds inside and outside the inferred area](charts/08_congestion_speed.png)

## Interactive explorer

[Open the bilingual explorer]({page}) · [Strategy memo](docs/memo.md) · [Methods](docs/methodology.md) · [Source notes](docs/sources.md)

The standalone [HTML file](docs/index.html) also opens locally. It includes metric switching, hover details, distance and hour views, a congestion comparison, and a searchable pickup-zone table. It uses embedded data and no external chart service.

## Data and method

- Only [NYC TLC High Volume FHV trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) and the official zone lookup feed the analysis. Companies: HV0003 Uber and HV0005 Lyft. Coverage: {data['first_month']} through {latest}; {data['coverage_months']} observed months. Recent snapshot: {data['recent_start']} through {data['recent_end']} ({data['recent_months']} observed months). Monthly rows are processed one file at a time; raw files are deleted and excluded from git. Completed monthly summaries are reused on reruns.
- Coverage mode from the download manifest: **{sample_text}**. Earlier sampled months are observations, not annual totals. The exact month list and download receipts are in `data/processed/manifest.json`.
- Keep fare > 0, driver pay ≥ 0, 0 < miles ≤ 100, duration 1–240 minutes, and pickup month matching the file. Valid waits are 0–60 minutes; invalid waits are excluded from the wait denominator only. Missing historical optional fee fields are zero. Record raw and retained counts by company and month.
- **Gross take = base passenger fare − driver pay. Take rate = sum(take) / sum(base fare).** Neither includes tips, tolls, taxes or surcharges. A group rate is a ratio of totals, not a mean of trip rates. Fare and pay growth compare mean dollars/trip in {data['first_month']} with {latest}; dollars are nominal.
- Distance, weekday-hour, airport, borough and pickup-zone comparisons pool the latest 12 calendar months. Airport-linked means either endpoint is zone 1, 132 or 138, including Newark. Speed = total miles / total occupied trip hours; pay/trip is not hourly driver earnings. Market share covers Uber and Lyft only.
- Congestion-zone membership is inferred from clean pooled Uber/Lyft pickup records in February 2025: more than 95% with a positive `cbd_congestion_fee`. A trip is zone-linked if either endpoint is in that fixed inferred set. Compare available matched February–December 2025 months with the same 2024 months, skipping January. Report growth within each group and the difference between growth rates; this is **descriptive, not a causal estimate**. Pooled per-trip metrics are computed after summing all matched trips.
- **Inferred-zone warning:** {warning_en}. Both meet the requested threshold with very small denominators. In particular, Newark is outside the legal CBD, but its endpoint trips enter the zone-linked group under this rule. Treat the groups as a data-inferred proxy; these false positives can materially affect the comparison. No extra volume cutoff is imposed.
- Policy context: the MTA passenger charge is $1.50 per qualifying trip from January 5, 2025; the March 3, 2026 court decision vacated the challenged federal termination attempts. TLC's March 1, 2026 in-city non-WAV driver-pay rates are $1.283/mile plus $0.681/minute, including utilization; these are not retroactively applied to past trips. See the primary sources in [source notes](docs/sources.md) and the structured receipt in `data/results/source_context.json`.
- Pooled Uber + Lyft UCLA cross-check: {ucla}. UCLA also uses a ratio of totals for take rate. Its filters differ: non-WAV, NYC endpoints, no shared 2019 trips, fare/pay above $0.01, duration up to five hours. Its separate 50% fare / 31% pay growth statement uses medians; this project uses means. [Original UCLA report](https://www.labor.ucla.edu/wp-content/uploads/2023/02/Taxi-Commission-policy-brief-2.9.23.pdf).{validation}

## Limitations

Gross take is **not profit**: insurance, payment processing, marketing, subsidies and other operating costs are not deducted. Driver incentives and passenger discounts may be incompletely captured. Recorded passenger totals add the listed fare, tips and fees and may not equal the passenger's final cash charge. Trip composition, inflation, prices, minimum driver-pay rules, seasonality and supply changes can all affect comparisons. Uber requests forwarded to yellow taxis can also change HVFHV counts without an equivalent change in overall rider demand. The fee's statutory passenger charge does not establish its economic incidence. Endpoint-based inferred zones miss trips that only pass through the area and can classify some fee-charged trips as Other. February 2025 training makes the geography descriptive rather than an independent pre-policy treatment assignment. Boroughs are pickup locations; no causal or company-profit claim is made.

## Run locally

Python 3.11 or 3.12:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
{run}
python -m pytest
```

The first run downloads substantial data and needs internet access and temporary disk space. A completed checkpoint is skipped. The pipeline documents any historical sampling in its manifest. CI runs the hand-written SQL tests on Python 3.11 and 3.12 without downloading the full dataset.

## Project structure

```text
src/             # Download, summarize, analyze, chart, build the explorer
sql/             # One readable DuckDB query per file
data/processed/  # Small additive monthly summaries and source receipts
data/results/    # Metrics, comparisons and key_numbers.json
charts/          # Eight PNG figures
docs/            # Standalone explorer, bilingual memo and source notes
tests/           # Hand-written SQL and metric checks
```

---

## 中文

**独立项目 · 数据来源：NYC TLC**

纽约 Uber/Lyft 每单基础车费扣除司机收入后剩下多少？拥堵收费前后，车费、司机收入和出行条件怎样变化？

### 关键发现

{findings_zh}

### 图表与页面

上方八张图展示抽成、车费与司机收入、份额、距离、时段和拥堵区变化。[交互页面]({page}) 支持中英文、深色模式、悬停数值和区域搜索；[策略备忘录](docs/memo.md) 给出四条有数据依据的建议。

### 数据与方法

数据区间为 {data['first_month']} 至 {latest}，共 {data['coverage_months']} 个有数据月份。最近 12 个月快照为 {data['recent_start']} 至 {data['recent_end']}。覆盖模式：**{sample_text}**；采样月份不能当作全年总量。逐月下载、用 DuckDB 汇总、删除原始文件，支持断点续跑。

保留基础车费大于零、司机收入非负、距离在 (0,100] 英里、时长 1—240 分钟且上车月份与文件一致的订单；等待时间仅纳入 0—60 分钟的有效记录。历史缺失的可选费用列按零处理。Uber/Lyft 对应 HV0003/HV0005，份额仅以这两家公司为分母。

毛额抽成＝基础车费－司机收入；抽成率＝合计抽成÷合计基础车费，不含小费、过路费、税费和附加费。先汇总再算比例；车费和司机收入增长比较名义平均每单金额。速度用总里程÷总行程小时，司机每单收入不是小时工资。机场单任一端为区域 1、132、138，包含 Newark。

用 2025 年 2 月超过 95% 订单被收 CBD 费用的上车区域识别收费区，任一端在该集合内即为区内关联订单。跳过 2025 年 1 月，把 2025 年 2—12 月的可用月份与 2024 年同月比较；分别计算区内外变化，再比较增速差。它只是差中差思路的描述性对照，不能写成政策因果效果。UCLA 的 9% 与 20.7% 及本项目对应核对值均为两平台合计的总额比例，但清洗、无障碍车、纽约两端和拼车范围不同；其 50%/31% 增长使用中位数，本项目使用均值。原始行数核对及政策原文见[来源说明](docs/sources.md)。

**区域推断警示：**{warning_zh}。它们在极小分母下通过阈值，尤其 Newark 不在法定 CBD 内，却会因端点规则被计入区内关联组。这里保留指定规则，不另加最低单量门槛；应把区域视作数据推断代理，其误分类可能显著影响区内外结果。

政策背景：拥堵区自 2025-01-05 对符合条件的网约车每单向乘客收取 $1.50；2026-03-03 法院撤销了受到挑战的联邦终止决定。2026-03-01 起，纽约市内非无障碍车辆的最低司机支付标准为每英里 $1.283 加每分钟 $0.681，已含利用率调整；本项目不把这一标准追溯应用到历史订单。

### 局限

毛额抽成不是利润，尚未扣除保险、支付手续费、营销、补贴等费用。奖励和乘客优惠可能未完整记录，所列费用合计也未必等于最终实付。价格、通胀、订单结构、司机最低收入调整、供需与季节因素都会影响结果。Uber 转派黄色出租车的订单也可能改变 HVFHV 分类计数。法定由乘客支付不等于能识别实际经济负担；按端点推断区域会漏掉只穿过收费区的订单。上车行政区不能代表司机居住地。本项目不估计净利润或政策因果效果。

### 如何运行与目录

安装依赖后运行上方四段脚本命令即可重建，`python -m pytest` 执行小样本测试。目录说明见上表；清洗汇总与结果 CSV 均可直接检查。

MIT License.
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    lines = ["# Strategy memo / 策略备忘录", "", "**Independent project · Perspective: Uber strategy analyst / 假设视角：Uber 策略分析师**", "", f"Data through {latest}; recent window {data['recent_start']}–{data['recent_end']}. Nominal USD; gross take is before platform costs. / 数据截至 {latest}，最近窗口 {data['recent_start']}—{data['recent_end']}；金额为名义美元，毛额抽成未扣平台成本。", ""]
    for index, item in enumerate(numbers["memo"], 1):
        lines.extend([f"**{index}. {item['title_en']} / {item['title_zh']}**", "", item["evidence_en"] + " " + item["action_en"], "", item["evidence_zh"] + " " + item["action_zh"], ""])
    lines.extend(["**Limits / 局限**", "", "Descriptive hypotheses, not causal effects: pricing, minimum-pay changes and trip mix confound comparisons. Gross take is not profit; incentives/discounts may be incomplete. The inferred proxy includes Newark and zone 105 from just one and two training pickups, respectively; it also misses through-trips. Economic incidence remains unidentified. Evidence: `data/results/key_numbers.json` and result CSVs.", "", "这是描述性假设；价格、最低收入与订单结构混杂，毛额抽成不是利润，优惠和激励可能遗漏。推断代理因训练月仅 1、2 单就纳入 Newark 与区域 105，还会漏掉穿区订单；经济负担归属无法识别。数字见 key_numbers.json 与结果表。", ""])
    (ROOT / "docs" / "memo.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    source_context = load_source_context()
    manifest = json.loads((PROCESSED / "manifest.json").read_text())
    if not manifest.get("all_selected_months_complete", False):
        raise ValueError("Download coverage is incomplete. Finish build_data.py before generating publishable results.")
    monthly_raw = read_table("monthly")
    monthly_raw = monthly_raw[monthly_raw["company"].isin(COMPANIES)]
    monthly = add_share(sum_groups(monthly_raw, ["month", "company"]), ["month"])
    monthly = monthly.sort_values(["month", "company"]).reset_index(drop=True)
    months = sorted(monthly["month"].unique())
    latest = months[-1]
    recent_start = str(pd.Period(latest, freq="M") - 11)
    recent_months = [month for month in months if month >= recent_start]
    expected_recent = [str(month) for month in pd.period_range(recent_start, latest, freq="M")]
    if recent_months != expected_recent or len(recent_months) != 12:
        raise ValueError("The recent snapshot requires all twelve calendar months.")
    if sorted(manifest["months"]) != months:
        raise ValueError("The manifest month list does not match the monthly table.")

    # Build the latest twelve-month operating views from additive summaries.
    distance = sum_groups(filter_recent(read_table("distance"), recent_months), ["company", "distance_bin"])
    distance["_order"] = distance["distance_bin"].map({name: index for index, name in enumerate(DISTANCE_BINS)})
    distance = distance.sort_values(["company", "_order"]).drop(columns="_order")
    hourly = sum_groups(filter_recent(read_table("hourly"), recent_months), ["company", "weekday", "hour"])
    airport = sum_groups(filter_recent(read_table("airport"), recent_months), ["company", "is_airport"])
    airport["trip_share"] = divide(airport["trips"], airport.groupby("company")["trips"].transform("sum"))
    snapshot = add_share(sum_groups(filter_recent(monthly_raw, recent_months), ["company"]), [])
    airport_share = airport[airport["is_airport"] == 1].set_index("company")["trip_share"]
    snapshot["airport_share"] = snapshot["company"].map(airport_share).fillna(0)
    zone = sum_groups(filter_recent(read_table("pickup_zone"), recent_months), ["company", "location_id"])
    lookup = pd.read_csv(PROCESSED / "taxi_zone_lookup.csv").rename(columns={"LocationID": "location_id", "Borough": "borough", "Zone": "zone"})
    zone = zone.merge(lookup[["location_id", "borough", "zone"]], on="location_id", how="left")
    zone[["borough", "zone"]] = zone[["borough", "zone"]].fillna("Unknown")
    zone = add_share(zone, ["company"])
    borough = add_share(sum_groups(zone, ["company", "borough"]), ["company"])
    congestion = sum_groups(read_table("congestion"), ["month", "company", "zone_group"])
    comparison, fees, matched = build_congestion_comparison(congestion, months)

    # Compare means at fixed endpoints rather than average monthly growth rates.
    baseline_rows = []
    for company in COMPANIES:
        start = monthly[(monthly["company"] == company) & (monthly["month"] == months[0])].iloc[0]
        end = monthly[(monthly["company"] == company) & (monthly["month"] == latest)].iloc[0]
        baseline_rows.append({"company": company, "baseline_month": months[0], "end_month": latest,
                              "fare_growth_pct": calculate_change(start["fare_per_trip"], end["fare_per_trip"], "fare_per_trip"),
                              "driver_pay_growth_pct": calculate_change(start["driver_pay_per_trip"], end["driver_pay_per_trip"], "driver_pay_per_trip"),
                              "take_rate_start": start["take_rate"], "take_rate_end": end["take_rate"],
                              "take_rate_change_pp": 100 * (end["take_rate"] - start["take_rate"])})
    baseline = pd.DataFrame(baseline_rows)
    ucla_rows = []
    for month, reported in [("2019-02", 0.09), ("2022-04", 0.207)]:
        selected = monthly[monthly["month"] == month]
        project_rate = selected["take"].sum() / selected["fare"].sum() if selected["fare"].sum() else float("nan")
        ucla_rows.append({"month": month, "project_take_rate": project_rate, "reported_take_rate": reported, "difference_pp": 100 * (project_rate - reported)})
    ucla = pd.DataFrame(ucla_rows)
    audit = pd.read_csv(PROCESSED / "audit.csv")
    audit["retained_share"] = divide(audit["kept_rows"], audit["raw_rows"])
    validation = build_external_validation(audit, source_context)
    tables = {"monthly_metrics": monthly, "distance_metrics": distance, "hourly_metrics": hourly,
              "airport_metrics": airport, "company_snapshot": snapshot, "borough_metrics": borough,
              "zone_metrics": zone, "congestion_trends": congestion, "congestion_comparison": comparison,
              "congestion_fee_metrics": fees, "baseline_comparison": baseline, "ucla_comparison": ucla,
              "audit_summary": audit, "validation": validation}
    # Check additive identities before writing documents or exposing the result data.
    for company in COMPANIES:
        company_months = monthly[monthly["company"] == company]
        expected = company_months[company_months["month"].isin(recent_months)][SUM_COLUMNS].sum()
        for name in ["distance_metrics", "hourly_metrics", "airport_metrics", "company_snapshot", "borough_metrics", "zone_metrics"]:
            actual = tables[name][tables[name]["company"] == company][SUM_COLUMNS].sum()
            if not ((actual - expected).abs() <= expected.abs().clip(lower=1) * 1e-8).all():
                raise ValueError(f"Additive totals do not reconcile: {name}, {company}")
    if not ((monthly["fare"] - monthly["driver_pay"] - monthly["take"]).abs() < monthly["fare"].abs() * 1e-8).all():
        raise ValueError("Gross take does not reconcile to fare minus driver pay.")
    if matched != [f"2025-{month:02d}" for month in range(2, 13)]:
        raise ValueError("The congestion comparison requires all matched February-December months.")
    for name, table in tables.items():
        write_table(table, name)
    pooled_dict = {}
    for company in COMPANIES:
        selected = comparison[(comparison["company"] == company) & (comparison["period"] == "pooled")]
        pooled_dict[company] = selected.drop(columns=["company", "period"]).set_index("metric").to_dict("index")
    fee_dict = fees[(fees["year"] == 2025) & (fees["zone_group"] == "Zone-linked")].drop(columns=["year", "zone_group"]).set_index("company").to_dict("index")
    inferred_zones = pd.read_csv(PROCESSED / "inferred_cbd_zones.csv")
    inferred_count = int(inferred_zones["in_zone"].isin([True, 1, "True", "true", "1"]).sum())
    warnings = inferred_zones[inferred_zones["location_id"].isin([1, 105]) & inferred_zones["in_zone"].isin([True, 1, "True", "true", "1"])].merge(lookup[["location_id", "zone"]], on="location_id", how="left")
    warnings = warnings.rename(columns={"trips": "training_trips"})[["location_id", "zone", "training_trips", "charged_share"]].to_dict("records")
    numbers = {"project": "NYC Rideshare Economics: Uber vs Lyft", "as_of_date": manifest.get("created_at", "2026-10-23")[:10],
               "data": {"first_month": months[0], "latest_month": latest, "recent_start": recent_start,
                        "recent_end": latest, "recent_months": len(recent_months), "coverage_months": len(months),
                        "sampling": manifest.get("sampling", "Full monthly coverage"), "months": months,
                        "matched_congestion_months": matched, "inferred_zone_count": inferred_count,
                        "inferred_zone_warnings": warnings},
               "colors": {"Uber": "#2a78d6", "Lyft": "#d6337a"},
               "definitions": {"take": "base_passenger_fare - driver_pay", "take_rate": "sum(take) / sum(base_passenger_fare)", "unit": "nominal USD", "warning": "Gross take is not profit; tips, tolls, taxes and fees excluded from take."},
               "recent12": snapshot.set_index("company").to_dict("index"),
               "latest_month": monthly[monthly["month"] == latest].drop(columns="month").set_index("company").to_dict("index"),
               "baseline": baseline.to_dict("records"), "ucla_check": ucla.to_dict("records"),
               "congestion": {"months": matched, "pooled": pooled_dict, "fee_metrics": fee_dict}}
    numbers["findings"], numbers["memo"] = build_narratives(numbers, distance, airport)
    numbers = clean_json(numbers)
    (RESULTS / "key_numbers.json").write_text(json.dumps(numbers, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_narratives(numbers)
    print(f"Analyzed {len(months)} months through {latest}; wrote {len(tables)} result tables and bilingual documents.")


if __name__ == "__main__":
    main()

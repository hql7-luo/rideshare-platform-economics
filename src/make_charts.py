"""Draw eight plain matplotlib figures from the committed analysis results."""

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.ticker import PercentFormatter
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"
CHARTS = ROOT / "charts"
COLORS = {"Uber": "#2a78d6", "Lyft": "#d6337a"}
COMPANIES = ["Uber", "Lyft"]
DISTANCE_BINS = ["0-1", "1-2", "2-3", "3-5", "5-10", "10-20", "20+"]


def set_style():
    """Use light grids, thin lines and legible labels without a dual axis."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 12,
        "axes.titleweight": "semibold", "axes.labelsize": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": False,
        "axes.grid": True, "grid.color": "#e5e9ef", "grid.linewidth": 0.6,
        "axes.axisbelow": True, "lines.linewidth": 1.6,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "text.color": "#172232", "axes.labelcolor": "#526174",
        "xtick.color": "#526174", "ytick.color": "#526174",
        "savefig.facecolor": "white", "savefig.dpi": 180,
    })


def save_figure(figure, name, note):
    figure.text(0.02, 0.015, note, ha="left", va="bottom", fontsize=8, color="#657184")
    figure.savefig(CHARTS / name, bbox_inches="tight", pad_inches=0.2)
    plt.close(figure)


def style_dates(axis, extend=True):
    axis.xaxis.set_major_locator(mdates.YearLocator())
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    if extend:
        left, right = axis.get_xlim()
        axis.set_xlim(left, right + (right - left) * 0.09)
    axis.tick_params(length=0, pad=7)


def annotate_end(axis, x, y, text, color, offset=(8, 0)):
    axis.annotate(text, (x, y), xytext=offset, textcoords="offset points", color=color,
                  fontsize=9, va="center", fontweight="semibold")


def plot_take_rate(monthly, numbers):
    latest = numbers["latest_month"]
    higher_company = max(COMPANIES, key=lambda company: latest[company]["take_rate"])
    figure, axis = plt.subplots(figsize=(10.8, 4.7))
    for company in COMPANIES:
        table = monthly[monthly["company"] == company].sort_values("date")
        axis.plot(table["date"], 100 * table["take_rate"], color=COLORS[company])
        end = table.iloc[-1]
        offset = (8, 8) if company == higher_company else (8, -8)
        annotate_end(axis, end["date"], 100 * end["take_rate"], f"{company} {100 * end['take_rate']:.1f}%", COLORS[company], offset)
    axis.set_title(f"Latest gross take rates: Uber {100 * latest['Uber']['take_rate']:.1f}%, Lyft {100 * latest['Lyft']['take_rate']:.1f}%", loc="left", pad=17)
    axis.set_ylabel("Gross take / base fare (%)")
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    style_dates(axis)
    figure.subplots_adjust(bottom=0.16, right=0.86)
    save_figure(figure, "01_take_rate_trend.png", "Source: NYC TLC · Ratio of sums; gross take = base fare − driver pay; not profit. Tips, tolls, taxes and fees excluded.")


def plot_fare_pay(monthly, numbers):
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    baseline = {row["company"]: row for row in numbers["baseline"]}
    for axis, company in zip(axes, COMPANIES):
        table = monthly[monthly["company"] == company].sort_values("date")
        base = table.iloc[0]
        for metric, label, linestyle, offset in [("fare_per_trip", "Fare", "-", (7, 5)), ("driver_pay_per_trip", "Pay", "--", (7, -5))]:
            values = 100 * table[metric] / base[metric]
            axis.plot(table["date"], values, color=COLORS[company], linestyle=linestyle, label=label)
            annotate_end(axis, table.iloc[-1]["date"], values.iloc[-1], f"{label} {values.iloc[-1]:.0f}", COLORS[company], offset)
        row = baseline[company]
        axis.set_title(f"{company}: fare {row['fare_growth_pct']:+.1f}% · pay {row['driver_pay_growth_pct']:+.1f}%", loc="left")
        axis.axhline(100, color="#9ba8b7", linewidth=0.7)
        style_dates(axis)
        axis.legend(frameon=False, loc="upper left")
    axes[0].set_ylabel(f"Mean $/trip index ({numbers['data']['first_month']} = 100)")
    figure.suptitle("Mean base fares and driver pay have grown at different rates", x=0.07, ha="left", fontsize=14, weight="semibold")
    figure.subplots_adjust(bottom=0.17, top=0.8, wspace=0.18, right=0.92)
    save_figure(figure, "02_fare_driver_pay.png", "Source: NYC TLC · Nominal means, indexed at the first month. Trip mix changes; driver pay/trip is not hourly earnings.")


def plot_lyft_share(monthly):
    table = monthly[monthly["company"] == "Lyft"].sort_values("date")
    figure, axis = plt.subplots(figsize=(10.8, 4.3))
    values = 100 * table["share"]
    axis.plot(table["date"], values, color=COLORS["Lyft"])
    axis.fill_between(table["date"], values, alpha=0.07, color=COLORS["Lyft"])
    end = table.iloc[-1]
    annotate_end(axis, end["date"], values.iloc[-1], f"{values.iloc[-1]:.1f}%", COLORS["Lyft"])
    axis.set_title(f"Lyft's share of Uber/Lyft trips ends at {values.iloc[-1]:.1f}%", loc="left", pad=17)
    axis.set_ylabel("Lyft trip share (%)")
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    axis.set_ylim(bottom=0)
    style_dates(axis)
    figure.subplots_adjust(bottom=0.18, right=0.88)
    save_figure(figure, "03_lyft_share.png", "Source: NYC TLC · Clean trips only; denominator is Uber + Lyft, excluding Juno, Via and other services.")


def plot_distance(distance, numbers):
    figure, axis = plt.subplots(figsize=(10.8, 4.6))
    for company in COMPANIES:
        table = distance[distance["company"] == company].set_index("distance_bin").reindex(DISTANCE_BINS)
        axis.plot(range(len(table)), 100 * table["take_rate"], marker="o", markersize=4, color=COLORS[company], label=company)
        for index, value in enumerate(table["take_rate"]):
            other_company = "Lyft" if company == "Uber" else "Uber"
            other_value = distance[(distance["company"] == other_company) & (distance["distance_bin"] == DISTANCE_BINS[index])].iloc[0]["take_rate"]
            offset = 10 if value >= other_value else -15
            axis.annotate(f"{100 * value:.1f}%", (index, 100 * value), xytext=(0, offset), textcoords="offset points", ha="center", color=COLORS[company], fontsize=8)
    axis.axhline(0, linewidth=0.8, color="#8995a6")
    axis.set_xticks(range(len(DISTANCE_BINS)), DISTANCE_BINS)
    axis.set_xlabel("Trip miles (upper boundary included)")
    axis.set_ylabel("Gross take / base fare (%)")
    uber = distance[distance["company"] == "Uber"].set_index("distance_bin")
    axis.set_title(f"Uber take rates: {100 * uber.loc['0-1', 'take_rate']:.1f}% up to 1 mile vs {100 * uber.loc['20+', 'take_rate']:.1f}% above 20 miles", loc="left", pad=17)
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    axis.legend(frameon=False)
    figure.subplots_adjust(bottom=0.19)
    save_figure(figure, "04_distance_take_rate.png", f"Source: NYC TLC · {numbers['data']['recent_start']}–{numbers['data']['recent_end']} · Ratio of sums. Negative take is possible; platform costs excluded.")


def plot_heatmap(hourly, metric, name, title, unit, numbers):
    figure, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True)
    multiplier = 100 if metric == "take_rate" else 1
    minimum = multiplier * hourly[metric].min()
    maximum = multiplier * hourly[metric].max()
    normalizer = Normalize(vmin=minimum, vmax=maximum)
    for axis, company in zip(axes, COMPANIES):
        selected = hourly[hourly["company"] == company]
        matrix = selected.pivot(index="weekday", columns="hour", values=metric).reindex(index=range(7), columns=range(24)) * multiplier
        palette = LinearSegmentedColormap.from_list(company, ["#f4f6fa", COLORS[company]])
        picture = axis.imshow(matrix, cmap=palette, norm=normalizer, aspect="auto", interpolation="nearest")
        axis.set_title(company, loc="left", color=COLORS[company])
        axis.set_xticks(range(0, 24, 3), [f"{hour:02d}" for hour in range(0, 24, 3)])
        axis.set_yticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        axis.set_xlabel("Pickup hour, NYC local time")
        axis.grid(False)
        bar = figure.colorbar(picture, ax=axis, fraction=0.03, pad=0.025)
        bar.set_label(unit)
    uber = hourly[hourly["company"] == "Uber"]
    maximum_row = uber.loc[uber[metric].idxmax()]
    weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][int(maximum_row["weekday"])]
    maximum_value = multiplier * maximum_row[metric]
    if metric == "take_rate":
        title = f"Uber's highest weekday-hour take rate is {maximum_value:.1f}% ({weekday} {int(maximum_row['hour']):02d}:00)"
    else:
        title = f"Uber's longest weekday-hour mean wait is {maximum_value:.1f} minutes ({weekday} {int(maximum_row['hour']):02d}:00)"
    figure.suptitle(title, x=0.075, ha="left", weight="semibold", fontsize=14)
    figure.subplots_adjust(bottom=0.19, top=0.8, wspace=0.16)
    note = "Ratios of summed take and base fare." if metric == "take_rate" else "Only request-to-pickup waits of 0–60 minutes enter the denominator."
    save_figure(figure, name, f"Source: NYC TLC · {numbers['data']['recent_start']}–{numbers['data']['recent_end']} · {note} Both panels use the same numeric scale.")


def plot_congestion_comparison(comparison):
    selected = comparison[comparison["period"] == "pooled"]
    metrics = ["trips", "fare_per_trip", "driver_pay_per_trip", "take_per_trip"]
    labels = ["Trips", "Base fare / trip", "Driver pay / trip", "Gross take / trip"]
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), sharey=True, sharex=True)
    for axis, company in zip(axes, COMPANIES):
        table = selected[selected["company"] == company].set_index("metric").reindex(metrics)
        axis.barh([index - 0.17 for index in range(4)], table["zone_change"], height=0.3, color=COLORS[company], label="Zone-linked")
        axis.barh([index + 0.17 for index in range(4)], table["other_change"], height=0.3, color="#aeb8c5", label="Other")
        for index, row in enumerate(table.to_dict("records")):
            for column, offset, color in [("zone_change", -0.17, COLORS[company]), ("other_change", 0.17, "#657184")]:
                value = row[column]
                axis.annotate(f"{value:+.1f}%", (value, index + offset), xytext=(4 if value >= 0 else -4, 0), textcoords="offset points", ha="left" if value >= 0 else "right", va="center", fontsize=8, color=color)
        axis.axvline(0, color="#8995a6", linewidth=0.8)
        axis.set_title(company, loc="left", color=COLORS[company])
        axis.set_yticks(range(4), labels)
        axis.set_xlabel("2025 versus 2024 change (%)")
        axis.margins(x=0.25)
        axis.legend(frameon=False, loc="lower right", fontsize=8)
    axes[0].invert_yaxis()
    uber_trips = selected[(selected["company"] == "Uber") & (selected["metric"] == "trips")].iloc[0]
    figure.suptitle(f"Uber zone-linked volume: {uber_trips['zone_change']:+.1f}% vs {uber_trips['other_change']:+.1f}% elsewhere", x=0.09, ha="left", weight="semibold", fontsize=14)
    figure.subplots_adjust(bottom=0.17, top=0.8, wspace=0.2)
    save_figure(figure, "07_congestion_comparison.png", "Source: NYC TLC · Pooled matched Feb–Dec 2025 vs same 2024 months. Fixed fee-inferred endpoint zones. Descriptive; not a causal policy estimate.")


def plot_congestion_speed(congestion):
    table = congestion[congestion["month"] >= "2024-01"].copy()
    table["date"] = pd.to_datetime(table["month"])
    figure, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), sharey=True)
    for axis, company in zip(axes, COMPANIES):
        for group, style, label, offset in [("Zone-linked", "-", "Zone", (6, -5)), ("Other", "--", "Other", (6, 5))]:
            selected = table[(table["company"] == company) & (table["zone_group"] == group)].sort_values("date")
            axis.plot(selected["date"], selected["speed_mph"], color=COLORS[company], linestyle=style, label=label)
            end = selected.iloc[-1]
            annotate_end(axis, end["date"], end["speed_mph"], f"{label} {end['speed_mph']:.1f}", COLORS[company], offset)
        axis.axvline(pd.Timestamp("2025-01-05"), color="#929dab", linewidth=1, linestyle=":")
        axis.set_title(company, loc="left", color=COLORS[company])
        axis.legend(frameon=False, fontsize=9)
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        axis.tick_params(axis="x", rotation=25)
        left, right = axis.get_xlim()
        axis.set_xlim(left, right + (right - left) * 0.17)
    axes[0].set_ylabel("Occupied trip speed (mph)")
    uber_latest = table[(table["company"] == "Uber") & (table["month"] == table["month"].max())].set_index("zone_group")
    figure.suptitle(f"Uber's latest zone-linked speed is {uber_latest.loc['Zone-linked', 'speed_mph']:.1f} mph vs {uber_latest.loc['Other', 'speed_mph']:.1f} elsewhere", x=0.07, ha="left", weight="semibold", fontsize=14)
    figure.subplots_adjust(bottom=0.22, top=0.81, right=0.9, wspace=0.15)
    save_figure(figure, "08_congestion_speed.png", "Source: NYC TLC · Total miles / total occupied trip hours. Dotted line: Jan 5, 2025. Endpoints infer zones; pass-through trips may be missed.")


def main():
    set_style()
    CHARTS.mkdir(parents=True, exist_ok=True)
    numbers = json.loads((RESULTS / "key_numbers.json").read_text())
    monthly = pd.read_csv(RESULTS / "monthly_metrics.csv")
    monthly["date"] = pd.to_datetime(monthly["month"])
    distance = pd.read_csv(RESULTS / "distance_metrics.csv")
    hourly = pd.read_csv(RESULTS / "hourly_metrics.csv")
    comparison = pd.read_csv(RESULTS / "congestion_comparison.csv")
    congestion = pd.read_csv(RESULTS / "congestion_trends.csv")
    plot_take_rate(monthly, numbers)
    plot_fare_pay(monthly, numbers)
    plot_lyft_share(monthly)
    plot_distance(distance, numbers)
    plot_heatmap(hourly, "take_rate", "05_hourly_take_rate.png", "Gross take rates differ by weekday and pickup hour", "Gross take / base fare (%)", numbers)
    plot_heatmap(hourly, "avg_wait_minutes", "06_hourly_wait.png", "Pickup waits reveal when supply is tightest", "Mean valid wait (minutes)", numbers)
    plot_congestion_comparison(comparison)
    plot_congestion_speed(congestion)
    print("Wrote eight charts from result CSVs.")


if __name__ == "__main__":
    main()

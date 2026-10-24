"""Check pooled business ratios and matched calendar-month comparisons by hand."""
import math

import pandas as pd
import pytest

from analyze import SUM_COLUMNS, add_metrics, build_congestion_comparison, build_external_validation, sum_groups, summarize_convergence


def make_totals(**changes):
    """Start with additive totals so every fixture has an explicit denominator."""
    row = {column: 0 for column in SUM_COLUMNS}
    row.update(changes)
    return row


def test_metrics_pool_numerators_before_dividing():
    table = pd.DataFrame([
        make_totals(company='Uber', trips=1, fare=10, driver_pay=12, take=-2,
                    miles=1, minutes=10, wait_minutes=1, wait_trips=1),
        make_totals(company='Uber', trips=9, fare=90, driver_pay=45, take=45,
                    miles=9, minutes=50, wait_minutes=9, wait_trips=3),
    ])
    pooled = sum_groups(table, ['company']).iloc[0]
    assert pooled['take_rate'] == pytest.approx(0.43)
    assert pooled['take_per_trip'] == pytest.approx(4.3)
    assert pooled['fare_per_trip'] == pytest.approx(10)
    assert pooled['avg_wait_minutes'] == pytest.approx(2.5)
    assert pooled['speed_mph'] == pytest.approx(10)


def test_empty_denominators_stay_missing_instead_of_infinite():
    row = add_metrics(pd.DataFrame([make_totals()])).iloc[0]
    for column in ['take_rate', 'fare_per_trip', 'take_per_trip', 'speed_mph',
                   'fare_per_mile', 'avg_wait_minutes', 'negative_take_share']:
        assert math.isnan(row[column])


def test_convergence_reports_both_company_endpoints_and_observed_recent_range():
    table = pd.DataFrame([
        {'month': '2019-02', 'company': 'Uber', 'take_rate': 0.02},
        {'month': '2019-02', 'company': 'Lyft', 'take_rate': 0.32},
        {'month': '2019-03', 'company': 'Uber', 'take_rate': -0.05},
        {'month': '2019-03', 'company': 'Lyft', 'take_rate': 0.30},
        {'month': '2024-01', 'company': 'Uber', 'take_rate': 0.28},
        {'month': '2024-01', 'company': 'Lyft', 'take_rate': 0.19},
        {'month': '2026-08', 'company': 'Uber', 'take_rate': 0.22},
        {'month': '2026-08', 'company': 'Lyft', 'take_rate': 0.24},
    ])
    result = summarize_convergence(table)
    assert result['early_take_rates']['2019-02'] == {'Uber': 0.02, 'Lyft': 0.32}
    assert result['early_take_rates']['2019-03']['Uber'] == -0.05
    assert result['minimum'] == pytest.approx(0.19)
    assert result['maximum'] == pytest.approx(0.28)
    assert result['company_ranges']['Uber'] == {'minimum': 0.22, 'maximum': 0.28}
    assert result['company_ranges']['Lyft'] == {'minimum': 0.19, 'maximum': 0.24}
    assert result['range_start'] == '2024-01'
    assert result['range_end'] == '2026-08'


def test_external_validation_uses_all_raw_rows_before_cleaning():
    audit = pd.DataFrame([
        {'month': '2025-12', 'company': 'Uber', 'raw_rows': 7, 'kept_rows': 4},
        {'month': '2025-12', 'company': 'Lyft', 'raw_rows': 3, 'kept_rows': 2},
        {'month': '2025-12', 'company': 'Other', 'raw_rows': 2, 'kept_rows': 1},
        {'month': '2025-11', 'company': 'Uber', 'raw_rows': 100, 'kept_rows': 90},
    ])
    context = {'sources': [{
        'id': 'tlc_official_trip_count', 'month': '2025-12', 'raw_trips': 10,
        'url': 'https://example.org/official-count',
    }]}
    row = build_external_validation(audit, context).iloc[0]
    assert row['raw_rows'] == 12
    assert row['official_rows'] == 10
    assert row['difference_rows'] == 2
    assert row['difference_pct'] == pytest.approx(20)
    assert row['month'] == '2025-12'


def test_congestion_pairs_same_months_and_excludes_january_and_unmatched_months():
    table = pd.DataFrame([
        make_totals(company='Uber', month='2024-02', zone_group='Zone-linked',
                    trips=10, fare=100, driver_pay=80, take=20, miles=10, minutes=120),
        make_totals(company='Uber', month='2025-02', zone_group='Zone-linked',
                    trips=20, fare=240, driver_pay=180, take=60, miles=20, minutes=120,
                    cbd_congestion_fee=30, charged_trips=20),
        make_totals(company='Uber', month='2024-02', zone_group='Other',
                    trips=20, fare=400, driver_pay=300, take=100, miles=20, minutes=120),
        make_totals(company='Uber', month='2025-02', zone_group='Other',
                    trips=30, fare=660, driver_pay=480, take=180, miles=30, minutes=180),
        make_totals(company='Uber', month='2025-01', zone_group='Zone-linked',
                    trips=999, fare=99999),
        make_totals(company='Uber', month='2025-03', zone_group='Zone-linked',
                    trips=999, fare=99999),
    ])
    comparison, fees, matched = build_congestion_comparison(table, sorted(table['month'].unique()))
    assert matched == ['2025-02']
    pooled = comparison[(comparison['company'] == 'Uber') & (comparison['period'] == 'pooled')].set_index('metric')
    assert pooled.loc['trips', 'zone_2024'] == 10
    assert pooled.loc['trips', 'zone_2025'] == 20
    assert pooled.loc['trips', 'difference_in_changes'] == pytest.approx(50)
    assert pooled.loc['fare_per_trip', 'zone_change'] == pytest.approx(20)
    assert pooled.loc['fare_per_trip', 'other_change'] == pytest.approx(10)
    assert pooled.loc['fare_per_trip', 'difference_in_changes'] == pytest.approx(10)
    assert pooled.loc['take_rate', 'zone_change'] == pytest.approx(5)
    assert pooled.loc['speed_mph', 'zone_change'] == pytest.approx(100)
    charged = fees[(fees['year'] == 2025) & (fees['zone_group'] == 'Zone-linked')].iloc[0]
    assert charged['charged_fee_per_charged_trip'] == pytest.approx(1.5)

"""Check business definitions against hand-written trips, never downloaded data."""
from datetime import datetime, timedelta

import duckdb
import pandas as pd
import pytest

from build_data import OPTIONAL_NUMBERS, open_month, read_sql


def make_trip(**changes):
    """Return one valid Uber trip that can be changed for an edge case."""
    trip = {
        'hvfhs_license_num': 'HV0003',
        'request_datetime': datetime(2025, 2, 3, 11, 55),
        'pickup_datetime': datetime(2025, 2, 3, 12),
        'PULocationID': 100,
        'DOLocationID': 200,
        'trip_miles': 2.0,
        'trip_time': 600,
        'base_passenger_fare': 10.0,
        'driver_pay': 8.0,
        'shared_request_flag': 'N',
    }
    trip.update(changes)
    return trip


@pytest.fixture
def load_month(tmp_path):
    """Write tiny parquet files and load the same SQL used by the pipeline."""
    connections = []

    def load_rows(rows, zone_ids=(), drop_columns=()):
        table = pd.DataFrame(rows).drop(columns=list(drop_columns), errors='ignore')
        for column in ['request_datetime', 'pickup_datetime']:
            if column in table:
                table[column] = pd.to_datetime(table[column])
        path = tmp_path / f'trips_{len(connections)}.parquet'
        table.to_parquet(path, index=False)
        connection = duckdb.connect()
        connections.append(connection)
        missing = open_month(connection, path, '2025-02', zone_ids)
        return connection, missing

    yield load_rows
    for connection in connections:
        connection.close()


def read_summary(connection, summary='monthly'):
    """Select one grain from the production grouping-sets query."""
    table = connection.execute(read_sql('aggregate')).df()
    return table.loc[table['summary'] == summary].reset_index(drop=True)


def test_cleaning_keeps_boundaries_and_audits_excluded_rows(load_month):
    # Upper and lower bounds must survive; each invalid trip fails one rule.
    valid = [
        make_trip(trip_time=60, trip_miles=0.001, driver_pay=0),
        make_trip(trip_time=14400, trip_miles=100),
        make_trip(base_passenger_fare=0.01),
    ]
    invalid = [
        make_trip(base_passenger_fare=0),
        make_trip(base_passenger_fare=-1),
        make_trip(driver_pay=-0.01),
        make_trip(trip_miles=0),
        make_trip(trip_miles=100.001),
        make_trip(trip_time=59),
        make_trip(trip_time=14401),
        make_trip(pickup_datetime=datetime(2025, 1, 31, 23, 59)),
        make_trip(pickup_datetime=datetime(2025, 3, 1)),
    ]
    connection, _ = load_month(valid + invalid + [make_trip(hvfhs_license_num='HV0002')])
    summary = read_summary(connection).iloc[0]
    assert summary.company == 'Uber'
    assert summary.trips == 3
    assert summary.fare == pytest.approx(20.01)
    audit = connection.execute(read_sql('audit')).df().set_index('company')
    assert audit.loc['Uber', 'raw_rows'] == 12
    assert audit.loc['Uber', 'kept_rows'] == 3
    assert audit.loc['Juno', 'raw_rows'] == 1
    assert audit.loc['Juno', 'kept_rows'] == 1


def test_invalid_waits_do_not_remove_otherwise_valid_trips(load_month):
    pickup = datetime(2025, 2, 3, 12)
    waits = [0, 30, 60, -1, 61, None]
    rows = [make_trip(request_datetime=pickup - timedelta(minutes=wait) if wait is not None else None)
            for wait in waits]
    connection, _ = load_month(rows)
    summary = read_summary(connection).iloc[0]
    assert summary.trips == 6
    assert summary.wait_trips == 3
    assert summary.wait_minutes == pytest.approx(90)
    assert summary.wait_minutes / summary.wait_trips == pytest.approx(30)


def test_missing_historical_fees_are_zero_but_missing_waits_are_not(load_month):
    connection, missing = load_month([make_trip()], drop_columns=['request_datetime', 'shared_request_flag'])
    summary = read_summary(connection).iloc[0]
    assert set(missing) == set(OPTIONAL_NUMBERS)
    assert all(summary[column] == 0 for column in OPTIONAL_NUMBERS)
    assert summary.wait_minutes == 0
    assert summary.wait_trips == 0
    assert summary.shared_trips == 0
    assert summary.trips == 1


def test_present_null_optional_fees_are_zero_filled(load_month):
    changes = {column: None for column in OPTIONAL_NUMBERS}
    connection, missing = load_month([make_trip(**changes)])
    summary = read_summary(connection).iloc[0]
    assert missing == []
    assert all(summary[column] == 0 for column in OPTIONAL_NUMBERS)


def test_take_uses_base_fare_and_keeps_negative_take(load_month):
    # Deliberately unequal fares catch an accidental mean of per-trip rates.
    rows = [
        make_trip(base_passenger_fare=10, driver_pay=12, tips=50, tolls=40,
                  congestion_surcharge=2.75, cbd_congestion_fee=1.5, shared_request_flag='Y'),
        make_trip(base_passenger_fare=90, driver_pay=45, tips=20, tolls=30),
    ]
    connection, _ = load_month(rows)
    summary = read_summary(connection).iloc[0]
    assert summary.fare == 100
    assert summary.driver_pay == 57
    assert summary['take'] == 43
    assert summary['take'] / summary.fare == pytest.approx(0.43)
    assert summary['take'] / summary.fare != pytest.approx(0.15)
    assert summary.negative_take_trips == 1
    assert summary.shared_trips == 1
    assert summary.charged_trips == 1
    assert summary.tips == 70
    assert summary.tolls == 70


def test_distance_bins_assign_exact_edges_to_lower_interval(load_month):
    distances = [0.1, 1, 1.001, 2, 2.001, 3, 3.001, 5, 5.001, 10, 10.001, 20, 20.001, 100]
    connection, _ = load_month([make_trip(trip_miles=distance) for distance in distances])
    table = read_summary(connection, 'distance').set_index('distance_bin')
    assert set(table.index) == {'0-1', '1-2', '2-3', '3-5', '5-10', '10-20', '20+'}
    assert table.trips.to_dict() == {'0-1': 2, '1-2': 2, '2-3': 2, '3-5': 2,
                                    '5-10': 2, '10-20': 2, '20+': 2}
    assert table.loc['10-20', 'miles'] == pytest.approx(30.001)
    assert table.trips.sum() == read_summary(connection).trips.sum()


def test_airports_and_zone_linkage_use_either_endpoint(load_month):
    rows = [
        make_trip(PULocationID=1, DOLocationID=200),
        make_trip(PULocationID=100, DOLocationID=132),
        make_trip(PULocationID=138, DOLocationID=100),
        make_trip(PULocationID=42, DOLocationID=200),
        make_trip(PULocationID=100, DOLocationID=42),
        make_trip(PULocationID=100, DOLocationID=200),
    ]
    connection, _ = load_month(rows, zone_ids=[42])
    airport = read_summary(connection, 'airport').set_index('is_airport')
    congestion = read_summary(connection, 'congestion').set_index('zone_group')
    assert airport.loc[1, 'trips'] == 3
    assert airport.loc[0, 'trips'] == 3
    assert congestion.loc['Zone-linked', 'trips'] == 2
    assert congestion.loc['Other', 'trips'] == 4


def test_hourly_dimensions_are_monday_zero_and_pickup_hour(load_month):
    connection, _ = load_month([
        make_trip(pickup_datetime=datetime(2025, 2, 3, 23)),
        make_trip(pickup_datetime=datetime(2025, 2, 9, 0)),
    ])
    hourly = read_summary(connection, 'hourly')
    assert set(zip(hourly.weekday, hourly.hour)) == {(0, 23), (6, 0)}
    assert hourly.trips.sum() == 2


def test_zone_inference_requires_strictly_more_than_95_percent(load_month):
    # Exactly 950 of 1,000 is 95%; pooling both companies is intentional.
    rows = []
    for location, charged_count in [(4, 950), (12, 951), (13, 949)]:
        for index in range(1000):
            rows.append(make_trip(PULocationID=location,
                                  hvfhs_license_num='HV0003' if index % 2 else 'HV0005',
                                  cbd_congestion_fee=1.5 if index < charged_count else 0))
    rows.append(make_trip(PULocationID=12, base_passenger_fare=0, cbd_congestion_fee=0))
    connection, _ = load_month(rows)
    zones = connection.execute(read_sql('infer_cbd_zones')).df().set_index('location_id')
    assert zones.loc[4, 'charged_share'] == pytest.approx(0.95)
    assert not zones.loc[4, 'in_zone']
    assert zones.loc[12, 'in_zone']
    assert zones.loc[12, 'trips'] == 1000
    assert not zones.loc[13, 'in_zone']


def test_missing_economic_fields_fail_instead_of_creating_fabricated_fares(load_month):
    with pytest.raises(ValueError, match='Missing core fields.*driver_pay'):
        load_month([make_trip()], drop_columns=['driver_pay'])


def test_zone_inference_excludes_non_manhattan_and_small_samples(load_month):
    # High fee shares alone cannot admit Newark, Queens, or a tiny island sample.
    rows = []
    for location, count in [(4, 1000), (12, 999), (1, 1000), (10, 1000), (105, 2)]:
        rows.extend(make_trip(PULocationID=location, cbd_congestion_fee=1.5)
                    for _ in range(count))
    connection, _ = load_month(rows)
    zones = connection.execute(read_sql('infer_cbd_zones')).df()
    inferred = zones.loc[zones.in_zone]
    assert inferred.location_id.tolist() == [4]
    assert inferred.borough.eq('Manhattan').all()
    assert inferred.trips.ge(1000).all()

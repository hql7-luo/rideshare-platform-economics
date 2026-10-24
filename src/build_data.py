"""Download one TLC month, summarize with DuckDB, and remove the raw parquet."""
import argparse
import hashlib
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
import requests

from config import (RAW, INTERIM, PROCESSED, SQL, TRIP_URL, ZONE_URL,
                    FIRST_MONTH, CBD_TRAIN_MONTH, CBD_RULE_VERSION,
                    CONGESTION_FIRST_MONTH, SUM_COLUMNS, create_folders)

TABLE_DIMS = {'monthly': [], 'distance': ['distance_bin'],
              'hourly': ['weekday', 'hour'], 'airport': ['is_airport'],
              'pickup_zone': ['location_id'], 'congestion': ['zone_group']}
CORE_COLUMNS = ['hvfhs_license_num', 'request_datetime', 'pickup_datetime',
                'pulocationid', 'dolocationid', 'trip_miles', 'trip_time',
                'base_passenger_fare', 'driver_pay']
OPTIONAL_NUMBERS = ['tips', 'tolls', 'bcf', 'sales_tax', 'congestion_surcharge',
                    'airport_fee', 'cbd_congestion_fee']


def read_sql(name, **values):
    """Read an inspectable SQL query and substitute controlled local values."""
    return (SQL / f'{name}.sql').read_text().format(**values)


def list_months(first, last):
    """Return all month labels in a closed interval."""
    return pd.period_range(first, last, freq='M').astype(str).tolist()


def discover_latest(session):
    """Check from the current Los Angeles month backwards, without guessing lag."""
    current = datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m')
    checked = []
    for month in reversed(list_months(FIRST_MONTH, current)):
        response = session.head(TRIP_URL.format(month=month), timeout=45)
        checked.append({'month': month, 'status': response.status_code})
        print(f'Check {month}: HTTP {response.status_code}', flush=True)
        if response.status_code == 200:
            return month, checked
        if response.status_code not in (403, 404):
            response.raise_for_status()
    raise RuntimeError('No TLC month can be downloaded. Stop for user assistance.')


def download_file(session, url, target):
    """Stream to disk and retry incomplete transfers without loading them in RAM."""
    for attempt in range(3):
        try:
            with session.get(url, stream=True, timeout=(30, 120)) as response:
                response.raise_for_status()
                expected = int(response.headers.get('Content-Length', 0))
                with target.open('wb') as stream:
                    for block in response.iter_content(4 * 1024 * 1024):
                        stream.write(block)
            if expected and target.stat().st_size != expected:
                raise IOError('Incomplete download')
            return
        except (requests.RequestException, IOError):
            target.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def open_month(connection, parquet_path, month, zone_ids):
    """Normalize historical schemas and prepare shared cleaning views."""
    available = {column.lower(): column for column in connection.read_parquet(str(parquet_path)).columns}
    missing = set(CORE_COLUMNS) - set(available)
    if missing - {'request_datetime'}:
        raise ValueError(f'Missing core fields: {sorted(missing)}')
    selections = []
    for column in CORE_COLUMNS + OPTIONAL_NUMBERS + ['shared_request_flag']:
        alias = 'fare' if column == 'base_passenger_fare' else column
        if column in available:
            value = f'"{available[column]}"'
            if column in OPTIONAL_NUMBERS:
                value = f'coalesce({value}, 0)'
        elif column == 'request_datetime':
            value = 'NULL::TIMESTAMP'
        elif column == 'shared_request_flag':
            value = "'N'"
        else:
            value = '0.0'
        selections.append(f'{value} AS {alias}')
    connection.execute(read_sql('read_raw', columns=', '.join(selections),
                                path=str(parquet_path).replace("'", "''")))
    connection.execute(read_sql('prepare', month=month,
                                zone_ids=','.join(map(str, zone_ids)) or '-1'))
    connection.execute(read_sql('clean'))
    connection.execute(read_sql('read_zones', path=str(PROCESSED / 'taxi_zone_lookup.csv').replace("'", "''")))
    return sorted(set(OPTIONAL_NUMBERS) - set(available))


def process_month(session, month, zone_ids, train=False):
    """Write a completed checkpoint only after every summary has succeeded."""
    started = time.monotonic()
    raw_path = RAW / f'fhvhv_tripdata_{month}.parquet'
    target = INTERIM / month
    staging = INTERIM / f'{month}.partial'
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    print(f'Download {month}', flush=True)
    download_file(session, TRIP_URL.format(month=month), raw_path)
    download_seconds = time.monotonic() - started
    raw_bytes = raw_path.stat().st_size
    digest = hashlib.sha256()
    with raw_path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    connection = duckdb.connect()
    connection.execute("SET memory_limit='2GB'")
    connection.execute('SET threads=4')
    connection.execute(f"SET temp_directory='{str(INTERIM / 'duckdb_temp')}'")
    missing = open_month(connection, raw_path, month, zone_ids)
    if train:
        zones = connection.execute(read_sql('infer_cbd_zones')).df()
        inferred_path = PROCESSED / 'inferred_cbd_zones.csv'
        old_zones = pd.read_csv(inferred_path) if inferred_path.exists() else pd.DataFrame()
        old_ids = old_zones.loc[old_zones.in_zone.astype(str).str.lower() == 'true', 'location_id'].astype(int).tolist() if not old_zones.empty else []
        zones['rule_version'] = CBD_RULE_VERSION
        zones.to_csv(PROCESSED / 'inferred_cbd_zones.csv', index=False)
        zone_ids = zones.loc[zones.in_zone, 'location_id'].astype(int).tolist()
        print(f'Old zones ({len(old_ids)}): {old_ids}', flush=True)
        print(f'New zones ({len(zone_ids)}): {zone_ids}', flush=True)
        print(f'Removed: {sorted(set(old_ids) - set(zone_ids))}; added: {sorted(set(zone_ids) - set(old_ids))}', flush=True)
        revision = zones[['location_id', 'borough', 'zone', 'trips', 'charged_share', 'in_zone']].copy()
        revision['previous_in_zone'] = revision.location_id.isin(old_ids)
        revision.to_csv(PROCESSED / 'cbd_zone_revision.csv', index=False)
        open_month(connection, raw_path, month, zone_ids)
    audit = connection.execute(read_sql('audit')).df()
    audit.insert(0, 'month', month)
    audit.to_csv(staging / 'audit.csv', index=False)
    summaries = connection.execute(read_sql('aggregate')).df()
    for name, dimensions in TABLE_DIMS.items():
        table = summaries.loc[summaries.summary == name, ['company'] + dimensions + SUM_COLUMNS].copy()
        for column in ['weekday', 'hour', 'is_airport', 'location_id']:
            if column in table:
                table[column] = table[column].astype(int)
        table.insert(0, 'month', month)
        table.to_csv(staging / f'{name}.csv', index=False, float_format='%.6f')
    connection.close()
    metadata = {'month': month, 'url': TRIP_URL.format(month=month),
                'bytes': raw_bytes, 'sha256': digest.hexdigest(),
                'raw_rows': int(audit.raw_rows.sum()),
                'kept_rows': int(audit.loc[audit.company.isin(['Uber','Lyft']), 'kept_rows'].sum()),
                'missing_zero_columns': missing,
                'download_seconds': round(download_seconds, 2),
                'total_seconds': round(time.monotonic() - started, 2),
                'congestion_rule_version': CBD_RULE_VERSION}
    (staging / 'complete.json').write_text(json.dumps(metadata, indent=2))
    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)
    raw_path.unlink()
    print(f'Finished {month}: {metadata["raw_rows"]:,} raw rows, '
          f'{metadata["total_seconds"]:.1f}s; raw file removed', flush=True)
    return zone_ids


def combine_checkpoints(months, latest, discovery, sampling):
    """Publish only small additive tables and their provenance manifest."""
    complete = [month for month in months if (INTERIM / month / 'complete.json').exists()]
    for name in ['audit'] + list(TABLE_DIMS):
        if complete:
            table = pd.concat([pd.read_csv(INTERIM / month / f'{name}.csv') for month in complete], ignore_index=True)
            if name == 'congestion':
                table = table.loc[table.month >= CONGESTION_FIRST_MONTH]
            table.to_csv(PROCESSED / f'{name}.csv', index=False, float_format='%.6f')
    metadata = [json.loads((INTERIM / month / 'complete.json').read_text()) for month in complete]
    congestion_complete = all(item.get('congestion_rule_version') == CBD_RULE_VERSION
                              for item in metadata if item['month'] >= CONGESTION_FIRST_MONTH)
    manifest = {'created_at': datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
                'latest_month': latest, 'first_month': FIRST_MONTH, 'months': complete,
                'expected_months': months, 'sampling': sampling,
                'all_selected_months_complete': complete == months and congestion_complete,
                'cbd_training_month': CBD_TRAIN_MONTH,
                'cbd_threshold': 'Manhattan; >=1000 valid Uber/Lyft pickups in 2025-02; >95% with fee>0',
                'congestion_first_month': CONGESTION_FIRST_MONTH,
                'congestion_rule_version': CBD_RULE_VERSION,
                'discovery': discovery, 'files': metadata,
                'source': 'NYC TLC High Volume FHV trip records', 'zone_url': ZONE_URL}
    (PROCESSED / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    size = sum(path.stat().st_size for path in PROCESSED.iterdir() if path.is_file())
    if size > 50_000_000:
        raise RuntimeError(f'Processed output exceeds 50 MB: {size}')


def restore_checkpoints(manifest):
    """Reuse committed summaries after cloning, even when interim files are absent."""
    months = manifest.get('months', [])
    if not months or any(not (PROCESSED / f'{name}.csv').exists()
                         for name in ['audit'] + list(TABLE_DIMS)):
        return
    tables = {name: pd.read_csv(PROCESSED / f'{name}.csv')
              for name in ['audit'] + list(TABLE_DIMS)}
    for name, table in tables.items():
        missing_months = set(months) - set(table['month'])
        if name == 'congestion' and manifest.get('congestion_first_month'):
            missing_months = {month for month in missing_months if month >= manifest['congestion_first_month']}
        if missing_months:
            raise ValueError(f'Committed {name} summary is missing months: {sorted(missing_months)}')
    metadata = {item['month']: item for item in manifest.get('files', [])}
    for month in months:
        folder = INTERIM / month
        if (folder / 'complete.json').exists() or month not in metadata:
            continue
        monthly = tables['monthly'].loc[tables['monthly'].month == month]
        expected = monthly.set_index('company')['trips'].to_dict()
        audited = tables['audit'].loc[(tables['audit'].month == month)
                                      & tables['audit'].company.isin(['Uber', 'Lyft'])]
        if audited.set_index('company')['kept_rows'].to_dict() != expected:
            raise ValueError(f'Committed monthly and audit counts disagree: {month}')
        for name in TABLE_DIMS:
            if name == 'congestion' and month < manifest.get('congestion_first_month', FIRST_MONTH):
                continue
            table = tables[name].loc[tables[name].month == month]
            if table.groupby('company')['trips'].sum().to_dict() != expected:
                raise ValueError(f'Committed {name} counts do not reconcile: {month}')
        folder.mkdir(exist_ok=True)
        for name, table in tables.items():
            table.loc[table.month == month].to_csv(folder / f'{name}.csv', index=False,
                                                   float_format='%.6f')
        (folder / 'complete.json').write_text(json.dumps(metadata[month], indent=2))


def build_data():
    """Resume completed months, with an explicit two-hour historical sampling rule."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--latest', help='Optional pinned end month for reproducibility')
    parser.add_argument('--full-history', action='store_true', help='Disable the two-hour sampling fallback')
    args = parser.parse_args()
    create_folders()
    # Discard an interrupted raw download before starting another month.
    for raw_path in RAW.glob('fhvhv_tripdata_*.parquet'):
        raw_path.unlink()
    session = requests.Session()
    latest, discovery = (args.latest, []) if args.latest else discover_latest(session)
    all_months = list_months(FIRST_MONTH, latest)
    old_manifest = json.loads((PROCESSED / 'manifest.json').read_text()) if (PROCESSED / 'manifest.json').exists() else {}
    restore_checkpoints(old_manifest)
    sampling = 'Full monthly coverage' if args.full_history else old_manifest.get('sampling', 'Full monthly coverage')
    sampled = 'quarter' in sampling.lower() and not args.full_history
    zone_path = PROCESSED / 'taxi_zone_lookup.csv'
    if not zone_path.exists():
        download_file(session, ZONE_URL, zone_path)
        # Normalize line endings without changing the source values.
        zone_path.write_text(zone_path.read_text())
    inferred_path = PROCESSED / 'inferred_cbd_zones.csv'
    zones = pd.read_csv(inferred_path) if inferred_path.exists() else pd.DataFrame()
    if zones.empty or 'rule_version' not in zones or not zones.rule_version.eq(CBD_RULE_VERSION).all():
        process_month(session, CBD_TRAIN_MONTH, [], train=True)
    zones = pd.read_csv(inferred_path)
    zone_ids = zones.loc[zones.in_zone.astype(str).str.lower() == 'true', 'location_id'].astype(int).tolist()
    if not zone_ids:
        raise RuntimeError('No fee zone inferred; investigate the training file.')
    # Start with a recent month to measure realistic full-history download time.
    order = [latest] + [month for month in reversed(all_months) if month != latest]
    for month in order:
        if sampled and month < '2023-01' and month[5:] not in ['02' if month[:4]=='2019' else '01', '04','07','10']:
            continue
        checkpoint = INTERIM / month / 'complete.json'
        if checkpoint.exists():
            metadata = json.loads(checkpoint.read_text())
            if month < CONGESTION_FIRST_MONTH or metadata.get('congestion_rule_version') == CBD_RULE_VERSION:
                continue
        process_month(session, month, zone_ids)
        completed = [json.loads(path.read_text()) for path in INTERIM.glob('????-??/complete.json')]
        if not sampled and not args.full_history and completed:
            mean_download = sum(item['download_seconds'] for item in completed) / len(completed)
            estimated_download = mean_download * len(all_months)
            if estimated_download > 7200 or sum(item['download_seconds'] for item in completed) > 7200:
                sampled = True
                sampling = ('Quarterly historical sample because projected full download exceeded 2h: '
                            '2019 Feb/Apr/Jul/Oct; 2020-2022 Jan/Apr/Jul/Oct; monthly from 2023')
                print(sampling, flush=True)
        selected = [item for item in all_months if not sampled or item >= '2023-01'
                    or item[5:] in ['02' if item[:4]=='2019' else '01','04','07','10']]
        combine_checkpoints(selected, latest, discovery, sampling)
    selected = [item for item in all_months if not sampled or item >= '2023-01'
                or item[5:] in ['02' if item[:4]=='2019' else '01','04','07','10']]
    combine_checkpoints(selected, latest, discovery, sampling)
    print(f'Ready: {len(selected)} months through {latest}', flush=True)


if __name__ == '__main__':
    build_data()

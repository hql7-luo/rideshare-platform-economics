"""Check that committed summaries restore safely without raw trip downloads."""
import json

import pandas as pd
import pytest

import build_data
from config import SUM_COLUMNS


@pytest.fixture
def saved_summaries(tmp_path, monkeypatch):
    """Build one complete month whose grains all reconcile to the audit."""
    processed = tmp_path / 'processed'
    interim = tmp_path / 'interim'
    processed.mkdir()
    interim.mkdir()
    monkeypatch.setattr(build_data, 'PROCESSED', processed)
    monkeypatch.setattr(build_data, 'INTERIM', interim)
    month = '2025-02'
    dimensions = {'distance_bin': '1-2', 'weekday': 0, 'hour': 12,
                  'is_airport': 0, 'location_id': 100, 'zone_group': 'Other'}
    for name, columns in build_data.TABLE_DIMS.items():
        rows = []
        for company, trips in [('Uber', 2), ('Lyft', 1)]:
            row = {column: 0 for column in SUM_COLUMNS}
            row.update(month=month, company=company, trips=trips,
                       fare=10 * trips, driver_pay=8 * trips, take=2 * trips)
            row.update({column: dimensions[column] for column in columns})
            rows.append(row)
        pd.DataFrame(rows).to_csv(processed / f'{name}.csv', index=False)
    pd.DataFrame([
        {'month': month, 'company': 'Uber', 'raw_rows': 3, 'kept_rows': 2},
        {'month': month, 'company': 'Lyft', 'raw_rows': 1, 'kept_rows': 1},
    ]).to_csv(processed / 'audit.csv', index=False)
    metadata = {'month': month, 'raw_rows': 4, 'kept_rows': 3,
                'download_seconds': 10, 'total_seconds': 15}
    manifest = {'months': [month], 'files': [metadata]}
    return processed, interim, manifest


def test_restore_reuses_committed_month_without_a_raw_file(saved_summaries):
    processed, interim, manifest = saved_summaries
    build_data.restore_checkpoints(manifest)
    restored = interim / '2025-02'
    assert json.loads((restored / 'complete.json').read_text()) == manifest['files'][0]
    for name in ['audit'] + list(build_data.TABLE_DIMS):
        pd.testing.assert_frame_equal(pd.read_csv(restored / f'{name}.csv'),
                                      pd.read_csv(processed / f'{name}.csv'))


@pytest.mark.parametrize('damage', ['missing_rows', 'inconsistent_trips'])
def test_restore_does_not_mark_an_incomplete_month_complete(saved_summaries, damage):
    processed, interim, manifest = saved_summaries
    path = processed / 'hourly.csv'
    table = pd.read_csv(path)
    if damage == 'missing_rows':
        table = table.iloc[:0]
    else:
        table.loc[table.company == 'Uber', 'trips'] = 999
    table.to_csv(path, index=False)
    with pytest.raises(ValueError):
        build_data.restore_checkpoints(manifest)
    assert not (interim / '2025-02' / 'complete.json').exists()

"""Keep paths, platform names, and analytical definitions in one place."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
INTERIM = ROOT / 'data' / 'interim'
PROCESSED = ROOT / 'data' / 'processed'
RESULTS = ROOT / 'data' / 'results'
SQL = ROOT / 'sql'
CHARTS = ROOT / 'charts'
DOCS = ROOT / 'docs'
TRIP_URL = 'https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{month}.parquet'
ZONE_URL = 'https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv'
COMPANIES = {'HV0003': 'Uber', 'HV0005': 'Lyft', 'HV0002': 'Juno', 'HV0004': 'Via'}
COLORS = {'Uber': '#2a78d6', 'Lyft': '#d6337a'}
AIRPORTS = (1, 132, 138)
FIRST_MONTH = '2019-02'
CBD_TRAIN_MONTH = '2025-02'
DISTANCE_BINS = ['0-1', '1-2', '2-3', '3-5', '5-10', '10-20', '20+']
SUM_COLUMNS = ['trips', 'fare', 'driver_pay', 'take', 'miles', 'minutes',
               'wait_minutes', 'wait_trips', 'tips', 'tolls', 'bcf', 'sales_tax',
               'congestion_surcharge', 'airport_fee', 'cbd_congestion_fee',
               'negative_take_trips', 'shared_trips', 'charged_trips']


def create_folders():
    """Create the small project output folders."""
    for folder in [RAW, INTERIM, PROCESSED, RESULTS, CHARTS, DOCS]:
        folder.mkdir(parents=True, exist_ok=True)

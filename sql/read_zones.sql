-- Read official borough labels before inferring the congestion zone.
CREATE OR REPLACE TEMP VIEW taxi_zones AS
SELECT LocationID AS location_id, Borough AS borough, Zone AS zone
FROM read_csv_auto('{path}');

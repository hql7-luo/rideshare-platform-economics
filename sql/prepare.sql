-- Define cleaning and dimensions once so every summary uses the same rows.
CREATE OR REPLACE TEMP VIEW prepared AS
SELECT *,
 CASE hvfhs_license_num WHEN 'HV0003' THEN 'Uber' WHEN 'HV0005' THEN 'Lyft'
 WHEN 'HV0002' THEN 'Juno' WHEN 'HV0004' THEN 'Via' ELSE 'Other' END AS company,
 fare > 0 AND driver_pay >= 0 AND trip_miles > 0 AND trip_miles <= 100
 AND trip_time BETWEEN 60 AND 14400
 AND pickup_datetime >= TIMESTAMP '{month}-01'
 AND pickup_datetime < TIMESTAMP '{month}-01' + INTERVAL 1 MONTH AS keep_row,
 date_diff('second', request_datetime, pickup_datetime) / 60.0 AS wait_value,
 CASE WHEN trip_miles <= 1 THEN '0-1' WHEN trip_miles <= 2 THEN '1-2'
 WHEN trip_miles <= 3 THEN '2-3' WHEN trip_miles <= 5 THEN '3-5'
 WHEN trip_miles <= 10 THEN '5-10' WHEN trip_miles <= 20 THEN '10-20'
 ELSE '20+' END AS distance_bin,
 (isodow(pickup_datetime) - 1)::INTEGER AS weekday,
 hour(pickup_datetime)::INTEGER AS hour,
 CASE WHEN pulocationid IN (1,132,138) OR dolocationid IN (1,132,138)
 THEN 1 ELSE 0 END AS is_airport,
 pulocationid AS location_id,
 CASE WHEN pulocationid IN ({zone_ids}) OR dolocationid IN ({zone_ids})
 THEN 'Zone-linked' ELSE 'Other' END AS zone_group
FROM raw;

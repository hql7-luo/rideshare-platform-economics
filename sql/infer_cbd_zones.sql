-- Freeze a Manhattan definition with enough February 2025 pickup observations.
WITH pickups AS (
 SELECT pulocationid AS location_id, count(*) AS trips,
  count(*) FILTER (WHERE cbd_congestion_fee > 0) AS charged_trips,
  count(*) FILTER (WHERE cbd_congestion_fee > 0) * 1.0 / count(*) AS charged_share
 FROM clean GROUP BY pulocationid
)
SELECT pickups.*, taxi_zones.borough, taxi_zones.zone,
 coalesce(borough = 'Manhattan' AND trips >= 1000 AND charged_share > 0.95, false) AS in_zone
FROM pickups LEFT JOIN taxi_zones USING (location_id)
ORDER BY location_id;

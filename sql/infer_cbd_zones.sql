-- Freeze a zone definition from the first complete post-policy month.
SELECT pulocationid AS location_id, count(*) AS trips,
 count(*) FILTER (WHERE cbd_congestion_fee > 0) AS charged_trips,
 count(*) FILTER (WHERE cbd_congestion_fee > 0) * 1.0 / count(*) AS charged_share,
 count(*) FILTER (WHERE cbd_congestion_fee > 0) * 1.0 / count(*) > 0.95 AS in_zone
FROM clean GROUP BY pulocationid ORDER BY pulocationid;

-- Add raw numerators once at each requested analytical grain.
SELECT company,
 CASE WHEN grouping(distance_bin)=0 THEN 'distance'
 WHEN grouping(weekday)=0 THEN 'hourly'
 WHEN grouping(is_airport)=0 THEN 'airport'
 WHEN grouping(location_id)=0 THEN 'pickup_zone'
 WHEN grouping(zone_group)=0 THEN 'congestion' ELSE 'monthly' END AS summary,
 distance_bin, weekday, hour, is_airport, location_id, zone_group,
 count(*) AS trips, sum(fare) AS fare, sum(driver_pay) AS driver_pay,
 sum(fare-driver_pay) AS take, sum(trip_miles) AS miles,
 sum(trip_time)/60.0 AS minutes,
 coalesce(sum(wait_value) FILTER(WHERE wait_value BETWEEN 0 AND 60),0) AS wait_minutes,
 count(*) FILTER(WHERE wait_value BETWEEN 0 AND 60) AS wait_trips,
 sum(tips) AS tips, sum(tolls) AS tolls, sum(bcf) AS bcf, sum(sales_tax) AS sales_tax,
 sum(congestion_surcharge) AS congestion_surcharge,
 sum(airport_fee) AS airport_fee, sum(cbd_congestion_fee) AS cbd_congestion_fee,
 count(*) FILTER(WHERE driver_pay>fare) AS negative_take_trips,
 count(*) FILTER(WHERE shared_request_flag='Y') AS shared_trips,
 count(*) FILTER(WHERE cbd_congestion_fee>0) AS charged_trips
FROM clean
GROUP BY GROUPING SETS ((company), (company,distance_bin), (company,weekday,hour),
 (company,is_airport),(company,location_id),(company,zone_group))
ORDER BY company, summary;

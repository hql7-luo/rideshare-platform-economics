-- Retain counts before and after cleaning for every observed platform.
SELECT company, count(*) AS raw_rows,
 count(*) FILTER (WHERE keep_row) AS kept_rows
FROM prepared GROUP BY company ORDER BY company;

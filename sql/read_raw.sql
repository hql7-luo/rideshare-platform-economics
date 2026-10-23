-- Normalize the available parquet columns before applying shared rules.
CREATE OR REPLACE TEMP VIEW raw AS
SELECT {columns} FROM read_parquet('{path}');

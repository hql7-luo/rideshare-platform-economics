-- Keep the requested platforms and valid trips; invalid waits remain eligible trips.
CREATE OR REPLACE TEMP VIEW clean AS
SELECT * FROM prepared WHERE keep_row AND company IN ('Uber','Lyft');

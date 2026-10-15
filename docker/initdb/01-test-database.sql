-- Runs once, when the data volume is first created (docker-entrypoint-initdb.d).
-- The API tests use this second database so they never touch the one the API writes to.
CREATE DATABASE anisotropy_test OWNER anisotropy;

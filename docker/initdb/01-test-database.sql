-- Runs once, when the Docker volume is first initialised.
-- The backend test suite migrates and wipes this database on every run;
-- never point it at a database whose name does not end in _test.
CREATE DATABASE ai_reminder_test;

# firebird

Firebird-vendor-specific tests (P8 vendor subtree, flat subject layout).

Contains the Firebird-only statement expressions with no cross-backend equivalent: COMMENT ON, CREATE/DROP DATABASE, EXCEPTION, EXECUTE STATEMENT / EXECUTE PROCEDURE / EXECUTE BLOCK, external functions, ROLE, ROUTINE, USER, and DOMAIN statements. All tests are pure expression construction — no database connection.

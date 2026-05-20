CREATE TABLE type_tests (
    id CHAR(36) CHARACTER SET OCTETS NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    optional_name VARCHAR(255),
    optional_age INT,
    last_login TIMESTAMP,
    type_tester VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending'
)

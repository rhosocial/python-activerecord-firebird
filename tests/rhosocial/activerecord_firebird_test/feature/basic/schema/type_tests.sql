CREATE TABLE type_tests (
    id CHAR(36) CHARACTER SET OCTETS NOT NULL PRIMARY KEY,
    string_field VARCHAR(255) DEFAULT 'test string',
    int_field INT DEFAULT 42,
    float_field DOUBLE PRECISION DEFAULT 3.14,
    decimal_field DECIMAL(18,2) DEFAULT 10.99,
    bool_field BOOLEAN DEFAULT TRUE,
    datetime_field TIMESTAMP,
    json_field BLOB SUB_TYPE TEXT,
    nullable_field VARCHAR(255)
)

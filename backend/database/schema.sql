DROP DATABASE IF EXISTS thermometer;
CREATE DATABASE thermometer;
USE thermometer;

CREATE TABLE temperature_samples(
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, -- PK: always present, so missing-interval rows (NULL boot_id/seq) can insert
    boot_id INT UNSIGNED,                        -- nullable: PROVISIONAL rows carry no boot_id
    sample_seq INT UNSIGNED,                     -- nullable: PROVISIONAL rows carry no sample_seq
    observed_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sensor1_c DECIMAL(5,2),
    sensor1_status ENUM('VALID','DISCONNECTED','NOT_RETRIEVED','MISSING') NOT NULL,
    sensor2_c DECIMAL(5,2),
    sensor2_status ENUM('VALID','DISCONNECTED','NOT_RETRIEVED','MISSING') NOT NULL,
    average_c DECIMAL(5,2),
    average_valid BOOLEAN NOT NULL,
    record_source ENUM('LIVE','HISTORY','PROVISIONAL') NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_sample (boot_id, sample_seq),    -- natural key still enforced for real rows; NULLs don't collide, so multiple PROVISIONAL rows are allowed
    INDEX entry_index (observed_at_utc)            -- SWE-DB-LLR-552;
);
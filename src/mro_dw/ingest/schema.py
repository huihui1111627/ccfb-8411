"""raw 层 DuckDB 建表 DDL。

raw 层保留源系统原貌（字符串/宽类型），规范化在 dbt staging 完成。
每张事务表带主键约束以支持 INSERT OR REPLACE 幂等加载。
"""

DDL_STATEMENTS: dict[str, str] = {
    "aircraft": """
        CREATE TABLE IF NOT EXISTS raw.aircraft (
            aircraft_msn     INTEGER NOT NULL PRIMARY KEY,
            tail_number      VARCHAR NOT NULL,
            aircraft_type    VARCHAR NOT NULL,
            in_service_date  DATE NOT NULL,
            loaded_at        TIMESTAMP NOT NULL
        )
    """,
    "parts": """
        CREATE TABLE IF NOT EXISTS raw.parts (
            part_number        VARCHAR NOT NULL PRIMARY KEY,
            part_name          VARCHAR NOT NULL,
            default_position   VARCHAR NOT NULL,
            is_life_limited    BOOLEAN NOT NULL,
            life_limit_hours   DOUBLE,
            life_limit_cycles  INTEGER,
            loaded_at          TIMESTAMP NOT NULL
        )
    """,
    "airworthiness_directives": """
        CREATE TABLE IF NOT EXISTS raw.airworthiness_directives (
            ad_id                VARCHAR NOT NULL PRIMARY KEY,
            ad_title             VARCHAR NOT NULL,
            aircraft_type        VARCHAR NOT NULL,
            applicable_msn_min   INTEGER NOT NULL,
            applicable_msn_max   INTEGER NOT NULL,
            due_hours            DOUBLE,
            due_date             DATE,
            issue_date           DATE NOT NULL,
            loaded_at            TIMESTAMP NOT NULL
        )
    """,
    "flight_logs": """
        CREATE TABLE IF NOT EXISTS raw.flight_logs (
            flight_log_id       VARCHAR NOT NULL PRIMARY KEY,
            aircraft_msn        INTEGER NOT NULL,
            flight_date         DATE NOT NULL,
            leg_seq             INTEGER NOT NULL,
            flight_hours        DOUBLE NOT NULL,
            flight_cycles       INTEGER NOT NULL,
            departure_airport   VARCHAR NOT NULL,
            arrival_airport     VARCHAR NOT NULL,
            record_date         DATE NOT NULL,
            loaded_at           TIMESTAMP NOT NULL
        )
    """,
    "component_events": """
        CREATE TABLE IF NOT EXISTS raw.component_events (
            event_id                 VARCHAR NOT NULL PRIMARY KEY,
            event_date               DATE NOT NULL,
            serial_number            VARCHAR NOT NULL,
            part_number              VARCHAR NOT NULL,
            aircraft_msn             INTEGER NOT NULL,
            event_type               VARCHAR NOT NULL,
            position_code            VARCHAR NOT NULL,
            related_work_order_id    VARCHAR NOT NULL,
            event_reason             VARCHAR NOT NULL,
            record_date              DATE NOT NULL,
            loaded_at                TIMESTAMP NOT NULL
        )
    """,
    "work_orders": """
        CREATE TABLE IF NOT EXISTS raw.work_orders (
            work_order_id    VARCHAR NOT NULL PRIMARY KEY,
            aircraft_msn     INTEGER NOT NULL,
            work_order_type  VARCHAR NOT NULL,
            description      VARCHAR NOT NULL,
            serial_number    VARCHAR,
            part_number      VARCHAR,
            ad_id            VARCHAR,
            is_routine       BOOLEAN NOT NULL,
            status           VARCHAR NOT NULL,
            opened_date      DATE NOT NULL,
            completed_date   DATE,
            record_date      DATE NOT NULL,
            loaded_at        TIMESTAMP NOT NULL
        )
    """,
    "ingest_state": """
        CREATE TABLE IF NOT EXISTS raw.ingest_state (
            source_name     VARCHAR NOT NULL PRIMARY KEY,
            last_record_date DATE NOT NULL,
            last_loaded_at  TIMESTAMP NOT NULL,
            rows_loaded     BIGINT NOT NULL
        )
    """,
}

# 每个源的主键列，用于幂等
PRIMARY_KEYS: dict[str, list[str]] = {
    "aircraft": ["aircraft_msn"],
    "parts": ["part_number"],
    "airworthiness_directives": ["ad_id"],
    "flight_logs": ["flight_log_id"],
    "component_events": ["event_id"],
    "work_orders": ["work_order_id"],
}

# 事务源 -> 用于增量水位的业务日期列
RECORD_DATE_COLUMN = {
    "flight_logs": "flight_date",
    "component_events": "event_date",
    "work_orders": "opened_date",
}

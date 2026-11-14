{{ config(materialized='incremental', incremental_strategy='merge', unique_key='flight_log_id') }}

select
    flight_log_id,
    aircraft_msn,
    flight_date,
    leg_seq,
    flight_hours,
    flight_cycles,
    departure_airport,
    arrival_airport,
    record_date
from {{ source('raw', 'flight_logs') }}
{% if is_incremental() %}
    where record_date >= (select coalesce(max(record_date), date '1900-01-01') from {{ this }})
{% endif %}

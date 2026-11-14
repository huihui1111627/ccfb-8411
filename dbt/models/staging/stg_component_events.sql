{{ config(materialized='incremental', incremental_strategy='merge', unique_key='event_id') }}

select
    event_id,
    event_date,
    serial_number,
    part_number,
    aircraft_msn,
    event_type,
    position_code,
    related_work_order_id,
    event_reason,
    record_date
from {{ source('raw', 'component_events') }}
{% if is_incremental() %}
    where record_date >= (select coalesce(max(record_date), date '1900-01-01') from {{ this }})
{% endif %}

{{ config(materialized='incremental', incremental_strategy='merge', unique_key='work_order_id') }}

select
    work_order_id,
    aircraft_msn,
    work_order_type,
    description,
    serial_number,
    part_number,
    ad_id,
    is_routine,
    status,
    opened_date,
    completed_date,
    record_date
from {{ source('raw', 'work_orders') }}
{% if is_incremental() %}
    where record_date >= (select coalesce(max(record_date), date '1900-01-01') from {{ this }})
{% endif %}

{{ config(materialized='incremental', incremental_strategy='merge', unique_key='aircraft_msn') }}

select
    aircraft_msn,
    tail_number,
    aircraft_type,
    in_service_date
from {{ source('raw', 'aircraft') }}
{% if is_incremental() %}
    where aircraft_msn not in (select aircraft_msn from {{ this }})
{% endif %}

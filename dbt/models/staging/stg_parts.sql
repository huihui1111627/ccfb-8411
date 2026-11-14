{{ config(materialized='incremental', incremental_strategy='merge', unique_key='part_number') }}

select
    part_number,
    part_name,
    default_position,
    is_life_limited,
    life_limit_hours,
    life_limit_cycles
from {{ source('raw', 'parts') }}
{% if is_incremental() %}
    where part_number not in (select part_number from {{ this }})
{% endif %}

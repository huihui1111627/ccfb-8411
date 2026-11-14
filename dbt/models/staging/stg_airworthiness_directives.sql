{{ config(materialized='incremental', incremental_strategy='merge', unique_key='ad_id') }}

select
    ad_id,
    ad_title,
    aircraft_type,
    applicable_msn_min,
    applicable_msn_max,
    due_hours,
    due_date,
    issue_date
from {{ source('raw', 'airworthiness_directives') }}
{% if is_incremental() %}
    where ad_id not in (select ad_id from {{ this }})
{% endif %}

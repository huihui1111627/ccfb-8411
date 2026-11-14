{{ config(materialized='table') }}

{# 适航指令符合性宽表（中间层适用性结果直接出 mart，附机号信息）。 #}
select
    ad_id,
    ad_title,
    aircraft_type,
    aircraft_msn,
    tail_number,
    applicable_msn_min,
    applicable_msn_max,
    due_hours,
    due_date,
    issue_date,
    aircraft_total_hours,
    is_completed,
    completed_date,
    compliance_status,
    case
        when is_completed then null
        when due_hours is not null
        then round(due_hours - aircraft_total_hours, 2)
        else null
    end as remaining_due_hours
from {{ ref('int_ad_applicability') }}

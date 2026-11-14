{{ config(materialized='table') }}

{# 适航指令适用性：机型一致且飞机 MSN 落在 [min, max] 序号范围内即适用。
   完成情况关联 AD 类型工卡；时限用机队累计飞行小时与到期日双重判断。 #}
with applicable as (
    select
        ad.ad_id,
        ad.ad_title,
        ad.aircraft_type,
        ad.applicable_msn_min,
        ad.applicable_msn_max,
        ad.due_hours,
        ad.due_date,
        ad.issue_date,
        ac.aircraft_msn,
        ac.tail_number
    from {{ ref('stg_airworthiness_directives') }} ad
    cross join {{ ref('stg_aircraft') }} ac
    where ac.aircraft_type = ad.aircraft_type
      and ac.aircraft_msn between ad.applicable_msn_min and ad.applicable_msn_max
),
ac_hours as (
    select
        aircraft_msn,
        round(sum(daily_flight_hours), 2) as total_flight_hours
    from {{ ref('int_flight_daily') }}
    group by aircraft_msn
),
ad_completion as (
    select
        ad_id,
        aircraft_msn,
        min(completed_date) as completed_date
    from {{ ref('stg_work_orders') }}
    where work_order_type = 'AD'
      and ad_id is not null
      and status = 'CLOSED'
    group by ad_id, aircraft_msn
)
select
    a.ad_id,
    a.ad_title,
    a.aircraft_type,
    a.aircraft_msn,
    a.tail_number,
    a.applicable_msn_min,
    a.applicable_msn_max,
    a.due_hours,
    a.due_date,
    a.issue_date,
    coalesce(h.total_flight_hours, 0) as aircraft_total_hours,
    c.completed_date is not null as is_completed,
    c.completed_date,
    case
        when c.completed_date is not null then 'COMPLIANT'
        when a.due_hours is not null and h.total_flight_hours > a.due_hours then 'OVERDUE_HOURS'
        when a.due_date is not null and current_date > a.due_date then 'OVERDUE_DATE'
        when a.due_hours is not null and h.total_flight_hours > 0.9 * a.due_hours then 'DUE_SOON'
        else 'OPEN'
    end as compliance_status
from applicable a
left join ac_hours h on h.aircraft_msn = a.aircraft_msn
left join ad_completion c
    on c.ad_id = a.ad_id and c.aircraft_msn = a.aircraft_msn

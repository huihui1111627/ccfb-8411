{{ config(materialized='table') }}

{# 机队可靠性指标（机/月粒度）。
   口径：
   - flights/cycles：当月航班段数与循环
   - flight_hours：当月飞行小时
   - non_routine_wo：非例行工卡（故障/AD/R&I），例行定检不计入
   - removal_events：当月部件拆下次数
   - technical_dispatch_rate = 1 - 非例行事件/航班段
   - removal_rate_per_100_flights：每百次飞行拆件率
   - routine_share：例行工卡占总工卡比例 #}
with bounds as (
    select min(flight_date) as min_d, max(flight_date) as max_d
    from {{ ref('int_flight_daily') }}
),
months as (
    select unnest(
        generate_series(date_trunc('month', min_d),
                        date_trunc('month', max_d),
                        interval 1 month)
    ) as month_start
    from bounds
),
calendar as (
    select
        ac.aircraft_msn,
        ac.tail_number,
        ac.aircraft_type,
        m.month_start::date as month_start,
        (m.month_start + interval 1 month)::date as month_end_excl
    from months m
    cross join {{ ref('stg_aircraft') }} ac
),
flights_m as (
    select
        aircraft_msn,
        date_trunc('month', flight_date)::date as month_start,
        sum(daily_flight_hours) as flight_hours,
        sum(daily_cycles) as flights,
        sum(leg_count) as leg_count
    from {{ ref('int_flight_daily') }}
    group by 1, 2
),
wo_m as (
    select
        aircraft_msn,
        date_trunc('month', opened_date)::date as month_start,
        sum(case when is_routine then 1 else 0 end) as routine_wo,
        sum(case when not is_routine then 1 else 0 end) as non_routine_wo,
        sum(case when work_order_type = 'R&I' then 1 else 0 end) as ri_wo,
        sum(case when work_order_type = 'AD' then 1 else 0 end) as ad_wo,
        count(*) as total_wo
    from {{ ref('stg_work_orders') }}
    group by 1, 2
),
rem_m as (
    select
        aircraft_msn,
        date_trunc('month', event_date)::date as month_start,
        count(*) as removal_events
    from {{ ref('stg_component_events') }}
    where event_type = 'REMOVE'
    group by 1, 2
)
select
    c.aircraft_msn,
    c.tail_number,
    c.aircraft_type,
    c.month_start,
    c.month_end_excl,
    coalesce(f.flight_hours, 0) as flight_hours,
    coalesce(f.flights, 0) as flights,
    coalesce(f.leg_count, 0) as leg_count,
    coalesce(w.total_wo, 0) as total_wo,
    coalesce(w.routine_wo, 0) as routine_wo,
    coalesce(w.non_routine_wo, 0) as non_routine_wo,
    coalesce(w.ri_wo, 0) as ri_wo,
    coalesce(w.ad_wo, 0) as ad_wo,
    coalesce(r.removal_events, 0) as removal_events,
    case when f.flights > 0
        then round(100.0 * (f.flights - coalesce(w.non_routine_wo, 0)) / f.flights, 2)
        else null end as technical_dispatch_rate_pct,
    case when f.flights > 0
        then round(100.0 * coalesce(r.removal_events, 0) / f.flights, 2)
        else null end as removal_rate_per_100_flights,
    case when w.total_wo > 0
        then round(100.0 * coalesce(w.routine_wo, 0) / w.total_wo, 2)
        else null end as routine_wo_share_pct,
    case when f.flight_hours > 0
        then round(f.flights / f.flight_hours, 3)
        else null end as cycles_per_hour
from calendar c
left join flights_m f using (aircraft_msn, month_start)
left join wo_m w using (aircraft_msn, month_start)
left join rem_m r using (aircraft_msn, month_start)

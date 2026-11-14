{{ config(materialized='table') }}

{# 按装机区间归集飞行日：同架飞机在 [install_date, interval_end_date]
   内的飞行小时与循环计入该区间（拆装当日按整日口径，区间口径全链路一致）。 #}
select
    p.installation_id,
    p.serial_number,
    p.part_number,
    p.aircraft_msn,
    p.position_code,
    p.install_date,
    p.interval_end_date,
    p.is_open,
    count(d.flight_date) as flight_days_in_interval,
    round(coalesce(sum(d.daily_flight_hours), 0), 2) as interval_flight_hours,
    coalesce(sum(d.daily_cycles), 0) as interval_cycles
from {{ ref('int_installation_periods') }} p
left join {{ ref('int_flight_daily') }} d
    on d.aircraft_msn = p.aircraft_msn
   and d.flight_date between p.install_date and p.interval_end_date
group by
    p.installation_id, p.serial_number, p.part_number, p.aircraft_msn,
    p.position_code, p.install_date, p.interval_end_date, p.is_open

{{ config(materialized='table') }}

{# 飞行日志按机/日聚合，下游所有小时、循环均以此为唯一粒度来源，
   保证"部件累计 = 逐段相加 = 日聚合之和"的勾稽关系。 #}
select
    aircraft_msn,
    flight_date,
    round(sum(flight_hours), 2) as daily_flight_hours,
    sum(flight_cycles) as daily_cycles,
    count(*) as leg_count
from {{ ref('stg_flight_logs') }}
group by aircraft_msn, flight_date

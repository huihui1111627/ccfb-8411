{{ config(materialized='table') }}

{# 时寿件剩余寿命与预警。
   阈值：剩余比例 <=10% 或已超 -> EXPIRED；<=20% -> WARNING；否则 HEALTHY。
   小时与循环两个维度取更严重者。 #}
with latest as (
    select
        serial_number,
        part_number,
        aircraft_msn,
        cumulative_hours_at_end as used_hours,
        cumulative_cycles_at_end as used_cycles
    from {{ ref('int_part_cumulative_usage') }}
    qualify row_number() over (
        partition by serial_number order by interval_end_date desc, installation_id desc
    ) = 1
),
enriched as (
    select
        l.serial_number,
        l.part_number,
        p.part_name,
        l.aircraft_msn,
        ac.tail_number,
        p.life_limit_hours,
        p.life_limit_cycles,
        l.used_hours,
        l.used_cycles,
        round(p.life_limit_hours - l.used_hours, 2) as remaining_hours,
        p.life_limit_cycles - l.used_cycles as remaining_cycles
    from latest l
    join {{ ref('stg_parts') }} p using (part_number)
    left join {{ ref('stg_aircraft') }} ac using (aircraft_msn)
    where p.is_life_limited
)
select
    *,
    case
        when remaining_hours <= 0 or remaining_cycles <= 0 then 'EXPIRED'
        when remaining_hours <= 0.2 * life_limit_hours
          or remaining_cycles <= 0.2 * life_limit_cycles then 'WARNING'
        else 'HEALTHY'
    end as life_status,
    round(100.0 * used_hours / life_limit_hours, 1) as hours_used_pct,
    round(100.0 * used_cycles / life_limit_cycles, 1) as cycles_used_pct
from enriched

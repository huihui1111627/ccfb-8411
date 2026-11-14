{{ config(materialized='table') }}

with cur as (
    select
        u.serial_number,
        u.part_number,
        p.part_name,
        p.is_life_limited,
        p.life_limit_hours,
        p.life_limit_cycles,
        count(u.installation_id) as installation_count,
        max(u.cumulative_hours_at_end) as total_flight_hours,
        max(u.cumulative_cycles_at_end) as total_cycles
    from {{ ref('int_part_cumulative_usage') }} u
    join {{ ref('stg_parts') }} p on p.part_number = u.part_number
    group by 1, 2, 3, 4, 5, 6
)
select * from cur

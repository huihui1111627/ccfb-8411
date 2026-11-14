{{ config(materialized='table') }}

{# 部件装机位置 SCD2：同一部件在同一架/同一位置的连续区间折叠为一条历史，
   跨机或换位置则开新行；is_current + end_date=9999-12-31 标识当前行。 #}
with periods as (
    select
        serial_number,
        part_number,
        aircraft_msn,
        position_code,
        install_date,
        interval_end_date,
        is_open
    from {{ ref('int_installation_periods') }}
),
lagged as (
    select
        *,
        lag(aircraft_msn) over (partition by serial_number order by install_date) as prev_msn,
        lag(position_code) over (partition by serial_number order by install_date) as prev_pos
    from periods
),
grouped as (
    select
        *,
        sum(
            case
                when prev_msn is null
                  or prev_msn <> aircraft_msn
                  or prev_pos <> position_code
                then 1 else 0
            end
        ) over (
            partition by serial_number
            order by install_date
            rows between unbounded preceding and current row
        ) as scd_group
    from lagged
),
scd as (
    select
        serial_number,
        part_number,
        aircraft_msn,
        position_code,
        min(install_date) as valid_from,
        max(interval_end_date) as valid_to_raw,
        bool_or(is_open) as has_open_interval
    from grouped
    group by serial_number, part_number, aircraft_msn, position_code, scd_group
)
select
    serial_number,
    part_number,
    aircraft_msn,
    position_code,
    valid_from,
    case when has_open_interval then date '9999-12-31' else valid_to_raw end as valid_to,
    has_open_interval as is_current
from scd

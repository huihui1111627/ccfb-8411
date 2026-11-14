{{ config(materialized='table') }}

{# 部件级累计：窗口函数按装机顺序累加区间小时/循环，
   给出每个区间起止时的部件累计值（时寿件剩余寿命以此为准）。 #}
select
    installation_id,
    serial_number,
    part_number,
    aircraft_msn,
    install_date,
    interval_end_date,
    interval_flight_hours,
    interval_cycles,
    round(
        coalesce(sum(interval_flight_hours) over (
            partition by serial_number
            order by install_date, installation_id
            rows between unbounded preceding and 1 preceding
        ), 0),
        2
    ) as cumulative_hours_at_install,
    round(
        sum(interval_flight_hours) over (
            partition by serial_number
            order by install_date, installation_id
            rows between unbounded preceding and current row
        ),
        2
    ) as cumulative_hours_at_end,
    coalesce(sum(interval_cycles) over (
        partition by serial_number
        order by install_date, installation_id
        rows between unbounded preceding and 1 preceding
    ), 0) as cumulative_cycles_at_install,
    sum(interval_cycles) over (
        partition by serial_number
        order by install_date, installation_id
        rows between unbounded preceding and current row
    ) as cumulative_cycles_at_end
from {{ ref('int_installation_usage') }}

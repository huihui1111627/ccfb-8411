{{ config(materialized='table') }}

{# 部件履历：每个装机区间一行，附机型、机号、区间使用量与累计量，
   网页"部件履历"页直接查询此表。 #}
select
    p.installation_id,
    p.serial_number,
    p.part_number,
    pt.part_name,
    p.aircraft_msn,
    ac.tail_number,
    ac.aircraft_type,
    p.position_code,
    p.install_seq,
    p.install_date,
    p.removal_date,
    p.is_open,
    p.install_work_order_id,
    p.removal_work_order_id,
    p.install_reason,
    p.removal_reason,
    u.flight_days_in_interval,
    u.interval_flight_hours,
    u.interval_cycles,
    c.cumulative_hours_at_install,
    c.cumulative_hours_at_end,
    c.cumulative_cycles_at_install,
    c.cumulative_cycles_at_end
from {{ ref('int_installation_periods') }} p
join {{ ref('int_installation_usage') }} u using (installation_id)
join {{ ref('int_part_cumulative_usage') }} c using (installation_id)
join {{ ref('stg_parts') }} pt on pt.part_number = p.part_number
join {{ ref('stg_aircraft') }} ac on ac.aircraft_msn = p.aircraft_msn

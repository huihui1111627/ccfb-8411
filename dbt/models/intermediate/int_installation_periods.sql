{{ config(materialized='table') }}

{# 把拆装事件流折叠为装机区间：第 N 次 INSTALL 与第 N 次 REMOVE 配对。
   交替合法性由 singular 测试 assert_install_remove_alternation 保证。
   未闭合区间（仍装机）的截止日取飞行日志最大日期，保证小时累计可复算。 #}
with events as (
    select
        *,
        row_number() over (
            partition by serial_number
            order by event_date,
                     case event_type when 'INSTALL' then 1 when 'REMOVE' then 2 end,
                     event_id
        ) as event_rn
    from {{ ref('stg_component_events') }}
),
installs as (
    select
        serial_number,
        part_number,
        aircraft_msn,
        position_code,
        event_date as install_date,
        related_work_order_id as install_work_order_id,
        event_reason as install_reason,
        row_number() over (
            partition by serial_number order by event_date, event_rn
        ) as install_seq
    from events
    where event_type = 'INSTALL'
),
removes as (
    select
        serial_number,
        event_date as removal_date,
        related_work_order_id as removal_work_order_id,
        event_reason as removal_reason,
        row_number() over (
            partition by serial_number order by event_date, event_rn
        ) as remove_seq
    from events
    where event_type = 'REMOVE'
),
bounds as (
    select max(flight_date) as max_flight_date
    from {{ ref('stg_flight_logs') }}
)
select
    i.serial_number || '-' || printf('%02d', i.install_seq) as installation_id,
    i.serial_number,
    i.part_number,
    i.aircraft_msn,
    i.position_code,
    i.install_seq,
    i.install_date,
    r.removal_date,
    case
        when r.removal_date is null then b.max_flight_date
        else r.removal_date
    end as interval_end_date,
    (r.removal_date is null) as is_open,
    i.install_work_order_id,
    r.removal_work_order_id,
    i.install_reason,
    r.removal_reason
from installs i
left join removes r
    on r.serial_number = i.serial_number
   and r.remove_seq = i.install_seq
cross join bounds b

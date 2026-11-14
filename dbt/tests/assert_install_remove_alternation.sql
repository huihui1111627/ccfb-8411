{# 拆装事件必须以 INSTALL 开始且 INSTALL/REMOVE 严格交替，
   否则区间折叠逻辑不成立。 #}
with ordered as (
    select
        serial_number,
        event_type,
        row_number() over (
            partition by serial_number
            order by event_date,
                     case event_type when 'INSTALL' then 1 when 'REMOVE' then 2 end,
                     event_id
        ) as rn,
        lag(event_type) over (
            partition by serial_number
            order by event_date,
                     case event_type when 'INSTALL' then 1 when 'REMOVE' then 2 end,
                     event_id
        ) as prev_type
    from {{ ref('stg_component_events') }}
)
select *
from ordered
where (rn = 1 and event_type <> 'INSTALL')
   or (rn > 1 and prev_type = event_type)

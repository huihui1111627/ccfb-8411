{# SCD2 约束：每个部件至多一条 is_current 行，且所有行 valid_from < valid_to。 #}
select serial_number, 'multiple_current' as violation, count(*) as n
from {{ ref('fct_component_position_history') }}
where is_current
group by serial_number
having count(*) > 1

union all

select serial_number, 'invalid_dates' as violation, 1 as n
from {{ ref('fct_component_position_history') }}
where valid_from >= valid_to

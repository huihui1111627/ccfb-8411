{# 任一部件在任一时刻只能有一个在役装机区间：区间不得重叠。 #}
select
    a.installation_id as interval_a,
    b.installation_id as interval_b,
    a.serial_number
from {{ ref('int_installation_periods') }} a
join {{ ref('int_installation_periods') }} b
    on a.serial_number = b.serial_number
   and a.installation_id < b.installation_id
   and b.install_date <= a.interval_end_date
   and a.install_date <= b.interval_end_date

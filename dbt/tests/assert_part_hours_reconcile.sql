{# 核心勾稽：部件累计小时/循环必须等于"逐区间相加"，
   而逐区间数字必须能由机/日飞行聚合独立重算出来。
   任一部件对不上即返回行 -> 测试失败（error 级，阻断下游）。 #}
with recon as (
    select
        p.serial_number,
        round(coalesce(sum(d.daily_flight_hours), 0), 2) as recon_hours,
        coalesce(sum(d.daily_cycles), 0) as recon_cycles
    from {{ ref('int_installation_periods') }} p
    left join {{ ref('int_flight_daily') }} d
        on d.aircraft_msn = p.aircraft_msn
       and d.flight_date between p.install_date and p.interval_end_date
    group by p.serial_number
),
cum as (
    select
        serial_number,
        max(cumulative_hours_at_end) as cum_hours,
        max(cumulative_cycles_at_end) as cum_cycles
    from {{ ref('int_part_cumulative_usage') }}
    group by serial_number
)
select
    recon.serial_number,
    recon.recon_hours,
    cum.cum_hours,
    recon.recon_cycles,
    cum.cum_cycles
from recon
join cum using (serial_number)
where abs(recon.recon_hours - cum.cum_hours) > 0.01
   or recon.recon_cycles <> cum.cum_cycles

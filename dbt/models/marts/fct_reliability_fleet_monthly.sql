{{ config(materialized='table') }}

{# 机队月汇总：在机/月指标上做加权汇总，比率类指标用总量重新计算，不做简单平均。 #}
select
    month_start,
    count(distinct aircraft_msn) as active_aircraft,
    sum(flight_hours) as fleet_flight_hours,
    sum(flights) as fleet_flights,
    sum(total_wo) as total_wo,
    sum(routine_wo) as routine_wo,
    sum(non_routine_wo) as non_routine_wo,
    sum(ri_wo) as ri_wo,
    sum(ad_wo) as ad_wo,
    sum(removal_events) as removal_events,
    case when sum(flights) > 0
        then round(100.0 * (sum(flights) - sum(non_routine_wo)) / sum(flights), 2)
        else null end as fleet_dispatch_rate_pct,
    case when sum(flights) > 0
        then round(100.0 * sum(removal_events) / sum(flights), 2)
        else null end as fleet_removal_rate_per_100_flights,
    case when sum(total_wo) > 0
        then round(100.0 * sum(routine_wo) / sum(total_wo), 2)
        else null end as fleet_routine_wo_share_pct
from {{ ref('fct_reliability_monthly') }}
group by month_start
order by month_start

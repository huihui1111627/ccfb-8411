"""数据仓库核心业务规则测试。"""
from __future__ import annotations

import duckdb
import pytest

from mro_dw.paths import duckdb_path


@pytest.fixture(scope="module")
def con(dw):
    # 不用 read_only：dbt 在同进程内持有读写连接，DuckDB 禁止异配置并发打开
    c = duckdb.connect(str(duckdb_path()))
    yield c
    c.close()


def test_same_aircraft_remove_and_reinstall(con):
    """SN-5001 在同一架 1001 上有 3 次完整拆下-装回，共 4 个装机区间。"""
    rows = con.execute("""
        select installation_id, aircraft_msn, install_date, removal_date, is_open
        from marts.fct_component_history
        where serial_number = 'SN-5001'
        order by install_date
    """).fetchall()
    assert len(rows) == 4
    assert {r[1] for r in rows} == {1001}
    closed = [r for r in rows if not r[4]]
    assert len(closed) == 3  # 前三个区间均已闭合


def test_cross_aircraft_transfer(con):
    """SN-5002：1002 -> 1003 -> 1002 串件路径。"""
    rows = con.execute("""
        select aircraft_msn from marts.fct_component_history
        where serial_number = 'SN-5002' order by install_date
    """).fetchall()
    assert [r[0] for r in rows] == [1002, 1003, 1002]


def test_part_cumulative_equals_sum_of_intervals(con):
    """部件累计小时/循环必须与逐段相加完全一致（所有部件）。"""
    rows = con.execute("""
        select
            serial_number,
            round(sum(interval_flight_hours), 2) as sum_hours,
            sum(interval_cycles) as sum_cycles,
            max(cumulative_hours_at_end) as cum_hours,
            max(cumulative_cycles_at_end) as cum_cycles
        from marts.fct_component_history
        group by serial_number
    """).fetchall()
    assert rows
    for sn, sh, sc, ch, cc in rows:
        assert abs(sh - ch) <= 0.01, f"{sn} 小时对不上: {sh} vs {ch}"
        assert sc == cc, f"{sn} 循环对不上: {sc} vs {cc}"


def test_interval_hours_recon_from_daily_flights(con):
    """区间小时必须能从机/日飞行聚合独立重算（勾稽链路第二条腿）。"""
    rows = con.execute("""
        with recon as (
            select p.installation_id,
                   round(coalesce(sum(d.daily_flight_hours), 0), 2) as recon_h
            from intermediate.int_installation_periods p
            left join intermediate.int_flight_daily d
              on d.aircraft_msn = p.aircraft_msn
             and d.flight_date between p.install_date and p.interval_end_date
            group by p.installation_id
        )
        select h.installation_id, h.interval_flight_hours, r.recon_h
        from intermediate.int_installation_usage h
        join recon r using (installation_id)
        where abs(h.interval_flight_hours - r.recon_h) > 0.01
    """).fetchall()
    assert rows == []


def test_scd2_single_current_row(con):
    bad = con.execute("""
        select serial_number from marts.fct_component_position_history
        where is_current group by serial_number having count(*) > 1
    """).fetchall()
    assert bad == []


def test_life_limited_warning_and_expired(con):
    """时寿件：SN-5009 到期，SN-5005 预警，SN-5008 健康。"""
    rows = dict(con.execute("""
        select serial_number, life_status from marts.fct_life_limited_parts
    """).fetchall())
    assert rows["SN-5009"] == "EXPIRED"
    assert rows["SN-5005"] == "WARNING"
    assert rows["SN-5008"] == "HEALTHY"


def test_ad_applicability_by_type_and_msn_range(con):
    # A350 指令无机队适用记录
    n = con.execute("""
        select count(*) from marts.fct_ad_status
        where ad_id = 'AD-2025-01-A350'
    """).fetchone()[0]
    assert n == 0
    # B737 指令恰好适用 3 架
    n = con.execute("""
        select count(*) from marts.fct_ad_status
        where ad_id = 'AD-2024-01-B737'
    """).fetchone()[0]
    assert n == 3
    # 1001/1002 已完成该 AD，1003 未完成
    done = dict(con.execute("""
        select aircraft_msn, is_completed from marts.fct_ad_status
        where ad_id = 'AD-2024-01-B737'
    """).fetchall())
    assert done[1001] and done[1002]
    assert not done[1003]


def test_reliability_metrics_present(con):
    rows = con.execute("select count(*) from marts.fct_reliability_fleet_monthly").fetchone()[0]
    assert rows >= 12  # 2024-01 ~ 2025-06
    bad = con.execute("""
        select * from marts.fct_reliability_fleet_monthly
        where fleet_dispatch_rate_pct < 0 or fleet_dispatch_rate_pct > 100
    """).fetchall()
    assert bad == []

"""飞行日志与最终落地数据的总装生成。"""
from __future__ import annotations

import math
from datetime import date, timedelta

from .master import AIRCRAFT, DATA_END, DATA_START, PARTS, RNG
from .scenarios import Event, WorkOrder, _d, airworthiness_directives, static_events, static_work_orders


def _aircraft_days(msn: int, in_service: date) -> list[date]:
    start = max(DATA_START, in_service)
    out, d = [], start
    while d <= DATA_END:
        out.append(d)
        d += timedelta(days=1)
    return out


# 每架飞机日均利用率（小时/飞行），用固定参数保证数据可解释
_FLEET_PROFILE = {
    1001: dict(flights=(3, 4), block=(2.6, 3.4)),
    1002: dict(flights=(3, 4), block=(2.4, 3.2)),
    1003: dict(flights=(2, 4), block=(2.2, 3.0)),
    2001: dict(flights=(3, 5), block=(3.0, 4.0)),
    2002: dict(flights=(2, 4), block=(2.8, 3.6)),
}


def generate_flights() -> list[dict]:
    rows: list[dict] = []
    seq = 1
    for ac in AIRCRAFT:
        # 每架飞机独立且确定的随机序列
        import random as _r
        local = _r.Random(7000 + ac.aircraft_msn)
        prof = _FLEET_PROFILE[ac.aircraft_msn]
        for d in _aircraft_days(ac.aircraft_msn, ac.in_service_date):
            # 约 3% 的天数为停场日（无飞行）
            if local.random() < 0.03:
                continue
            n = local.randint(*prof["flights"])
            for leg in range(n):
                block = round(local.uniform(*prof["block"]), 2)
                rows.append({
                    "flight_log_id": f"FL-{seq:06d}",
                    "aircraft_msn": ac.aircraft_msn,
                    "flight_date": d,
                    "leg_seq": leg + 1,
                    "flight_hours": block,
                    "flight_cycles": 1,
                    "departure_airport": local.choice(["PEK", "PVG", "CAN", "CTU", "SZX", "KMG"]),
                    "arrival_airport": local.choice(["PEK", "PVG", "CAN", "CTU", "SZX", "KMG"]),
                })
                seq += 1
    return rows


def _cumulative_hours(flights: list[dict], msn: int, up_to: date) -> float:
    return round(sum(r["flight_hours"] for r in flights
                     if r["aircraft_msn"] == msn and r["flight_date"] <= up_to), 2)


def _dynamic_llp_events(flights: list[dict]):
    """SN-5005（1500h 上限）装机后到数据末端的使用量应落在预警区。

    部件使用量 = 飞机全期小时 − 装机日累计小时（装得越晚用得越少）。
    目标：已用 1250~1400h，即剩余 100~250h（处于 20% 预警线内且未到期）。
    """
    total = _cumulative_hours(flights, 1002, DATA_END)
    chosen: date | None = None
    d = date(2024, 6, 1)
    while d <= date(2025, 3, 1):
        part_used = round(total - _cumulative_hours(flights, 1002, d), 2)
        if 1250.0 <= part_used <= 1400.0:
            chosen = d
            break
        d += timedelta(days=1)
    if chosen is None:  # 兜底
        chosen = date(2025, 1, 15)
    wo = f"WO-{chosen:%Y}-5005"
    events = [Event(chosen, "SN-5005", "PN-DSK-004", 1002, "INSTALL",
                    "ENG/DISK-HPC", wo, "时寿盘装机")]
    return events, [WorkOrder(wo, 1002, "R&I", "高压压气机盘装机",
                              chosen, chosen, "SN-5005", "PN-DSK-004")]


def _routine_work_orders() -> list[WorkOrder]:
    """每月每架一张例行定检工卡，体现 routine/non-routine 指标。"""
    out: list[WorkOrder] = []
    n = 1
    for ac in AIRCRAFT:
        d = max(DATA_START.replace(day=1), ac.in_service_date.replace(day=1))
        while d <= DATA_END:
            out.append(WorkOrder(
                work_order_id=f"WO-RT-{n:04d}",
                aircraft_msn=ac.aircraft_msn,
                work_order_type="INSPECT",
                description=f"{ac.tail_number} {d:%Y-%m} 月度定检",
                opened_date=d,
                completed_date=d + timedelta(days=1),
                is_routine=True,
            ))
            n += 1
            # 下一个月
            d = (d.replace(day=28) + timedelta(days=10)).replace(day=1)
    return out


def build_all() -> dict[str, list[dict]]:
    flights = generate_flights()
    llp_events, llp_wos = _dynamic_llp_events(flights)
    events = static_events() + llp_events
    wos = static_work_orders() + llp_wos + _routine_work_orders()

    event_rows = [
        {
            "event_id": f"EV-{i:05d}",
            "event_date": ev.event_date,
            "serial_number": ev.serial_number,
            "part_number": ev.part_number,
            "aircraft_msn": ev.aircraft_msn,
            "event_type": ev.event_type,
            "position_code": ev.position_code,
            "related_work_order_id": ev.related_work_order_id,
            "event_reason": ev.event_reason,
        }
        for i, ev in enumerate(events, start=1)
    ]
    wo_rows = [
        {
            "work_order_id": w.work_order_id,
            "aircraft_msn": w.aircraft_msn,
            "work_order_type": w.work_order_type,
            "description": w.description,
            "serial_number": w.serial_number,
            "part_number": w.part_number,
            "ad_id": w.ad_id,
            "is_routine": w.is_routine,
            "status": w.status,
            "opened_date": w.opened_date,
            "completed_date": w.completed_date,
        }
        for w in wos
    ]
    aircraft_rows = [vars(a) for a in AIRCRAFT]
    part_rows = [vars(p) for p in PARTS]
    ad_rows = airworthiness_directives()
    return {
        "aircraft": aircraft_rows,
        "parts": part_rows,
        "airworthiness_directives": ad_rows,
        "component_events": event_rows,
        "work_orders": wo_rows,
        "flight_logs": flights,
    }

"""拆装事件场景编排（手工设计，确定性）。

每个 REMOVE/INSTALL 都关联工卡；同一轮拆装共用一张 R&I 工卡。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .master import DATA_END, DATA_START


@dataclass
class Event:
    event_date: date
    serial_number: str
    part_number: str
    aircraft_msn: int
    event_type: str          # INSTALL / REMOVE
    position_code: str
    related_work_order_id: str
    event_reason: str


@dataclass
class WorkOrder:
    work_order_id: str
    aircraft_msn: int
    work_order_type: str     # R&I / AD / INSPECT
    description: str
    opened_date: date
    completed_date: date
    serial_number: str | None = None
    part_number: str | None = None
    ad_id: str | None = None
    is_routine: bool = False
    status: str = "CLOSED"


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


# ---------------------------------------------------------------- 静态场景
def static_events() -> list[Event]:
    P = {
        "idg": "PN-IDG-001",
        "hyd": "PN-HYD-002",
        "apu": "PN-APU-003",
        "dsk4": "PN-DSK-004",
        "dsk5": "PN-DSK-005",
    }
    e: list[Event] = []

    # SN-5001：同一架 1001 上三次拆下、三次装回
    rows = [
        ("2024-01-01", "INSTALL", "WO-2024-0101", "初始装机"),
        ("2024-06-10", "REMOVE", "WO-2024-0610", "发电机滑油渗漏，故障拆下"),
        ("2024-06-25", "INSTALL", "WO-2024-0610", "修理合格后装回原机"),
        ("2024-11-18", "REMOVE", "WO-2024-1118", "定检发现轴承磨损，拆下"),
        ("2024-12-02", "INSTALL", "WO-2024-1118", "更换轴承后装回"),
        ("2025-03-20", "REMOVE", "WO-2025-0320", "线路故障排查拆下"),
        ("2025-04-05", "INSTALL", "WO-2025-0320", "排查完毕装回"),
    ]
    for iso, typ, wo, reason in rows:
        e.append(Event(_d(iso), "SN-5001", P["idg"], 1001, typ,
                       "ELECTRICAL/IDG-L", wo, reason))

    # SN-5002：1002 拆下 -> 装到 1003 -> 拆回 1002
    rows = [
        ("2024-01-01", 1002, "INSTALL", "WO-2024-0102", "初始装机"),
        ("2024-09-05", 1002, "REMOVE", "WO-2024-0905", "1002 发电机故障拆下"),
        ("2024-09-20", 1003, "INSTALL", "WO-2024-0920", "串件至 1003 临时使用"),
        ("2025-02-10", 1003, "REMOVE", "WO-2025-0210", "1003 航后拆下待串回"),
        ("2025-02-25", 1002, "INSTALL", "WO-2025-0225", "装回原机 1002"),
    ]
    for iso, msn, typ, wo, reason in rows:
        e.append(Event(_d(iso), "SN-5002", P["idg"], msn, typ,
                       "ELECTRICAL/IDG-L", wo, reason))

    # SN-5003：2001 全程在位，无拆装
    e.append(Event(_d("2024-01-01"), "SN-5003", P["idg"], 2001,
                   "INSTALL", "ELECTRICAL/IDG-L", "WO-2024-0103", "初始装机"))

    # SN-5006：A320 2002 同架拆下又装回
    rows = [
        ("2024-03-01", "INSTALL", "WO-2024-0301", "初始装机"),
        ("2024-08-12", "REMOVE", "WO-2024-0812", "液压压力波动，拆下检查"),
        ("2024-08-20", "INSTALL", "WO-2024-0812", "检查合格装回"),
    ]
    for iso, typ, wo, reason in rows:
        e.append(Event(_d(iso), "SN-5006", P["hyd"], 2002, typ,
                       "HYD/PUMP-A", wo, reason))

    # SN-5007：1001 拆下 -> 跨机型装到 2001
    rows = [
        ("2024-01-01", 1001, "INSTALL", "WO-2024-0104", "初始装机"),
        ("2025-01-15", 1001, "REMOVE", "WO-2025-0115", "APU 火警故障，拆下"),
        ("2025-02-01", 2001, "INSTALL", "WO-2025-0201", "跨机型改装后装至 2001"),
    ]
    for iso, msn, typ, wo, reason in rows:
        e.append(Event(_d(iso), "SN-5007", P["apu"], msn, typ,
                       "APU/MAIN", wo, reason))

    # SN-5009：时寿件（800h/600cy 上限），2024-01-01 装上 1001 后从未拆下 -> 到期
    e.append(Event(_d("2024-01-01"), "SN-5009", P["dsk5"], 1001,
                   "INSTALL", "ENG/DISK-LPT", "WO-2024-0105", "初始装机"))

    # SN-5008：时寿件，2025-06-01 才装上 2001，累计很低 -> 健康
    e.append(Event(_d("2025-06-01"), "SN-5008", P["dsk4"], 2001,
                   "INSTALL", "ENG/DISK-HPC", "WO-2025-0601", "新件装机"))
    return e


def static_work_orders() -> list[WorkOrder]:
    wos: list[WorkOrder] = []
    # 拆装工卡（与事件对应）
    ri = [
        ("WO-2024-0101", 1001, "2024-01-01", "2024-01-01", "SN-5001", "PN-IDG-001", "IDG 初始装机"),
        ("WO-2024-0610", 1001, "2024-06-10", "2024-06-25", "SN-5001", "PN-IDG-001", "IDG 拆下修理并装回"),
        ("WO-2024-1118", 1001, "2024-11-18", "2024-12-02", "SN-5001", "PN-IDG-001", "IDG 轴承更换"),
        ("WO-2025-0320", 1001, "2025-03-20", "2025-04-05", "SN-5001", "PN-IDG-001", "IDG 线路排查"),
        ("WO-2024-0102", 1002, "2024-01-01", "2024-01-01", "SN-5002", "PN-IDG-001", "IDG 初始装机"),
        ("WO-2024-0905", 1002, "2024-09-05", "2024-09-05", "SN-5002", "PN-IDG-001", "IDG 故障拆下"),
        ("WO-2024-0920", 1003, "2024-09-20", "2024-09-20", "SN-5002", "PN-IDG-001", "IDG 串件装机"),
        ("WO-2025-0210", 1003, "2025-02-10", "2025-02-10", "SN-5002", "PN-IDG-001", "IDG 拆下"),
        ("WO-2025-0225", 1002, "2025-02-25", "2025-02-25", "SN-5002", "PN-IDG-001", "IDG 装回原机"),
        ("WO-2024-0103", 2001, "2024-01-01", "2024-01-01", "SN-5003", "PN-IDG-001", "IDG 初始装机"),
        ("WO-2024-0301", 2002, "2024-03-01", "2024-03-01", "SN-5006", "PN-HYD-002", "液压泵初始装机"),
        ("WO-2024-0812", 2002, "2024-08-12", "2024-08-20", "SN-5006", "PN-HYD-002", "液压泵拆下检查装回"),
        ("WO-2024-0104", 1001, "2024-01-01", "2024-01-01", "SN-5007", "PN-APU-003", "APU 初始装机"),
        ("WO-2025-0115", 1001, "2025-01-15", "2025-01-15", "SN-5007", "PN-APU-003", "APU 故障拆下"),
        ("WO-2025-0201", 2001, "2025-02-01", "2025-02-01", "SN-5007", "PN-APU-003", "APU 跨机型装机"),
        ("WO-2024-0105", 1001, "2024-01-01", "2024-01-01", "SN-5009", "PN-DSK-005", "压气机盘初始装机"),
        ("WO-2025-0601", 2001, "2025-06-01", "2025-06-01", "SN-5008", "PN-DSK-004", "涡轮盘新件装机"),
    ]
    for wid, msn, od, cd, sn, pn, desc in ri:
        wos.append(WorkOrder(wid, msn, "R&I", desc, _d(od), _d(cd), sn, pn))

    # 适航指令工卡
    ads = [
        ("WO-AD-2024-001", 1001, "2024-04-10", "2024-04-15", "AD-2024-01-B737", "导线束检查"),
        ("WO-AD-2024-002", 1002, "2024-04-10", "2024-04-15", "AD-2024-01-B737", "导线束检查"),
        ("WO-AD-2025-001", 2001, "2025-03-05", "2025-03-10", "AD-2025-02-A320", "ECAM 软件升级"),
    ]
    for wid, msn, od, cd, ad_id, desc in ads:
        wos.append(WorkOrder(wid, msn, "AD", f"{ad_id} {desc}",
                             _d(od), _d(cd), ad_id=ad_id))
    return wos


# ---------------------------------------------------------------- 适航指令主数据
def airworthiness_directives() -> list[dict]:
    return [
        {
            "ad_id": "AD-2024-01-B737",
            "ad_title": "737 导线束磨损检查",
            "aircraft_type": "B737-800",
            "applicable_msn_min": 1001,
            "applicable_msn_max": 1003,
            "due_hours": 1200.0,
            "due_date": None,
            "issue_date": date(2024, 2, 1),
        },
        {
            "ad_id": "AD-2024-03-B737",
            "ad_title": "737 升降舵铰链检查",
            "aircraft_type": "B737-800",
            "applicable_msn_min": 1001,
            "applicable_msn_max": 1002,
            "due_hours": None,
            "due_date": date(2025, 12, 31),
            "issue_date": date(2024, 7, 1),
        },
        {
            "ad_id": "AD-2025-02-A320",
            "ad_title": "A320 ECAM 软件升级",
            "aircraft_type": "A320-200",
            "applicable_msn_min": 2001,
            "applicable_msn_max": 2002,
            "due_hours": 2000.0,
            "due_date": None,
            "issue_date": date(2025, 1, 10),
        },
        {
            "ad_id": "AD-2025-01-A350",
            "ad_title": "A350 复合材料检修（本无机队适用）",
            "aircraft_type": "A350-900",
            "applicable_msn_min": 3001,
            "applicable_msn_max": 3099,
            "due_hours": 3000.0,
            "due_date": None,
            "issue_date": date(2025, 3, 1),
        },
    ]

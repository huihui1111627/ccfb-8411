"""测试数据生成（确定性，可重复运行）。

场景覆盖（详见 README）：
- SN-5001：同一架飞机多次拆下又装回（3 次拆装循环）
- SN-5002：拆下后装到另一架，再拆回
- SN-5005 / SN-5009：时寿件，分别触发预警和到期
- SN-5004：从未装机的备件
- SN-5003：全程在位、无拆装记录
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

RNG = random.Random(20260630)

DATA_START = date(2024, 1, 1)
DATA_END = date(2025, 6, 30)


@dataclass(frozen=True)
class Aircraft:
    aircraft_msn: int          # 机龄序号（适航指令按此序号范围判断）
    tail_number: str
    aircraft_type: str
    in_service_date: date


@dataclass(frozen=True)
class Part:
    part_number: str
    part_name: str
    default_position: str
    is_life_limited: bool
    life_limit_hours: float | None
    life_limit_cycles: int | None


AIRCRAFT: list[Aircraft] = [
    Aircraft(1001, "B-1001", "B737-800", date(2023, 6, 1)),
    Aircraft(1002, "B-1002", "B737-800", date(2023, 6, 1)),
    Aircraft(1003, "B-1003", "B737-800", date(2024, 1, 15)),
    Aircraft(2001, "B-2001", "A320-200", date(2023, 9, 1)),
    Aircraft(2002, "B-2002", "A320-200", date(2024, 3, 1)),
]

PARTS: list[Part] = [
    Part("PN-IDG-001", "整体驱动发电机 IDG", "ELECTRICAL/IDG-L", False, None, None),
    Part("PN-HYD-002", "液压泵", "HYD/PUMP-A", False, None, None),
    Part("PN-APU-003", "辅助动力装置 APU", "APU/MAIN", False, None, None),
    Part("PN-DSK-004", "高压压气机盘(时寿件)", "ENG/DISK-HPC", True, 1500.0, 1000),
    Part("PN-DSK-005", "低压涡轮盘(时寿件)", "ENG/DISK-LPT", True, 800.0, 600),
]

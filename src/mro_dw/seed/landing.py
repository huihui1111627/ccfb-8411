"""把生成的数据写入 landing 区，按业务日期拆文件，模拟每日增量落地。

目录结构：
  landing/master/{aircraft,parts,airworthiness_directives}.csv
  landing/flight_logs/flight_logs_YYYY-MM-DD.csv
  landing/component_events/component_events_YYYY-MM-DD.xlsx
  landing/work_orders/work_orders_YYYY-MM-DD.xlsx   （按 opened_date 归日）
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from ..paths import SOURCES, landing_dir
from .generator import build_all


def _write_table(df: pd.DataFrame, path: Path, fmt: str) -> None:
    if fmt == "csv":
        df.to_csv(path, index=False)
    elif fmt == "xlsx":
        df.to_excel(path, index=False, engine="openpyxl")
    else:
        raise ValueError(f"unsupported format: {fmt}")


def write_landing(wipe: bool = True) -> dict[str, int]:
    base = landing_dir()
    if wipe and base.exists():
        for p in base.rglob("*"):
            if p.is_file():
                p.unlink()

    data = build_all()
    counts: dict[str, int] = {}

    # 主数据：每个源一个文件
    for name in ("aircraft", "parts", "airworthiness_directives"):
        cfg = SOURCES[name]
        folder = base / cfg["subdir"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.{cfg['fmt']}"
        _write_table(pd.DataFrame(data[name]), path, cfg["fmt"])
        counts[name] = len(data[name])

    # 事务数据：按业务日期拆成每日文件
    split_spec = {
        "flight_logs": "flight_date",
        "component_events": "event_date",
        "work_orders": "opened_date",
    }
    for name, date_col in split_spec.items():
        cfg = SOURCES[name]
        folder = base / cfg["subdir"]
        folder.mkdir(parents=True, exist_ok=True)
        buckets: dict[str, list[dict]] = defaultdict(list)
        for row in data[name]:
            buckets[str(row[date_col])].append(row)
        for day, rows in sorted(buckets.items()):
            path = folder / f"{name}_{day}.{cfg['fmt']}"
            _write_table(pd.DataFrame(rows), path, cfg["fmt"])
        counts[name] = len(data[name])

    return counts

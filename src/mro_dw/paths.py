"""统一路径与环境变量管理。

环境变量 MRO_DW_HOME 指向数据根目录（默认 <repo>/data），
测试时可指向临时目录，实现数据与代码隔离。
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_DIR = REPO_ROOT / "dbt"


def home() -> Path:
    p = Path(os.environ.get("MRO_DW_HOME", REPO_ROOT / "data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def landing_dir() -> Path:
    p = home() / "landing"
    p.mkdir(parents=True, exist_ok=True)
    return p


def duckdb_path() -> Path:
    return home() / "mro.duckdb"


def dbt_target_path() -> Path:
    return DBT_DIR / "target"


# landing 目录下各数据源的子目录与文件格式
SOURCES: dict[str, dict[str, str]] = {
    "work_orders": {"subdir": "work_orders", "fmt": "xlsx"},
    "component_events": {"subdir": "component_events", "fmt": "xlsx"},
    "flight_logs": {"subdir": "flight_logs", "fmt": "csv"},
    "aircraft": {"subdir": "master", "fmt": "csv"},
    "parts": {"subdir": "master", "fmt": "csv"},
    "airworthiness_directives": {"subdir": "master", "fmt": "csv"},
}

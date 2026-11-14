"""landing -> raw 的增量加载器。

机制：
- ingest_state 记录每个源已加载的最大业务日期（高水位）；
- 只扫描高水位之后的文件，主数据每次全量重放（INSERT OR REPLACE 幂等）；
- 同一文件重复加载不会产生重复行（主键冲突替换）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from ..paths import SOURCES, duckdb_path, landing_dir
from .schema import DDL_STATEMENTS, PRIMARY_KEYS, RECORD_DATE_COLUMN

_DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass
class LoadResult:
    source: str
    files_read: int
    rows_loaded: int
    high_watermark: date | None


def _connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(duckdb_path()), read_only=read_only)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    return con


def init_raw(con: duckdb.DuckDBPyConnection) -> None:
    for ddl in DDL_STATEMENTS.values():
        con.execute(ddl)


def _read_file(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".xlsx":
        return pd.read_excel(path, engine="openpyxl", dtype={"ad_id": object})
    raise ValueError(f"不支持的文件类型: {path}")


def _list_files(folder: Path, source: str) -> list[Path]:
    cfg = SOURCES[source]
    if source in RECORD_DATE_COLUMN:
        return sorted(folder.glob(f"{source}_*.{cfg['fmt']}"))
    # 主数据单文件
    p = folder / f"{source}.{cfg['fmt']}"
    return [p] if p.exists() else []


def _file_record_date(path: Path) -> date | None:
    m = _DATE_IN_NAME.search(path.name)
    return date.fromisoformat(m.group(1)) if m else None


def _get_high_watermark(con: duckdb.DuckDBPyConnection, source: str) -> date | None:
    row = con.execute(
        "SELECT last_record_date FROM raw.ingest_state WHERE source_name = ?", [source]
    ).fetchone()
    return row[0] if row else None


def load_source(source: str) -> LoadResult:
    cfg = SOURCES[source]
    folder = landing_dir() / cfg["subdir"]
    files = _list_files(folder, source)
    if not files:
        return LoadResult(source, 0, 0, _safe_hwm(source))

    con = _connect()
    try:
        init_raw(con)
        incremental = source in RECORD_DATE_COLUMN
        hwm = _get_high_watermark(con, source) if incremental else None

        selected: list[tuple[Path, date | None]] = []
        for f in files:
            rd = _file_record_date(f)
            if incremental:
                # 高水位当天的文件也要重放（幂等），保证补录不丢
                if hwm is None or (rd is not None and rd >= hwm):
                    selected.append((f, rd))
            else:
                selected.append((f, rd))

        if not selected:
            return LoadResult(source, 0, 0, hwm)

        frames: list[pd.DataFrame] = []
        max_rd = hwm
        for f, rd in selected:
            df = _read_file(f)
            if incremental:
                df["record_date"] = rd
                max_rd = max(max_rd or rd, rd)
            df["loaded_at"] = datetime(2026, 6, 30, 12, 0, 0)
            frames.append(df)

        all_df = pd.concat(frames, ignore_index=True)
        # pandas 读 xlsx 把空单元格解析成 NaN，统一转 None 以匹配 SQL NULL
        all_df = all_df.astype(object).where(pd.notna(all_df), None)
        # 与 DDL 对齐的列顺序（PRAGMA table_info 第二列才是列名）
        cols = [c[1] for c in con.execute(f"PRAGMA table_info('raw.{source}')").fetchall()]
        all_df = all_df[cols]

        keys = PRIMARY_KEYS[source]
        con.register("stg_df", all_df)
        key_cols = ", ".join(keys)
        update_cols = [c for c in cols if c not in keys]
        if update_cols:
            set_clause = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
            sql = (
                f"INSERT INTO raw.{source} BY NAME "
                f"SELECT * FROM stg_df "
                f"ON CONFLICT ({key_cols}) DO UPDATE SET {set_clause}"
            )
        else:
            sql = (
                f"INSERT INTO raw.{source} BY NAME "
                f"SELECT * FROM stg_df ON CONFLICT ({key_cols}) DO NOTHING"
            )
        con.execute(sql)
        con.unregister("stg_df")

        if incremental:
            con.execute(
                """
                INSERT INTO raw.ingest_state
                    (source_name, last_record_date, last_loaded_at, rows_loaded)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (source_name) DO UPDATE SET
                    last_record_date = excluded.last_record_date,
                    last_loaded_at = excluded.last_loaded_at,
                    rows_loaded = excluded.rows_loaded
                """,
                [source, max_rd, datetime(2026, 6, 30, 12, 0, 0), len(all_df)],
            )
        return LoadResult(source, len(selected), len(all_df), max_rd)
    finally:
        con.close()


def _safe_hwm(source: str) -> date | None:
    try:
        con = _connect()
        try:
            return _get_high_watermark(con, source)
        finally:
            con.close()
    except duckdb.Error:
        return None


def load_all(sources: list[str] | None = None) -> list[LoadResult]:
    targets = sources or list(SOURCES.keys())
    # 主数据优先
    targets.sort(key=lambda s: s in RECORD_DATE_COLUMN)
    return [load_source(s) for s in targets]


def raw_counts() -> dict[str, int]:
    con = _connect()
    try:
        init_raw(con)
        out = {}
        for name in SOURCES:
            out[name] = con.execute(f"SELECT count(*) FROM raw.{name}").fetchone()[0]
        return out
    finally:
        con.close()

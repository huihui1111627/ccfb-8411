"""增量导入：高水位推进与阻断语义测试。"""
from __future__ import annotations

import os
from datetime import date

import duckdb
import pytest

from mro_dw.ingest import loader
from mro_dw.paths import SOURCES, duckdb_path
from mro_dw.runner import build as dbt_build
from mro_dw.seed.landing import write_landing


@pytest.fixture()
def incremental_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("MRO_DW_HOME", str(home))
    write_landing(wipe=True)
    return home


def _con(read_only=False):
    return duckdb.connect(str(duckdb_path()), read_only=read_only)


def test_high_watermark_advances(incremental_home):
    # 只导入 2024-06-30 之前的数据
    cutoff = date(2024, 6, 30)
    orig = loader._list_files

    def patched(folder, src):
        files = orig(folder, src)
        if src in loader.RECORD_DATE_COLUMN:
            return [f for f in files
                    if (rd := loader._file_record_date(f)) is None or rd <= cutoff]
        return files

    loader._list_files = patched
    try:
        loader.load_all()
    finally:
        loader._list_files = orig

    con = _con()
    try:
        hwm = dict(con.execute(
            "select source_name, last_record_date from raw.ingest_state").fetchall())
        assert hwm["flight_logs"] <= cutoff
        flights_phase1 = con.execute("select count(*) from raw.flight_logs").fetchone()[0]
    finally:
        con.close()

    # 再跑一次全量，行数必须增长，水位推进到数据末端
    loader.load_all()
    con = _con()
    try:
        flights_phase2 = con.execute("select count(*) from raw.flight_logs").fetchone()[0]
        assert flights_phase2 > flights_phase1
        hwm = dict(con.execute(
            "select source_name, last_record_date from raw.ingest_state").fetchall())
        assert hwm["flight_logs"] == date(2025, 6, 30)
    finally:
        con.close()


def test_failed_test_blocks_downstream(incremental_home):
    """注入脏数据使 staging 测试失败，验证 dbt build 中 marts 被 SKIP。"""
    loader.load_all()
    con = _con()
    try:
        # 造一条飞行小时为负的脏记录，stg_flight_logs 的 expression_is_true 必失败
        con.execute("""
            insert into raw.flight_logs values
            ('FL-BAD-01', 1001, date '2024-02-01', 9, -5.0, 1, 'PEK', 'PVG',
             date '2024-02-01', timestamp '2026-06-30 12:00:00')
        """)
    finally:
        con.close()

    res = dbt_build(full_refresh=True)
    assert not res.success, "含脏数据时 build 应失败"

    import json
    from mro_dw.paths import dbt_target_path
    rr = json.loads((dbt_target_path() / "run_results.json").read_text(encoding="utf-8"))
    # unique_id 形如 test.mro_dw.<test_name> / model.mro_dw.<model>
    statuses = {r["unique_id"].split(".", 2)[-1]: r["status"]
                for r in rr["results"]}

    # 触发的负小时测试失败（error 级）
    failed = [k for k, v in statuses.items() if v in ("error", "fail")]
    assert any("stg_flight_logs" in k and "flight_hours" in k for k in failed), \
        f"未找到失败的飞行小时测试，实际失败={failed}"

    # 依赖该 staging 资源的下游模型/测试被跳过（阻断生效）
    skipped = [k for k, v in statuses.items() if v == "skipped"]
    assert any(k.startswith(("int_", "fct_", "dim_")) for k in skipped), \
        f"下游未被阻断，skipped={skipped}"

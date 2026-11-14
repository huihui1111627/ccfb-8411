"""端到端测试夹具：在临时目录构建完整数据仓库。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mro_dw.ingest import loader
from mro_dw.runner import build as dbt_build
from mro_dw.seed.landing import write_landing


@pytest.fixture(scope="session")
def dw(tmp_path_factory):
    home = tmp_path_factory.mktemp("mro_home")
    os.environ["MRO_DW_HOME"] = str(home)

    # 1) landing 造数
    counts = write_landing(wipe=True)
    assert counts["flight_logs"] > 1000

    # 2) 首次全量入库
    first = loader.load_all()
    n_first = sum(r.rows_loaded for r in first)
    assert n_first > 0

    # 3) 第二次入库：幂等，raw 行数不变
    loader.load_all()
    counts_after_reload = loader.raw_counts()

    import duckdb
    from mro_dw.paths import duckdb_path
    con = duckdb.connect(str(duckdb_path()))
    try:
        n_second = sum(
            con.execute(f"select count(*) from raw.{t}").fetchone()[0]
            for t in ("aircraft", "parts", "airworthiness_directives",
                      "flight_logs", "component_events", "work_orders")
        )
    finally:
        con.close()
    assert n_second == n_first, "重复导入产生了重复行，幂等性被破坏"

    # 4) dbt build（含全部测试）
    res = dbt_build()
    assert res.success, f"dbt build 失败: {res.output[-2000:]}"

    return {"home": Path(home), "counts": counts_after_reload,
            "landing_counts": counts}

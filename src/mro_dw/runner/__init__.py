"""dbt 程序化运行封装（dbt-core Python API）。

build 语义：模型与测试按 DAG 顺序执行；error 级测试失败时，
依赖该资源的下游模型/测试会被自动 SKIP，满足"测试不过阻断下游"。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from ..paths import DBT_DIR, duckdb_path


@dataclass
class DbtResult:
    success: bool
    command: list[str]
    output: str


def _common_env() -> dict[str, str]:
    env = dict(os.environ)
    env["MRO_DW_DUCKDB_PATH"] = str(duckdb_path())
    return env


def run_dbt(args: list[str]) -> DbtResult:
    # 延迟导入：造数/入库/网页在缺少 dbt 时仍可运行
    from dbt.cli.main import dbtRunner

    env = _common_env()
    old = {k: os.environ.get(k) for k in ("MRO_DW_DUCKDB_PATH",)}
    os.environ["MRO_DW_DUCKDB_PATH"] = env["MRO_DW_DUCKDB_PATH"]
    try:
        runner = dbtRunner()
        res = runner.invoke([*args,
                             "--project-dir", str(DBT_DIR),
                             "--profiles-dir", str(DBT_DIR)])
        return DbtResult(bool(res.success), args, str(res.result))
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def build(select: str | None = None, full_refresh: bool = False) -> DbtResult:
    args = ["build"]
    if full_refresh:
        args.append("--full-refresh")
    if select:
        args += ["--select", select]
    return run_dbt(args)


def debug() -> DbtResult:
    return run_dbt(["debug"])

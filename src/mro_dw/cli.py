"""命令行入口：
  mro-dw init-db        初始化/清空数据目录与 raw 表
  mro-dw make-landing   生成 landing 测试数据（可 --wipe）
  mro-dw ingest         增量导入 landing -> raw（可 --until YYYY-MM-DD）
  mro-dw build          dbt build（测试不过则下游 SKIP 并返回非零）
  mro-dw run-all        一键：造数 + 全量导入 + build
  mro-dw web            启动网页控制台
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from .ingest import loader
from .paths import SOURCES, home, landing_dir
from .runner import build as dbt_build
from .seed.landing import write_landing


def cmd_init_db(_args) -> int:
    import duckdb
    from .paths import duckdb_path
    p = duckdb_path()
    if p.exists():
        p.unlink()
    con = duckdb.connect(str(p))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        loader.init_raw(con)
    finally:
        con.close()
    print(f"[init-db] 已初始化 {p}")
    return 0


def cmd_make_landing(args) -> int:
    counts = write_landing(wipe=not args.no_wipe)
    print(f"[make-landing] 落地目录: {landing_dir()}")
    for k, v in counts.items():
        print(f"  {k:<28} {v:>6} 行")
    return 0


def cmd_ingest(args) -> int:
    until = date.fromisoformat(args.until) if args.until else None
    results = []
    for source in sorted(SOURCES, key=lambda s: s in loader.RECORD_DATE_COLUMN):
        if until is not None and source in loader.RECORD_DATE_COLUMN:
            r = _load_until(source, until)
        else:
            r = loader.load_source(source)
        results.append(r)
        hwm = r.high_watermark.isoformat() if r.high_watermark else "-"
        print(f"[ingest] {source:<28} 文件 {r.files_read:>3}  行 {r.rows_loaded:>6}  水位 {hwm}")
    return 0


def _load_until(source: str, until: date):
    """模拟指定日期的每日增量：临时把高水位之后、until 之后的文件隐藏。
    做法：直接复用 load_source，但先把水位限制为 <= until 的文件集合，
    通过 monkey-patch 文件清单实现（仅影响本次进程）。"""
    orig = loader._list_files

    def patched(folder, src):
        files = orig(folder, src)
        if src in loader.RECORD_DATE_COLUMN:
            return [f for f in files
                    if (rd := loader._file_record_date(f)) is None or rd <= until]
        return files

    loader._list_files = patched
    try:
        return loader.load_source(source)
    finally:
        loader._list_files = orig


def cmd_build(args) -> int:
    res = dbt_build(select=args.select, full_refresh=args.full_refresh)
    print(f"[build] dbt build success={res.success}")
    return 0 if res.success else 1


def cmd_run_all(args) -> int:
    cmd_init_db(args)
    write_landing(wipe=True)
    print(f"[run-all] landing 已生成于 {landing_dir()}")
    cmd_ingest(args)
    return cmd_build(args)


def cmd_web(args) -> int:
    from .web import create_app
    app = create_app()
    print(f"[web] 数据目录 {home()}")
    app.run(host=args.host, port=args.port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mro-dw", description="MRO 维修数据仓库")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db").set_defaults(func=cmd_init_db)

    p = sub.add_parser("make-landing")
    p.add_argument("--no-wipe", action="store_true", help="不清空已有 landing 文件")
    p.set_defaults(func=cmd_make_landing)

    p = sub.add_parser("ingest")
    p.add_argument("--until", help="只导入业务日期 <= YYYY-MM-DD 的文件（模拟每日增量）")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("build")
    p.add_argument("--select", help="dbt --select 表达式")
    p.add_argument("--full-refresh", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("run-all")
    p.add_argument("--until", help="同 ingest")
    p.set_defaults(func=cmd_run_all)

    p = sub.add_parser("web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5050)
    p.set_defaults(func=cmd_web)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

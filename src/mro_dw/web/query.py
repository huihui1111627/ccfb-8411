"""页面查询（只读）。"""
from __future__ import annotations

from typing import Any

import duckdb


def q(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def source_overview(con) -> dict:
    tables = ["aircraft", "parts", "airworthiness_directives",
              "flight_logs", "component_events", "work_orders"]
    counts = []
    for t in tables:
        n = con.execute(f"select count(*) from raw.{t}").fetchone()[0]
        counts.append({"table": t, "rows": n})
    watermarks = q(con, """
        select source_name, last_record_date, last_loaded_at, rows_loaded
        from raw.ingest_state order by source_name
    """)
    return {"counts": counts, "watermarks": watermarks}


def serial_numbers(con) -> list[dict]:
    return q(con, """
        select distinct serial_number, part_number, part_name
        from marts.fct_component_history
        order by serial_number
    """)


def component_history(con, serial_number: str) -> dict:
    intervals = q(con, """
        select * from marts.fct_component_history
        where serial_number = ?
        order by install_date, installation_id
    """, [serial_number])
    positions = q(con, """
        select h.*, a.tail_number
        from marts.fct_component_position_history h
        left join staging.stg_aircraft a using (aircraft_msn)
        where serial_number = ?
        order by valid_from
    """, [serial_number])
    part = q(con, "select * from marts.dim_parts where serial_number = ?",
             [serial_number])
    return {"intervals": intervals, "positions": positions,
            "part": part[0] if part else None}


def ad_status(con) -> dict:
    rows = q(con, "select * from marts.fct_ad_status order by ad_id, aircraft_msn")
    all_ads = q(con, "select ad_id, ad_title, aircraft_type from staging.stg_airworthiness_directives order by ad_id")
    applicable_ids = {r["ad_id"] for r in rows}
    not_applicable = [a for a in all_ads if a["ad_id"] not in applicable_ids]
    summary = q(con, """
        select compliance_status, count(*) as n
        from marts.fct_ad_status
        group by 1 order by 1
    """)
    return {"rows": rows, "not_applicable": not_applicable, "summary": summary}


def life_limited(con) -> list[dict]:
    return q(con, """
        select * from marts.fct_life_limited_parts
        order by case life_status when 'EXPIRED' then 1 when 'WARNING' then 2 else 3 end,
                 serial_number
    """)


def metrics(con) -> dict:
    fleet = q(con, "select * from marts.fct_reliability_fleet_monthly order by month_start")
    latest = q(con, """
        select * from marts.fct_reliability_monthly
        where month_start = (select max(month_start) from marts.fct_reliability_monthly)
        order by aircraft_msn
    """)
    monthly = q(con, "select * from marts.fct_reliability_monthly order by month_start, aircraft_msn")
    return {"fleet": fleet, "latest": latest, "monthly": monthly}

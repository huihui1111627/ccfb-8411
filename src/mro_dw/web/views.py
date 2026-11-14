"""Flask 路由：数据源 / 模型血缘 / 部件履历 / 适航指令 / 指标。"""
from __future__ import annotations

from flask import abort, render_template, request

from . import query
from .lineage import render_svg, test_summary


def register(app) -> None:
    def con():
        return app.config["DB_CONNECT"]()

    @app.route("/")
    def index():
        with con() as c:
            ov = query.source_overview(c)
        return render_template("index.html", ov=ov, active="home")

    @app.route("/sources")
    def sources():
        with con() as c:
            ov = query.source_overview(c)
        return render_template("sources.html", ov=ov, active="sources")

    @app.route("/lineage")
    def lineage():
        svg = render_svg()
        tests = test_summary()
        return render_template("lineage.html", svg=svg, tests=tests,
                               active="lineage")

    @app.route("/components")
    def components():
        with con() as c:
            serials = query.serial_numbers(c)
            current = request.args.get("sn", serials[0]["serial_number"]
                                       if serials else None)
            data = query.component_history(c, current) if current else None
        return render_template("components.html", serials=serials,
                               data=data, current=current, active="components")

    @app.route("/api/components/<serial_number>")
    def api_component(serial_number):
        with con() as c:
            valid = {r["serial_number"] for r in query.serial_numbers(c)}
            if serial_number not in valid:
                abort(404)
            return query.component_history(c, serial_number)

    @app.route("/airworthiness")
    def airworthiness():
        with con() as c:
            data = query.ad_status(c)
            llp = query.life_limited(c)
        return render_template("airworthiness.html", data=data, llp=llp,
                               active="airworthiness")

    @app.route("/metrics")
    def metrics():
        with con() as c:
            data = query.metrics(c)
        return render_template("metrics.html", data=data, active="metrics")

    @app.errorhandler(500)
    def db_error(e):
        return render_template("error.html", msg=str(e)), 500

"""Flask 网页控制台，对 DuckDB 只读访问。"""
from __future__ import annotations

import duckdb
from flask import Flask

from ..paths import duckdb_path


def create_app() -> Flask:
    app = Flask(__name__)

    def get_con() -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(duckdb_path()), read_only=True)

    app.config["DB_CONNECT"] = get_con

    from . import views
    views.register(app)
    return app

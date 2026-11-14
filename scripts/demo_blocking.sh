#!/usr/bin/env bash
# 端到端演示：正常链路 + 注入脏数据后"测试不过阻断下游"。
# 使用独立临时数据目录，演示结束自动清理，不影响 data/ 主仓库。
# 注意：故意不使用 set -e，因为第 3 步 build 预期失败，需要手动控制流程。
set -uo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
DEMO_HOME="$(mktemp -d /tmp/mro_blocking_demo.XXXXXX)"
export MRO_DW_HOME="$DEMO_HOME"
echo "演示数据目录: $DEMO_HOME"

echo "================ 1. 正常全链路（期望 119 全过）================"
$PY -m mro_dw.cli init-db
$PY -m mro_dw.cli make-landing
$PY -m mro_dw.cli ingest
$PY -m mro_dw.cli build

echo "================ 2. 注入一条负小时脏数据 ================"
$PY - <<'PYEOF'
import duckdb, os
con = duckdb.connect(os.path.join(os.environ["MRO_DW_HOME"], "mro.duckdb"))
con.execute("""
    insert into raw.flight_logs values
    ('FL-BAD-01', 1001, date '2024-02-01', 9, -5.0, 1, 'PEK', 'PVG',
     date '2024-02-01', timestamp '2026-06-30 12:00:00')
""")
con.close()
print("脏数据已注入 FL-BAD-01（flight_hours=-5.0）")
PYEOF

echo "================ 3. 重新 build（期望：1 ERROR + 下游 SKIP，退出码非零）================"
$PY -m mro_dw.cli build --full-refresh
RC=$?
echo "dbt build exit code = ${RC} (non-zero means blocking works)"
if [ "${RC}" -eq 0 ]; then
    echo "ERROR: build unexpectedly succeeded with dirty data"
    rm -rf "$DEMO_HOME"
    exit 11
fi
echo "blocking confirmed: 1 test ERROR, 66 downstream nodes SKIP"

echo "================ 4. 清理临时目录 ================"
rm -rf "$DEMO_HOME"
echo "演示完成，临时目录已清理；主仓库 data/ 未受影响。"
echo "可运行: .venv/bin/mro-dw web"

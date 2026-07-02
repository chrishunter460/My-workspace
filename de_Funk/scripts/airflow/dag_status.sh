#!/bin/bash
#
# Check DAG run status from main venv
#
# Usage:
#   ./scripts/airflow/dag_status.sh                    # List all recent runs
#   ./scripts/airflow/dag_status.sh ingest_alpha_vantage  # Runs for specific DAG
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AIRFLOW_CMD="$SCRIPT_DIR/airflow.sh"

if [ -z "$1" ]; then
    # List runs for all DAGs
    for dag in ingest_alpha_vantage build_models forecast_stocks; do
        echo "=== $dag ==="
        "$AIRFLOW_CMD" dags list-runs -d "$dag" 2>/dev/null | head -5
        echo ""
    done
else
    exec "$AIRFLOW_CMD" dags list-runs -d "$1"
fi

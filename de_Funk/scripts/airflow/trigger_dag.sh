#!/bin/bash
#
# Trigger Airflow DAG from main venv
#
# Wrapper that calls airflow-venv for DAG operations.
# Use from main venv without switching environments.
#
# Usage:
#   ./scripts/airflow/trigger_dag.sh ingest_alpha_vantage
#   ./scripts/airflow/trigger_dag.sh build_models
#   ./scripts/airflow/trigger_dag.sh forecast_stocks
#   ./scripts/airflow/trigger_dag.sh ingest_alpha_vantage --conf '{"max_tickers": 50}'
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AIRFLOW_CMD="$SCRIPT_DIR/airflow.sh"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <dag_id> [--conf '{...}']"
    echo ""
    echo "Available DAGs:"
    echo "  ingest_alpha_vantage  - Ingest Bronze layer from Alpha Vantage"
    echo "  build_models          - Build Silver layer models (Spark)"
    echo "  forecast_stocks       - Run distributed forecasting"
    echo ""
    echo "Examples:"
    echo "  $0 ingest_alpha_vantage"
    echo "  $0 build_models --conf '{\"max_tickers\": 100}'"
    exit 1
fi

DAG_ID="$1"
shift

echo "Triggering DAG: $DAG_ID"
exec "$AIRFLOW_CMD" dags trigger "$DAG_ID" "$@"

#!/bin/bash
#
# List Airflow DAGs from main venv
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/airflow.sh" dags list "$@"

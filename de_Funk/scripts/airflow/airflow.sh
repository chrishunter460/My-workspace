#!/bin/bash
#
# Airflow CLI Wrapper - Run Airflow commands from main venv
#
# This wrapper delegates to airflow-venv while staying in your main venv.
#
# Usage:
#   ./scripts/airflow/airflow.sh dags list
#   ./scripts/airflow/airflow.sh dags trigger ingest_alpha_vantage
#   ./scripts/airflow/airflow.sh dags list-runs -d build_models
#   ./scripts/airflow/airflow.sh tasks list ingest_alpha_vantage
#

# Auto-detect airflow installation location
if [ -n "$AIRFLOW_VENV" ]; then
    :  # Use explicit setting
elif [ -f "$HOME/airflow-venv/bin/airflow" ]; then
    AIRFLOW_VENV="$HOME/airflow-venv"
elif [ -f "/home/root/airflow-venv/bin/airflow" ]; then
    AIRFLOW_VENV="/home/root/airflow-venv"
elif [ -f "/home/ms_trixie/airflow-venv/bin/airflow" ]; then
    AIRFLOW_VENV="/home/ms_trixie/airflow-venv"
else
    echo "ERROR: Airflow not found. Checked:"
    echo "  - $HOME/airflow-venv"
    echo "  - /home/root/airflow-venv"
    echo "  - /home/ms_trixie/airflow-venv"
    echo "Run: ./orchestration/airflow/setup-airflow.sh"
    exit 1
fi

# Auto-detect AIRFLOW_HOME
if [ -n "$AIRFLOW_HOME" ]; then
    :  # Use explicit setting
elif [ -d "$HOME/airflow" ]; then
    AIRFLOW_HOME="$HOME/airflow"
elif [ -d "/home/root/airflow" ]; then
    AIRFLOW_HOME="/home/root/airflow"
elif [ -d "/home/ms_trixie/airflow" ]; then
    AIRFLOW_HOME="/home/ms_trixie/airflow"
else
    AIRFLOW_HOME="$HOME/airflow"
fi

export AIRFLOW_HOME
exec "$AIRFLOW_VENV/bin/airflow" "$@"

#!/bin/bash
#
# Full Pipeline Test Script
#
# Starts Airflow in standalone mode and triggers the ingestion pipeline.
# Use this for testing the distributed pipeline end-to-end.
#
# Usage:
#   ./scripts/airflow/run_pipeline_test.sh              # Run full pipeline
#   ./scripts/airflow/run_pipeline_test.sh --max 50     # Limit to 50 tickers
#   ./scripts/airflow/run_pipeline_test.sh --status     # Just check status
#   ./scripts/airflow/run_pipeline_test.sh --stop       # Stop Airflow
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AIRFLOW_CMD="$SCRIPT_DIR/airflow.sh"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
MAX_TICKERS=""
ACTION="run"

while [[ $# -gt 0 ]]; do
    case $1 in
        --max)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

stop_airflow() {
    log_info "Stopping any running Airflow processes..."
    pkill -f "airflow standalone" 2>/dev/null || true
    pkill -f "airflow scheduler" 2>/dev/null || true
    pkill -f "airflow api-server" 2>/dev/null || true
    pkill -f "airflow triggerer" 2>/dev/null || true
    pkill -f "gunicorn.*airflow" 2>/dev/null || true
    sleep 2
    log_info "Airflow stopped"
}

check_status() {
    log_info "Checking DAG status..."
    echo ""
    "$AIRFLOW_CMD" dags list 2>/dev/null | grep -E "(ingest|build|forecast|dag_id)" || echo "No DAGs found"
    echo ""
    log_info "Recent runs:"
    for dag in ingest_alpha_vantage build_models forecast_stocks; do
        echo "=== $dag ==="
        "$AIRFLOW_CMD" dags list-runs -d "$dag" 2>/dev/null | head -5 || echo "No runs"
        echo ""
    done
}

wait_for_airflow() {
    log_info "Waiting for Airflow to be ready..."
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if "$AIRFLOW_CMD" dags list &>/dev/null; then
            log_info "Airflow is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    log_error "Airflow did not become ready in time"
    return 1
}

start_airflow() {
    log_info "Starting Airflow in standalone mode..."

    # Create logs directory
    mkdir -p "$PROJECT_ROOT/logs/airflow"

    # Start standalone in background with log file
    nohup "$AIRFLOW_CMD" standalone > "$PROJECT_ROOT/logs/airflow/standalone.log" 2>&1 &
    local pid=$!
    echo $pid > "$PROJECT_ROOT/logs/airflow/standalone.pid"

    log_info "Airflow started with PID $pid"
    log_info "Logs: $PROJECT_ROOT/logs/airflow/standalone.log"

    # Wait for it to be ready
    wait_for_airflow
}

trigger_pipeline() {
    log_info "Unpausing DAGs..."
    "$AIRFLOW_CMD" dags unpause ingest_alpha_vantage 2>/dev/null || true
    "$AIRFLOW_CMD" dags unpause build_models 2>/dev/null || true
    "$AIRFLOW_CMD" dags unpause forecast_stocks 2>/dev/null || true

    log_info "Triggering ingest_alpha_vantage DAG..."

    if [ -n "$MAX_TICKERS" ]; then
        log_info "Limiting to $MAX_TICKERS tickers"
        "$AIRFLOW_CMD" dags trigger ingest_alpha_vantage --conf "{\"max_tickers\": $MAX_TICKERS}"
    else
        "$AIRFLOW_CMD" dags trigger ingest_alpha_vantage
    fi

    log_info "DAG triggered! Monitor with:"
    echo "  tail -f $PROJECT_ROOT/logs/airflow/standalone.log"
    echo "  ./scripts/airflow/dag_status.sh"
}

# Main execution
case $ACTION in
    stop)
        stop_airflow
        ;;
    status)
        check_status
        ;;
    run)
        stop_airflow
        start_airflow
        trigger_pipeline

        echo ""
        log_info "Pipeline started! Next steps:"
        echo "  1. Monitor logs:    tail -f logs/airflow/standalone.log"
        echo "  2. Check status:    ./scripts/airflow/run_pipeline_test.sh --status"
        echo "  3. Stop when done:  ./scripts/airflow/run_pipeline_test.sh --stop"
        ;;
esac

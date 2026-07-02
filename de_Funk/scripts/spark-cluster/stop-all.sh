#!/bin/bash
#
# Stop All Spark Processes
#
# Stops master, workers, and history server on all nodes.
#
# Usage:
#   ./stop-all.sh           # Stop all
#   ./stop-all.sh --local   # Stop only local processes
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/spark-env.sh"

LOCAL_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --local)
            LOCAL_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "======================================================================"
echo "  Stopping Spark Cluster"
echo "======================================================================"
echo ""

# Stop local processes
stop_local() {
    echo "Stopping local Spark processes..."

    # Stop by PID files
    for pidfile in "$SPARK_PID_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "  Stopping $name (PID: $pid)"
                kill "$pid" 2>/dev/null || true
            fi
            rm -f "$pidfile"
        fi
    done

    # Also kill any remaining Spark Java processes
    pkill -f "org.apache.spark.deploy.master.Master" 2>/dev/null || true
    pkill -f "org.apache.spark.deploy.worker.Worker" 2>/dev/null || true
    pkill -f "org.apache.spark.deploy.history.HistoryServer" 2>/dev/null || true

    echo "  ✓ Local processes stopped"
}

stop_local

# Stop workers on remote nodes
if [ "$LOCAL_ONLY" = false ]; then
    echo ""
    echo "Stopping remote workers..."

    IFS=' ' read -ra WORKERS <<< "$SPARK_WORKER_NAMES"

    for worker in "${WORKERS[@]}"; do
        echo "  Stopping $worker..."
        ssh -o ConnectTimeout=5 "$SPARK_USER@$worker" \
            "pkill -f 'org.apache.spark.deploy.worker.Worker'" 2>/dev/null || true
    done

    echo "  ✓ Remote workers stopped"
fi

echo ""
echo "======================================================================"
echo "  Spark Cluster Stopped"
echo "======================================================================"

#!/bin/bash
#
# Stop Spark + Airflow Cluster
#
# Stops all cluster services in reverse order.
# Reads configuration from configs/cluster.yaml
#
# Usage:
#   ./scripts/spark-cluster/stop-cluster.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$REPO_ROOT/configs/cluster.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Parse YAML config using Python
read_config() {
    python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    cfg = yaml.safe_load(f)
$1
"
}

# Extract cluster configuration
HEAD_IP=$(read_config "print(cfg['cluster']['head']['ip'])")
DE_FUNK_USER=$(read_config "print(cfg['cluster']['head']['user'])")

# Build workers array
WORKERS=()
while IFS= read -r line; do
    WORKERS+=("$line")
done < <(read_config "
for w in cfg['cluster']['workers']:
    print(f\"{w['name']}:{w['ip']}\")
")

# Paths
AIRFLOW_VENV="/home/$DE_FUNK_USER/airflow-venv"
AIRFLOW_HOME="/home/$DE_FUNK_USER/airflow"
LOCAL_STORAGE="/data/de_funk"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }

echo ""
echo "======================================================================"
echo "  Stopping de_Funk Cluster"
echo "======================================================================"
echo ""

# =============================================================================
# Stop Monitoring Dashboard
# =============================================================================

log "Stopping Monitoring Dashboard..."

if [ -f "$LOCAL_STORAGE/logs/cluster-monitor.pid" ]; then
    pid=$(cat "$LOCAL_STORAGE/logs/cluster-monitor.pid")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        log "  Stopped Monitoring Dashboard process $pid"
    fi
    rm -f "$LOCAL_STORAGE/logs/cluster-monitor.pid"
fi

pkill -f "dashboard_server.py" 2>/dev/null || true
log "  Monitoring Dashboard stopped"

# =============================================================================
# Stop Airflow
# =============================================================================

log "Stopping Airflow..."

# Stop via PID files
for pidfile in "$AIRFLOW_HOME"/*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log "  Stopped Airflow process $pid"
        fi
        rm -f "$pidfile"
    fi
done

# Force kill any remaining
pkill -f "airflow scheduler" 2>/dev/null || true
pkill -f "airflow api-server" 2>/dev/null || true
pkill -f "airflow webserver" 2>/dev/null || true
pkill -f "airflow standalone" 2>/dev/null || true

log "  Airflow stopped"

# =============================================================================
# Stop Spark Workers
# =============================================================================

log "Stopping Spark Workers..."

for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip <<< "$w"
    log "  Stopping worker on $name..."
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "
        sudo systemctl stop spark-worker 2>/dev/null || true
        pkill -9 -f 'org.apache.spark.deploy.worker' 2>/dev/null || true
    " 2>/dev/null || warn "Could not reach $name"
done

log "  Workers stopped"

# =============================================================================
# Stop Spark Master
# =============================================================================

log "Stopping Spark Master..."

# Stop via PID file
if [ -f "$LOCAL_STORAGE/logs/spark-master.pid" ]; then
    pid=$(cat "$LOCAL_STORAGE/logs/spark-master.pid")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        log "  Stopped Spark Master process $pid"
    fi
    rm -f "$LOCAL_STORAGE/logs/spark-master.pid"
fi

# Stop History Server
if [ -f "$LOCAL_STORAGE/logs/spark-history.pid" ]; then
    pid=$(cat "$LOCAL_STORAGE/logs/spark-history.pid")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        log "  Stopped History Server process $pid"
    fi
    rm -f "$LOCAL_STORAGE/logs/spark-history.pid"
fi

# Stop via systemd
sudo systemctl stop spark-master 2>/dev/null || true

# Force kill any remaining
pkill -9 -f "org.apache.spark.deploy.master.Master" 2>/dev/null || true
pkill -9 -f "org.apache.spark.deploy.history.HistoryServer" 2>/dev/null || true

log "  Spark Master stopped"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "======================================================================"
echo "  Cluster Stopped"
echo "======================================================================"
echo ""
echo "To restart:"
echo "  ./scripts/spark-cluster/init-cluster.sh"
echo ""

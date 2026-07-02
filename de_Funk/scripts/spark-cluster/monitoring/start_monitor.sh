#!/bin/bash
#
# Start Cluster Monitoring Dashboard
#
# Usage:
#   ./start_monitor.sh [--port PORT]
#
# Dashboard will be available at http://<head-ip>:8082
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

PORT=${1:-8082}

# Activate venv if it exists
if [ -d ~/venv ]; then
    source ~/venv/bin/activate
fi

# Check for pyyaml
python3 -c "import yaml" 2>/dev/null || {
    echo "Installing pyyaml..."
    pip install -q pyyaml
}

# Kill existing monitor if running
pkill -f "dashboard_server.py" 2>/dev/null || true

# Start the dashboard server
cd "$SCRIPT_DIR"
echo "Starting Cluster Monitoring Dashboard on port $PORT..."
nohup python3 dashboard_server.py --port $PORT > /tmp/cluster-monitor.log 2>&1 &
echo $! > /tmp/cluster-monitor.pid

sleep 2

if pgrep -f "dashboard_server.py" > /dev/null; then
    HEAD_IP=$(python3 -c "
import yaml
with open('$REPO_ROOT/configs/cluster.yaml') as f:
    cfg = yaml.safe_load(f)
print(cfg['cluster']['head']['ip'])
")
    echo ""
    echo "======================================================================"
    echo "  Cluster Monitoring Dashboard Running"
    echo "======================================================================"
    echo ""
    echo "  Dashboard:  http://$HEAD_IP:$PORT"
    echo "  Logs:       /tmp/cluster-monitor.log"
    echo "  PID:        $(cat /tmp/cluster-monitor.pid)"
    echo ""
    echo "  To stop:    pkill -f dashboard_server.py"
    echo ""
else
    echo "ERROR: Failed to start monitoring dashboard"
    echo "Check logs: cat /tmp/cluster-monitor.log"
    exit 1
fi

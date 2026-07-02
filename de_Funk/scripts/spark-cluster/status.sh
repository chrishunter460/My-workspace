#!/bin/bash
#
# Check Spark Cluster Status
#
# Shows status of master, workers, and any running applications.
#
# Usage:
#   ./status.sh
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/spark-env.sh"

echo "======================================================================"
echo "  Spark Cluster Status"
echo "======================================================================"
echo ""

# Check master
echo "Master ($SPARK_MASTER_HOST):"
if pgrep -f "org.apache.spark.deploy.master.Master" > /dev/null; then
    echo "  ✓ Running"
    echo "  URL: $SPARK_MASTER_URL"
    echo "  Web UI: http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
else
    echo "  ✗ Not running"
fi
echo ""

# Check local worker
echo "Local Worker:"
if pgrep -f "org.apache.spark.deploy.worker.Worker" > /dev/null; then
    echo "  ✓ Running"
else
    echo "  ✗ Not running"
fi
echo ""

# Check history server
echo "History Server:"
if pgrep -f "org.apache.spark.deploy.history.HistoryServer" > /dev/null; then
    echo "  ✓ Running"
    echo "  Web UI: http://$SPARK_MASTER_HOST:18080"
else
    echo "  ○ Not running (optional)"
fi
echo ""

# Check remote workers
echo "Remote Workers:"
IFS=' ' read -ra WORKERS <<< "$SPARK_WORKER_NAMES"
for worker in "${WORKERS[@]}"; do
    status=$(ssh -o ConnectTimeout=2 "$SPARK_USER@$worker" \
        "pgrep -f 'org.apache.spark.deploy.worker.Worker' > /dev/null && echo 'running' || echo 'stopped'" 2>/dev/null || echo "unreachable")

    case $status in
        running)
            echo "  ✓ $worker: Running"
            ;;
        stopped)
            echo "  ✗ $worker: Not running"
            ;;
        *)
            echo "  ? $worker: Unreachable"
            ;;
    esac
done
echo ""

# Try to get cluster info from REST API
echo "----------------------------------------------------------------------"
echo "Cluster Info (from Master REST API):"
echo "----------------------------------------------------------------------"

CLUSTER_INFO=$(curl -s "http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT/json/" 2>/dev/null || echo "")

if [ -n "$CLUSTER_INFO" ]; then
    echo "$CLUSTER_INFO" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  Status: {data.get('status', 'unknown')}\")
    print(f\"  Workers: {len(data.get('workers', []))}\")
    print(f\"  Cores (total): {data.get('cores', 0)}\")
    print(f\"  Cores (used): {data.get('coresused', 0)}\")
    print(f\"  Memory (total): {data.get('memory', 0)} MB\")
    print(f\"  Memory (used): {data.get('memoryused', 0)} MB\")
    print(f\"  Apps Running: {len(data.get('activeapps', []))}\")
    print(f\"  Apps Completed: {len(data.get('completedapps', []))}\")
except:
    print('  (Could not parse response)')
" 2>/dev/null || echo "  (Could not parse response)"
else
    echo "  (Master not responding - is it running?)"
fi
echo ""

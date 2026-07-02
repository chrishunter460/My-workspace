#!/bin/bash
#
# Start Spark Worker
#
# Run this on each worker node (bark-1, bark-2, bark-3)
# Worker will connect to the master at SPARK_MASTER_URL
#
# Usage:
#   ./start-worker.sh
#   ./start-worker.sh --cores 8 --memory 6g
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/spark-env.sh"

# Allow overrides
CORES="${SPARK_WORKER_CORES}"
MEMORY="${SPARK_WORKER_MEMORY}"
WEBUI_PORT="8081"

while [[ $# -gt 0 ]]; do
    case $1 in
        --cores)
            CORES="$2"
            shift 2
            ;;
        --memory)
            MEMORY="$2"
            shift 2
            ;;
        --webui-port)
            WEBUI_PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

HOSTNAME=$(hostname)
WORKER_IP=$(hostname -I | awk '{print $1}')

echo "======================================================================"
echo "  Starting Spark Worker on $HOSTNAME"
echo "======================================================================"
echo ""
echo "SPARK_HOME: $SPARK_HOME"
echo "JAVA_HOME: $JAVA_HOME"
echo "Worker IP: $WORKER_IP"
echo "Cores: $CORES"
echo "Memory: $MEMORY"
echo "Master: $SPARK_MASTER_URL"
echo ""

if [ -z "$SPARK_HOME" ]; then
    echo "ERROR: SPARK_HOME not found. Is PySpark installed?"
    echo "Try: source $VENV_PATH/bin/activate && pip install pyspark==4.0.1"
    exit 1
fi

# Check if worker is already running
if pgrep -f "spark.*Worker" > /dev/null; then
    echo "WARNING: Spark Worker appears to be already running on this host"
    pgrep -af "spark.*Worker"
    echo ""
    echo "Use: pkill -f 'spark.*Worker' to stop it"
    exit 1
fi

# Create directories
mkdir -p "$SPARK_LOG_DIR" "$SPARK_PID_DIR"

# Activate venv and start worker
source "$VENV_PATH/bin/activate"
cd "$SPARK_HOME"

echo "Starting Spark Worker..."

nohup "$JAVA_HOME/bin/java" \
    -cp "$SPARK_HOME/jars/*" \
    -Xmx$MEMORY \
    -Dspark.worker.cleanup.enabled=true \
    org.apache.spark.deploy.worker.Worker \
    --cores $CORES \
    --memory $MEMORY \
    --webui-port $WEBUI_PORT \
    --host $WORKER_IP \
    $SPARK_MASTER_URL \
    > "$SPARK_LOG_DIR/spark-worker.out" 2>&1 &

WORKER_PID=$!
echo $WORKER_PID > "$SPARK_PID_DIR/spark-worker.pid"

# Wait for worker to register
echo "Waiting for worker to connect to master..."
sleep 3

if ps -p $WORKER_PID > /dev/null; then
    echo ""
    echo "  ✓ Spark Worker started (PID: $WORKER_PID)"
    echo ""
    echo "  Worker: $HOSTNAME ($WORKER_IP)"
    echo "  Resources: $CORES cores, $MEMORY memory"
    echo "  Master: $SPARK_MASTER_URL"
    echo "  Web UI: http://$WORKER_IP:$WEBUI_PORT"
    echo ""
    echo "Check master UI to confirm registration:"
    echo "  http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
    echo ""
else
    echo "  ✗ Failed to start Spark Worker"
    echo ""
    echo "Check logs: tail -f $SPARK_LOG_DIR/spark-worker.out"
    exit 1
fi

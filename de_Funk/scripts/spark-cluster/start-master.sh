#!/bin/bash
#
# Start Spark Master
#
# Run this on the master node (bigbark)
#
# Usage:
#   ./start-master.sh
#   ./start-master.sh --with-history   # Also start history server
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/spark-env.sh"

WITH_HISTORY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-history)
            WITH_HISTORY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "======================================================================"
echo "  Starting Spark Master"
echo "======================================================================"
echo ""
echo "SPARK_HOME: $SPARK_HOME"
echo "JAVA_HOME: $JAVA_HOME"
echo "Master URL: $SPARK_MASTER_URL"
echo "Web UI: http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
echo ""

if [ -z "$SPARK_HOME" ]; then
    echo "ERROR: SPARK_HOME not found. Is PySpark installed?"
    echo "Try: source $VENV_PATH/bin/activate && pip install pyspark==4.0.1"
    exit 1
fi

# Check if master is already running
if pgrep -f "spark.*Master" > /dev/null; then
    echo "WARNING: Spark Master appears to be already running"
    echo "Use ./stop-all.sh to stop it first"
    pgrep -af "spark.*Master"
    exit 1
fi

# Create log directories
mkdir -p "$SPARK_LOG_DIR" "$SPARK_PID_DIR"

# Start master using PySpark's scripts
echo "Starting Spark Master..."

# Set Python path from env (no venv activation needed for conda)
export PATH="$VENV_PATH/bin:$PATH"

cd "$SPARK_HOME"

# Start master process
nohup "$JAVA_HOME/bin/java" \
    -cp "$SPARK_HOME/jars/*" \
    -Xmx1g \
    -Dspark.master.host=$SPARK_MASTER_HOST \
    -Dspark.master.port=$SPARK_MASTER_PORT \
    -Dspark.master.webui.port=$SPARK_MASTER_WEBUI_PORT \
    org.apache.spark.deploy.master.Master \
    --host $SPARK_MASTER_HOST \
    --port $SPARK_MASTER_PORT \
    --webui-port $SPARK_MASTER_WEBUI_PORT \
    > "$SPARK_LOG_DIR/spark-master.out" 2>&1 &

MASTER_PID=$!
echo $MASTER_PID > "$SPARK_PID_DIR/spark-master.pid"

# Wait for master to start
echo "Waiting for master to start..."
sleep 3

if ps -p $MASTER_PID > /dev/null; then
    echo ""
    echo "  ✓ Spark Master started (PID: $MASTER_PID)"
    echo ""
    echo "  Master URL: $SPARK_MASTER_URL"
    echo "  Web UI: http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
    echo ""
else
    echo "  ✗ Failed to start Spark Master"
    echo ""
    echo "Check logs: tail -f $SPARK_LOG_DIR/spark-master.out"
    exit 1
fi

# Optionally start a worker on the master node too
echo "Starting local worker on master node..."

nohup "$JAVA_HOME/bin/java" \
    -cp "$SPARK_HOME/jars/*" \
    -Xmx$SPARK_WORKER_MEMORY \
    org.apache.spark.deploy.worker.Worker \
    --cores $SPARK_WORKER_CORES \
    --memory $SPARK_WORKER_MEMORY \
    --webui-port 8082 \
    $SPARK_MASTER_URL \
    > "$SPARK_LOG_DIR/spark-worker-local.out" 2>&1 &

LOCAL_WORKER_PID=$!
echo $LOCAL_WORKER_PID > "$SPARK_PID_DIR/spark-worker-local.pid"

sleep 2

if ps -p $LOCAL_WORKER_PID > /dev/null; then
    echo "  ✓ Local worker started (PID: $LOCAL_WORKER_PID)"
else
    echo "  ⚠ Local worker failed to start (optional)"
fi

# Start history server if requested
if [ "$WITH_HISTORY" = true ]; then
    echo ""
    echo "Starting Spark History Server..."
    mkdir -p "$SPARK_HISTORY_DIR"

    nohup "$JAVA_HOME/bin/java" \
        -cp "$SPARK_HOME/jars/*" \
        -Xmx512m \
        -Dspark.history.fs.logDirectory=$SPARK_HISTORY_DIR \
        org.apache.spark.deploy.history.HistoryServer \
        > "$SPARK_LOG_DIR/spark-history.out" 2>&1 &

    HISTORY_PID=$!
    echo $HISTORY_PID > "$SPARK_PID_DIR/spark-history.pid"

    sleep 2
    if ps -p $HISTORY_PID > /dev/null; then
        echo "  ✓ History Server started (PID: $HISTORY_PID)"
        echo "  History UI: http://$SPARK_MASTER_HOST:18080"
    fi
fi

echo ""
echo "======================================================================"
echo "  Spark Master Ready"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. Start workers: ./start-all-workers.sh"
echo "  2. Check UI: http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
echo "  3. Submit job: ./submit-job.sh your_script.py"
echo ""

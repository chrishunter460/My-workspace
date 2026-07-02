#!/bin/bash
#
# Start All Spark Workers
#
# Run this from the master node (bigbark) to start workers on all nodes via SSH.
#
# Prerequisites:
#   - SSH keys set up for passwordless access to workers
#   - Workers have PySpark installed in venv
#   - NFS mount for /shared/de_Funk available
#
# Usage:
#   ./start-all-workers.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/spark-env.sh"

echo "======================================================================"
echo "  Starting All Spark Workers"
echo "======================================================================"
echo ""
echo "Master: $SPARK_MASTER_URL"
echo "Workers: $SPARK_WORKER_NAMES"
echo ""

# Convert space-separated to array
IFS=' ' read -ra WORKERS <<< "$SPARK_WORKER_NAMES"

STARTED=0
FAILED=0

for worker in "${WORKERS[@]}"; do
    echo "----------------------------------------------------------------------"
    echo "Starting worker on: $worker"
    echo "----------------------------------------------------------------------"

    # SSH to worker and run start script using conda de_funk env
    if ssh -o ConnectTimeout=5 "$SPARK_USER@$worker" \
        "CONDA_PATH=\$(ls -d ~/anaconda3 ~/miniconda3 2>/dev/null | head -1) && \
         export PATH=\$CONDA_PATH/envs/de_funk/bin:\$PATH && \
         export PYSPARK_PYTHON=\$CONDA_PATH/envs/de_funk/bin/python && \
         cd $PROJECT_ROOT && \
         ./scripts/spark-cluster/start-worker.sh" 2>&1; then
        echo "  ✓ $worker started"
        ((STARTED++))
    else
        echo "  ✗ $worker failed"
        ((FAILED++))
    fi
    echo ""
done

echo "======================================================================"
echo "  Workers Started: $STARTED / $((STARTED + FAILED))"
echo "======================================================================"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "Some workers failed. Check:"
    echo "  - SSH connectivity: ssh $SPARK_USER@<worker>"
    echo "  - PySpark installed: pip list | grep pyspark"
    echo "  - NFS mount: ls $PROJECT_ROOT"
    echo ""
fi

echo ""
echo "Check cluster status at: http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
echo ""

#!/bin/bash
#
# Spark Cluster Environment Configuration
#
# This file is sourced by all spark-cluster scripts.
# Edit these values to match your cluster.
#

# =============================================================================
# Cluster Topology
# =============================================================================

# Master node
SPARK_MASTER_HOST="192.168.1.212"
SPARK_MASTER_PORT="7077"
SPARK_MASTER_WEBUI_PORT="8080"

# Worker nodes (space-separated)
SPARK_WORKERS="192.168.1.207 192.168.1.202 192.168.1.203"

# Worker hostnames (for SSH)
SPARK_WORKER_NAMES="bark-1 bark-2 bark-3"

# =============================================================================
# Resource Configuration
# =============================================================================

# Memory per worker (leave some for OS)
SPARK_WORKER_MEMORY="8g"

# Cores per worker (leave 1-2 for OS)
SPARK_WORKER_CORES="10"

# Driver memory for submitted jobs
SPARK_DRIVER_MEMORY="4g"

# Executor memory
SPARK_EXECUTOR_MEMORY="6g"

# =============================================================================
# Paths
# =============================================================================

# User account
SPARK_USER="ms_trixie"

# Python environment with PySpark
# Head node uses conda env, workers use ~/venv
if [ -d "/home/$SPARK_USER/anaconda3/envs/de_funk" ]; then
    VENV_PATH="/home/$SPARK_USER/anaconda3/envs/de_funk"
else
    VENV_PATH="/home/$SPARK_USER/venv"
fi
export PYSPARK_PYTHON="$VENV_PATH/bin/python"
export PYSPARK_DRIVER_PYTHON="$VENV_PATH/bin/python"

# Detect if NFS is mounted, otherwise use local paths
if [ -d "/shared/storage" ]; then
    # Cluster mode with NFS
    SHARED_STORAGE="/shared/storage"
    PROJECT_ROOT="/shared/de_Funk"
else
    # Local development mode
    SHARED_STORAGE="/home/$SPARK_USER/PycharmProjects/de_Funk/storage"
    PROJECT_ROOT="/home/$SPARK_USER/PycharmProjects/de_Funk"
fi

# Log directory
SPARK_LOG_DIR="/tmp/spark-logs"

# Event log directory (for history server)
SPARK_HISTORY_DIR="$SHARED_STORAGE/spark-history"

# PID directory
SPARK_PID_DIR="/tmp/spark-pids"

# =============================================================================
# Derived Settings (don't edit below)
# =============================================================================

# Find SPARK_HOME from PySpark installation
find_spark_home() {
    if [ -n "$SPARK_HOME" ]; then
        echo "$SPARK_HOME"
        return
    fi

    # Try to find it from pyspark
    local pyspark_path
    pyspark_path=$($VENV_PATH/bin/python -c "import pyspark; print(pyspark.__path__[0])" 2>/dev/null)

    if [ -n "$pyspark_path" ]; then
        echo "$pyspark_path"
    else
        echo ""
    fi
}

export SPARK_HOME=$(find_spark_home)
export SPARK_MASTER_URL="spark://$SPARK_MASTER_HOST:$SPARK_MASTER_PORT"

# Java home (should be set from worker setup)
if [ -z "$JAVA_HOME" ]; then
    export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
fi

# Ensure directories exist
mkdir -p "$SPARK_LOG_DIR" "$SPARK_PID_DIR" 2>/dev/null || true

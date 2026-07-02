#!/bin/bash
#
# Spark Cluster - Head Node Setup
#
# Sets up the head node (bigbark) with:
# - Spark Master + local Worker
# - Airflow scheduler + webserver
# - NFS server for shared storage
#
# Usage:
#   ./setup-head.sh
#   ./setup-head.sh --skip-nfs      # Skip NFS setup
#   ./setup-head.sh --skip-airflow  # Skip Airflow setup
#
# Run this ONCE on the head node, then run setup-worker.sh on each worker.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# =============================================================================
# Configuration
# =============================================================================

# Network
HEAD_IP="192.168.1.212"

# User
DE_FUNK_USER="ms_trixie"
VENV_PATH="/home/$DE_FUNK_USER/venv"

# Storage
STORAGE_PATH="/data/de_funk"
NFS_EXPORT_PATH="/shared"

# Spark
SPARK_MASTER_PORT=7077
SPARK_WEBUI_PORT=8080

# Airflow
AIRFLOW_PORT=8081  # Different from Spark UI

# Flags
SKIP_NFS=false
SKIP_AIRFLOW=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-nfs)
            SKIP_NFS=true
            shift
            ;;
        --skip-airflow)
            SKIP_AIRFLOW=true
            shift
            ;;
        --head-ip)
            HEAD_IP="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-nfs       Skip NFS server setup"
            echo "  --skip-airflow   Skip Airflow setup"
            echo "  --head-ip IP     Override head node IP"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

echo "======================================================================"
echo "  Spark Cluster - Head Node Setup"
echo "======================================================================"
echo ""
echo "Head IP: $HEAD_IP"
echo "User: $DE_FUNK_USER"
echo "Storage: $STORAGE_PATH"
echo "Skip NFS: $SKIP_NFS"
echo "Skip Airflow: $SKIP_AIRFLOW"
echo ""

# =============================================================================
# Step 1: System Packages
# =============================================================================

log "Step 1: Installing system packages..."

sudo apt-get update -qq
sudo apt-get install -y -qq \
    openjdk-17-jdk \
    python3-pip \
    python3-venv \
    nfs-kernel-server \
    nfs-common \
    curl \
    wget \
    git

# Set JAVA_HOME
JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
echo "export JAVA_HOME=$JAVA_HOME" >> /home/$DE_FUNK_USER/.bashrc

log "  ✓ System packages installed"
log "  ✓ JAVA_HOME=$JAVA_HOME"

# =============================================================================
# Step 2: Python Environment
# =============================================================================

log "Step 2: Setting up Python environment..."

if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

pip install --upgrade pip setuptools wheel -q
pip install \
    'pyspark==4.0.1' \
    'delta-spark==4.0.0' \
    'deltalake>=0.14.0' \
    pandas \
    numpy \
    pyarrow \
    requests \
    python-dotenv \
    -q

log "  ✓ Python environment ready"

# =============================================================================
# Step 3: NFS Server
# =============================================================================

if [ "$SKIP_NFS" = false ]; then
    log "Step 3: Setting up NFS server..."

    # Create directories
    sudo mkdir -p "$NFS_EXPORT_PATH/storage"
    sudo mkdir -p "$NFS_EXPORT_PATH/de_Funk"
    sudo mkdir -p "$STORAGE_PATH"

    # Link storage
    if [ ! -L "$NFS_EXPORT_PATH/storage" ] || [ "$(readlink -f $NFS_EXPORT_PATH/storage)" != "$STORAGE_PATH" ]; then
        sudo rm -rf "$NFS_EXPORT_PATH/storage"
        sudo ln -s "$STORAGE_PATH" "$NFS_EXPORT_PATH/storage"
    fi

    # Link project
    if [ ! -L "$NFS_EXPORT_PATH/de_Funk" ] || [ "$(readlink -f $NFS_EXPORT_PATH/de_Funk)" != "$PROJECT_ROOT" ]; then
        sudo rm -rf "$NFS_EXPORT_PATH/de_Funk"
        sudo ln -s "$PROJECT_ROOT" "$NFS_EXPORT_PATH/de_Funk"
    fi

    # Set permissions
    sudo chown -R $DE_FUNK_USER:$DE_FUNK_USER "$STORAGE_PATH"
    sudo chmod -R 755 "$NFS_EXPORT_PATH"

    # Configure exports
    EXPORT_LINE="$NFS_EXPORT_PATH 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)"
    if ! grep -q "$NFS_EXPORT_PATH" /etc/exports 2>/dev/null; then
        echo "$EXPORT_LINE" | sudo tee -a /etc/exports
    fi

    # Restart NFS
    sudo exportfs -ra
    sudo systemctl restart nfs-kernel-server

    log "  ✓ NFS server configured"
    log "  ✓ Exports: $NFS_EXPORT_PATH/storage, $NFS_EXPORT_PATH/de_Funk"
else
    log "Step 3: Skipping NFS setup"
fi

# =============================================================================
# Step 4: Spark Configuration
# =============================================================================

log "Step 4: Configuring Spark..."

# Find SPARK_HOME from PySpark
SPARK_HOME=$($VENV_PATH/bin/python -c "import pyspark; print(pyspark.__path__[0])")

# Update spark-env.sh with actual paths
sed -i "s|SPARK_MASTER_HOST=.*|SPARK_MASTER_HOST=\"$HEAD_IP\"|" "$PROJECT_ROOT/scripts/spark-cluster/spark-env.sh"
sed -i "s|VENV_PATH=.*|VENV_PATH=\"$VENV_PATH\"|" "$PROJECT_ROOT/scripts/spark-cluster/spark-env.sh"
sed -i "s|SHARED_STORAGE=.*|SHARED_STORAGE=\"/shared/storage\"|" "$PROJECT_ROOT/scripts/spark-cluster/spark-env.sh"
sed -i "s|PROJECT_ROOT=.*|PROJECT_ROOT=\"/shared/de_Funk\"|" "$PROJECT_ROOT/scripts/spark-cluster/spark-env.sh"

log "  ✓ Spark configuration updated"
log "  ✓ SPARK_HOME=$SPARK_HOME"

# =============================================================================
# Step 5: Airflow
# =============================================================================

if [ "$SKIP_AIRFLOW" = false ]; then
    log "Step 5: Setting up Airflow..."

    # Run Airflow setup script
    bash "$PROJECT_ROOT/orchestration/airflow/setup-airflow.sh" --with-systemd

    log "  ✓ Airflow installed"
else
    log "Step 5: Skipping Airflow setup"
fi

# =============================================================================
# Step 6: Create Storage Directories
# =============================================================================

log "Step 6: Creating storage directories..."

mkdir -p "$STORAGE_PATH/bronze"
mkdir -p "$STORAGE_PATH/silver"
mkdir -p "$STORAGE_PATH/spark-history"
mkdir -p "$STORAGE_PATH/checkpoints"

log "  ✓ Storage directories created"

# =============================================================================
# Step 7: Systemd Services for Spark
# =============================================================================

log "Step 7: Installing Spark systemd services..."

# Spark Master Service
sudo tee /etc/systemd/system/spark-master.service > /dev/null <<EOF
[Unit]
Description=Apache Spark Master
After=network.target

[Service]
Type=simple
User=$DE_FUNK_USER
Environment="JAVA_HOME=$JAVA_HOME"
Environment="SPARK_HOME=$SPARK_HOME"
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin"
ExecStart=/bin/bash -c 'source $VENV_PATH/bin/activate && $PROJECT_ROOT/scripts/spark-cluster/start-master.sh'
ExecStop=/bin/bash -c '$PROJECT_ROOT/scripts/spark-cluster/stop-all.sh --local'
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable spark-master

log "  ✓ Spark Master service installed"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "======================================================================"
echo "  Head Node Setup Complete!"
echo "======================================================================"
echo ""
echo "Services installed:"
echo "  - Spark Master (port $SPARK_MASTER_PORT)"
echo "  - Spark Web UI (port $SPARK_WEBUI_PORT)"
if [ "$SKIP_AIRFLOW" = false ]; then
echo "  - Airflow Web UI (port $AIRFLOW_PORT)"
fi
echo ""
echo "NFS Exports:"
echo "  - /shared/storage -> $STORAGE_PATH"
echo "  - /shared/de_Funk -> $PROJECT_ROOT"
echo ""
echo "Next Steps:"
echo ""
echo "  1. Start Spark Master:"
echo "     sudo systemctl start spark-master"
echo "     # Or: ./scripts/spark-cluster/start-master.sh"
echo ""
echo "  2. Setup workers (run on each worker node):"
echo "     curl -sSL http://$HEAD_IP:8000/setup-worker.sh | bash -s -- --worker-id 0"
echo ""
echo "  3. Start Airflow (if installed):"
echo "     ~/airflow/start-airflow.sh"
echo ""
echo "  4. Check cluster status:"
echo "     ./scripts/spark-cluster/status.sh"
echo ""
echo "Web UIs:"
echo "  Spark:   http://$HEAD_IP:$SPARK_WEBUI_PORT"
if [ "$SKIP_AIRFLOW" = false ]; then
echo "  Airflow: http://$HEAD_IP:$AIRFLOW_PORT"
fi
echo ""

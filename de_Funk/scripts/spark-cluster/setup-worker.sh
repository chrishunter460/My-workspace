#!/bin/bash
#
# Spark Cluster - Worker Node Setup
#
# Sets up a worker node (bark-1, bark-2, bark-3) with:
# - Java + Python environment
# - PySpark (matching head node version)
# - NFS mounts for shared storage
# - Spark Worker service
#
# Usage (from worker machine):
#   curl -sSL http://192.168.1.212:8000/setup-worker.sh | bash -s -- --worker-id 0
#
# Or locally:
#   ./setup-worker.sh --worker-id 0
#
# Options:
#   --worker-id N     Worker index (0, 1, 2)
#   --head-ip IP      Override head node IP
#   --skip-nfs        Skip NFS mount setup
#

set -e

# =============================================================================
# Configuration
# =============================================================================

HEAD_IP="192.168.1.212"
HEAD_PORT="7077"

# Workers: IP:CORES:MEMORY_GB
WORKERS=(
    "192.168.1.207:10:8"   # bark-1
    "192.168.1.202:10:8"   # bark-2
    "192.168.1.203:10:8"   # bark-3
)

WORKER_NAMES=(
    "bark-1"
    "bark-2"
    "bark-3"
)

DE_FUNK_USER="ms_trixie"
VENV_PATH="/home/$DE_FUNK_USER/venv"
NFS_MOUNT="/shared"

# Flags
WORKER_ID=""
SKIP_NFS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --worker-id)
            WORKER_ID="$2"
            shift 2
            ;;
        --head-ip)
            HEAD_IP="$2"
            shift 2
            ;;
        --skip-nfs)
            SKIP_NFS=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 --worker-id N [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --worker-id N    Worker index (0, 1, 2)"
            echo "  --head-ip IP     Head node IP (default: 192.168.1.212)"
            echo "  --skip-nfs       Skip NFS mount"
            echo ""
            echo "Workers:"
            for i in "${!WORKERS[@]}"; do
                IFS=':' read -r ip cores mem <<< "${WORKERS[$i]}"
                echo "  $i: ${WORKER_NAMES[$i]} ($ip) - $cores cores, ${mem}GB RAM"
            done
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$WORKER_ID" ]; then
    echo "ERROR: --worker-id is required"
    echo "Usage: $0 --worker-id N"
    exit 1
fi

# Get worker config
IFS=':' read -r WORKER_IP WORKER_CORES WORKER_MEM <<< "${WORKERS[$WORKER_ID]}"
HOSTNAME="${WORKER_NAMES[$WORKER_ID]}"

if [ -z "$WORKER_IP" ]; then
    echo "ERROR: Invalid worker-id: $WORKER_ID"
    exit 1
fi

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

echo "======================================================================"
echo "  Spark Cluster - Worker Setup: $HOSTNAME"
echo "======================================================================"
echo ""
echo "Worker: $HOSTNAME ($WORKER_IP)"
echo "Resources: $WORKER_CORES cores, ${WORKER_MEM}GB RAM"
echo "Head Node: $HEAD_IP:$HEAD_PORT"
echo ""

# =============================================================================
# Step 1: Set Hostname
# =============================================================================

log "Step 1: Setting hostname..."

sudo hostnamectl set-hostname "$HOSTNAME"

# Add to /etc/hosts if not present
if ! grep -q "$HOSTNAME" /etc/hosts; then
    echo "127.0.0.1 $HOSTNAME" | sudo tee -a /etc/hosts
fi

log "  ✓ Hostname set to $HOSTNAME"

# =============================================================================
# Step 2: System Packages
# =============================================================================

log "Step 2: Installing system packages..."

sudo apt-get update -qq
sudo apt-get install -y -qq \
    openjdk-17-jdk \
    python3-pip \
    python3-venv \
    nfs-common \
    curl

# Set JAVA_HOME
JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
echo "export JAVA_HOME=$JAVA_HOME" >> /home/$DE_FUNK_USER/.bashrc

log "  ✓ System packages installed"
log "  ✓ JAVA_HOME=$JAVA_HOME"

# =============================================================================
# Step 3: NFS Mounts
# =============================================================================

if [ "$SKIP_NFS" = false ]; then
    log "Step 3: Mounting NFS shares..."

    sudo mkdir -p "$NFS_MOUNT/storage"
    sudo mkdir -p "$NFS_MOUNT/de_Funk"

    # Mount storage
    if ! mountpoint -q "$NFS_MOUNT/storage"; then
        sudo mount -t nfs "$HEAD_IP:/shared/storage" "$NFS_MOUNT/storage"
    fi

    # Mount project
    if ! mountpoint -q "$NFS_MOUNT/de_Funk"; then
        sudo mount -t nfs "$HEAD_IP:/shared/de_Funk" "$NFS_MOUNT/de_Funk"
    fi

    # Add to fstab for persistence
    if ! grep -q "$NFS_MOUNT/storage" /etc/fstab; then
        echo "$HEAD_IP:/shared/storage $NFS_MOUNT/storage nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab
        echo "$HEAD_IP:/shared/de_Funk $NFS_MOUNT/de_Funk nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab
    fi

    log "  ✓ NFS shares mounted"
else
    log "Step 3: Skipping NFS setup"
fi

# =============================================================================
# Step 4: Python Environment
# =============================================================================

log "Step 4: Setting up Python environment..."

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
    -q

log "  ✓ Python environment ready"

# =============================================================================
# Step 5: Spark Worker Service
# =============================================================================

log "Step 5: Installing Spark Worker service..."

# Use NFS-mounted Spark distribution (has full jars and build info for executor spawning)
SPARK_HOME="/shared/spark"

# Verify Spark is accessible via NFS
if [ ! -d "$SPARK_HOME/jars" ]; then
    log "  ERROR: Spark not found at $SPARK_HOME"
    log "  Make sure NFS is mounted and head node has Spark distribution"
    exit 1
fi

sudo tee /etc/systemd/system/spark-worker.service > /dev/null <<EOF
[Unit]
Description=Apache Spark Worker
After=network.target

[Service]
Type=simple
User=$DE_FUNK_USER
WorkingDirectory=/home/$DE_FUNK_USER
Environment="JAVA_HOME=$JAVA_HOME"
Environment="SPARK_HOME=$SPARK_HOME"
Environment="SPARK_SCALA_VERSION=2.13"
Environment="PYSPARK_PYTHON=$VENV_PATH/bin/python3"
Environment="PATH=$VENV_PATH/bin:/usr/local/bin:/usr/bin"
ExecStart=$JAVA_HOME/bin/java -cp "$SPARK_HOME/jars/*" -Xmx${WORKER_MEM}g org.apache.spark.deploy.worker.Worker --cores $WORKER_CORES --memory ${WORKER_MEM}g spark://$HEAD_IP:$HEAD_PORT
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable spark-worker
sudo systemctl start spark-worker

log "  ✓ Spark Worker service installed and started"

# =============================================================================
# Verify
# =============================================================================

log "Verifying Spark Worker..."

sleep 3

if systemctl is-active --quiet spark-worker; then
    log "  ✓ Spark Worker is running"
else
    log "  ✗ Spark Worker failed to start"
    journalctl -u spark-worker -n 20 --no-pager
    exit 1
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "======================================================================"
echo "  Worker Setup Complete: $HOSTNAME"
echo "======================================================================"
echo ""
echo "Worker: $HOSTNAME ($WORKER_IP)"
echo "Resources: $WORKER_CORES cores, ${WORKER_MEM}GB RAM"
echo "Master: spark://$HEAD_IP:$HEAD_PORT"
echo ""
echo "NFS Mounts:"
echo "  $NFS_MOUNT/storage -> shared storage"
echo "  $NFS_MOUNT/de_Funk -> project code"
echo ""
echo "Check status:"
echo "  systemctl status spark-worker"
echo "  curl http://$HEAD_IP:8080/json/"
echo ""
echo "View on Master UI: http://$HEAD_IP:8080"
echo ""

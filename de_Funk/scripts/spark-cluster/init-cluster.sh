#!/bin/bash
#
# Spark + Airflow Cluster - Full Setup
#
# Sequential setup with connection validation. Run from head node.
# Reads configuration from configs/cluster.yaml
#
# Usage:
#   ./init-cluster.sh
#

set -e

# =============================================================================
# Configuration - Read from cluster.yaml
# =============================================================================

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
SPARK_MASTER_PORT=$(read_config "print(cfg['spark']['master']['port'])")
SPARK_UI_PORT=$(read_config "print(cfg['spark']['master']['ui_port'])")
AIRFLOW_PORT=$(read_config "print(cfg['airflow']['port'])")

# Build workers array from config: "name:ip:cores:memory"
WORKERS=()
while IFS= read -r line; do
    WORKERS+=("$line")
done < <(read_config "
for w in cfg['cluster']['workers']:
    print(f\"{w['name']}:{w['ip']}:{w['cores']}:{w['memory_gb']}\")
")

# Derived paths
SPARK_VENV="/home/$DE_FUNK_USER/venv"
AIRFLOW_VENV="/home/$DE_FUNK_USER/airflow-venv"
LOCAL_PROJECT="/home/$DE_FUNK_USER/PycharmProjects/de_Funk"
LOCAL_STORAGE="/data/de_funk"
NFS_ROOT="/shared"

echo "Loaded configuration from: $CONFIG_FILE"
echo "  Head: $HEAD_IP (user: $DE_FUNK_USER)"
echo "  Workers: ${#WORKERS[@]}"
echo "  Spark Master: port $SPARK_MASTER_PORT, UI port $SPARK_UI_PORT"
echo "  Airflow: port $AIRFLOW_PORT"

# =============================================================================
# Helpers
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }
fail() { echo -e "${RED}[$(date '+%H:%M:%S')] FAIL:${NC} $1"; exit 1; }

section() {
    echo ""
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
    echo ""
}

# =============================================================================
# Step 0: Validate Connections & Setup Sudo
# =============================================================================

section "Step 0: Validating Connections & Sudo Access"

log "Checking head node..."
if [[ "$(hostname -I)" != *"$HEAD_IP"* ]]; then
    fail "This script must run on head node ($HEAD_IP)"
fi
log "  ✓ Running on head node"

# Cache sudo credentials locally
log "Caching sudo credentials (enter password once)..."
sudo -v || fail "Sudo access required"

# Keep sudo alive in background
(while true; do sudo -n true; sleep 50; done) &
SUDO_KEEPER=$!
trap "kill $SUDO_KEEPER 2>/dev/null" EXIT

log "  ✓ Local sudo cached"

# Check workers and setup passwordless sudo if needed
for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    log "Checking $name ($ip)..."

    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "echo ok" &>/dev/null; then
        fail "$name ($ip) not reachable via SSH. Check SSH keys."
    fi
    log "  ✓ $name SSH ok"

    # Check if passwordless sudo works
    if ! ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "sudo -n true" &>/dev/null; then
        log "  Setting up passwordless sudo on $name..."
        # Use ssh -t for interactive sudo, then set up NOPASSWD
        ssh -t "$DE_FUNK_USER@$ip" "echo '$DE_FUNK_USER ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/$DE_FUNK_USER > /dev/null"
        log "  ✓ $name passwordless sudo configured"
    else
        log "  ✓ $name sudo ok"
    fi
done

log "All nodes ready!"

# =============================================================================
# Step 1: Cleanup Everything
# =============================================================================

section "Step 1: Cleanup Existing Processes"

log "Stopping local Spark..."
pkill -9 -f "org.apache.spark.deploy" 2>/dev/null || true
rm -f /tmp/spark-*.pid 2>/dev/null || true

log "Stopping local Airflow..."
pkill -9 -f "airflow" 2>/dev/null || true
rm -f ~/airflow/*.pid 2>/dev/null || true

log "  ✓ Local processes stopped (workers will be restarted in Step 6)"

# =============================================================================
# Step 2: Setup NFS on Head
# =============================================================================

section "Step 2: NFS Setup (Head Node)"

# Check if NFS is already properly set up and working
if mountpoint -q "$NFS_ROOT/storage" 2>/dev/null && [ -d "$NFS_ROOT/storage/bronze" ]; then
    log "NFS already configured at $NFS_ROOT - skipping setup"
else
    # Only clean up mounts if they exist but aren't working
    log "Setting up NFS mounts..."

    # Check if storage directories exist (from previous setup)
    if [ -d "$LOCAL_STORAGE/bronze" ] && [ -d "$LOCAL_STORAGE/silver" ]; then
        log "Storage directories exist at $LOCAL_STORAGE - quick setup"
    else
        log "Installing NFS server..."
        sudo apt-get update
        sudo apt-get install -y nfs-kernel-server nfs-common

        log "Creating directories..."
        sudo mkdir -p "$NFS_ROOT/storage" "$NFS_ROOT/de_Funk" "$NFS_ROOT/spark"
        sudo mkdir -p "$LOCAL_STORAGE"/{bronze,silver,logs,checkpoints}
        sudo chown -R $DE_FUNK_USER:$DE_FUNK_USER "$LOCAL_STORAGE"
    fi

    log "Setting up bind mounts..."
    sudo mkdir -p "$NFS_ROOT/storage" "$NFS_ROOT/de_Funk" "$NFS_ROOT/spark"
    # Only mount if not already mounted
    mountpoint -q "$NFS_ROOT/storage" || sudo mount --bind "$LOCAL_STORAGE" "$NFS_ROOT/storage"
    mountpoint -q "$NFS_ROOT/de_Funk" || sudo mount --bind "$LOCAL_PROJECT" "$NFS_ROOT/de_Funk"

    log "Configuring NFS exports..."
    sudo tee /etc/exports > /dev/null <<EOF
$NFS_ROOT 192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash,crossmnt)
EOF

    sudo exportfs -ra
    sudo systemctl restart nfs-kernel-server
fi

# Ensure firewall allows NFS ports
if command -v ufw &> /dev/null && sudo ufw status | grep -q "Status: active"; then
    log "Configuring firewall for NFS..."
    sudo ufw allow from 192.168.1.0/24 to any port 111 > /dev/null 2>&1 || true    # rpcbind
    sudo ufw allow from 192.168.1.0/24 to any port 2049 > /dev/null 2>&1 || true   # nfs
    sudo ufw allow from 192.168.1.0/24 to any port 20048 > /dev/null 2>&1 || true  # mountd
    log "  ✓ Firewall configured for NFS"
fi

log "  ✓ NFS ready: $NFS_ROOT"

# =============================================================================
# Step 3: Setup Python on Head
# =============================================================================

section "Step 3: Python Environment (Head Node)"

log "Setting up Spark venv..."
if [ ! -d "$SPARK_VENV" ]; then
    python3 -m venv "$SPARK_VENV"
fi

source "$SPARK_VENV/bin/activate"
pip install -q --upgrade pip

# Core data processing
pip install -q 'pyspark==4.0.1' 'delta-spark==4.0.0' 'deltalake>=0.14.0' pandas numpy pyarrow requests python-dotenv networkx

# Machine learning libraries
pip install -q scikit-learn statsmodels pmdarima prophet xgboost lightgbm

# Deep learning (CPU versions for compatibility - use GPU versions if needed)
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -q tensorflow

JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
SPARK_HOME=$(python -c "import pyspark; print(pyspark.__path__[0])")

log "  ✓ JAVA_HOME: $JAVA_HOME"
log "  ✓ SPARK_HOME: $SPARK_HOME"

# Download and setup Spark distribution for workers
# IMPORTANT: Must include full distribution with sbin/ scripts for workers
SPARK_VERSION="4.0.1"
SPARK_DIST_NAME="spark-${SPARK_VERSION}-bin-hadoop3"
SPARK_DIST_DIR="/home/$DE_FUNK_USER"
SPARK_TGZ="${SPARK_DIST_NAME}.tgz"
SPARK_URL="https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/${SPARK_TGZ}"

log "Setting up Spark distribution for workers..."
if [ ! -d "$SPARK_DIST_DIR/$SPARK_DIST_NAME" ]; then
    log "  Downloading Spark ${SPARK_VERSION}..."
    cd "$SPARK_DIST_DIR"
    if [ ! -f "$SPARK_TGZ" ]; then
        wget -q "$SPARK_URL" || curl -sLO "$SPARK_URL"
    fi
    tar xzf "$SPARK_TGZ"
    rm -f "$SPARK_TGZ"
    cd "$REPO_ROOT"
    log "  ✓ Spark distribution extracted"
else
    log "  ✓ Spark distribution already exists"
fi

# Verify sbin scripts exist
if [ ! -f "$SPARK_DIST_DIR/$SPARK_DIST_NAME/sbin/start-worker.sh" ]; then
    fail "Spark distribution missing sbin scripts! Remove $SPARK_DIST_DIR/$SPARK_DIST_NAME and re-run."
fi
log "  ✓ Spark sbin scripts verified"

# Copy Spark distribution to NFS share (bind mounts don't work across NFS!)
# NFS clients see the underlying directory, not bind-mounted content
sudo mkdir -p "$NFS_ROOT/spark"

# Check if Spark is already properly copied (not just an empty dir or stale bind mount)
if [ -f "$NFS_ROOT/spark/sbin/start-worker.sh" ] && [ -d "$NFS_ROOT/spark/jars" ]; then
    # Verify it's not a stale bind mount by checking file count
    JAR_COUNT=$(ls "$NFS_ROOT/spark/jars/"*.jar 2>/dev/null | wc -l)
    if [ "$JAR_COUNT" -gt 10 ]; then
        log "  ✓ Spark already available at $NFS_ROOT/spark ($JAR_COUNT jars)"
    else
        log "  Spark directory exists but appears incomplete, re-copying..."
        sudo rm -rf "$NFS_ROOT/spark"/*
        sudo cp -r "$SPARK_DIST_DIR/$SPARK_DIST_NAME"/* "$NFS_ROOT/spark/"
        sudo chown -R $DE_FUNK_USER:$DE_FUNK_USER "$NFS_ROOT/spark"
        log "  ✓ Spark copied to NFS share"
    fi
else
    log "  Copying Spark distribution to NFS share..."
    # Remove any stale bind mount first
    sudo umount "$NFS_ROOT/spark" 2>/dev/null || true
    sudo rm -rf "$NFS_ROOT/spark"/*
    sudo cp -r "$SPARK_DIST_DIR/$SPARK_DIST_NAME"/* "$NFS_ROOT/spark/"
    sudo chown -R $DE_FUNK_USER:$DE_FUNK_USER "$NFS_ROOT/spark"
    log "  ✓ Spark copied to NFS share"
fi

# Final verification
if [ ! -f "$NFS_ROOT/spark/sbin/start-worker.sh" ]; then
    fail "Spark distribution not available at $NFS_ROOT/spark"
fi

# =============================================================================
# Step 4: Setup Each Worker (Sequential)
# =============================================================================

section "Step 4: Worker Setup"

worker_idx=0
for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"

    log "Setting up $name ($ip) - $cores cores, ${mem}GB RAM..."

    if ! ssh -o ConnectTimeout=30 "$DE_FUNK_USER@$ip" bash -s "$HEAD_IP" "$NFS_ROOT" "$name" <<WORKER_SCRIPT
set -e

echo "  Installing packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq openjdk-17-jdk python3-pip python3-venv nfs-common

echo "  Mounting NFS..."
sudo mkdir -p /shared

# Always force remount to clear NFS cache (critical for seeing updated Spark files)
echo "  Remounting NFS to clear cache..."
sudo umount -l /shared 2>/dev/null || true
sleep 1
sudo mount -t nfs -o vers=4,noac $HEAD_IP:$NFS_ROOT /shared

# Verify Spark jars are accessible (not just the directory)
if ls /shared/spark/jars/*.jar >/dev/null 2>&1; then
    JAR_COUNT=\$(ls /shared/spark/jars/*.jar | wc -l)
    echo "  NFS mounted - Spark jars accessible (\$JAR_COUNT jars)"
else
    echo "  ERROR: /shared/spark/jars not accessible after mount!"
    echo "  Contents of /shared/spark:"
    ls -la /shared/spark/ 2>&1 || echo "  (directory not found)"
    exit 1
fi
ls /shared/

# Persist mount (with noac to prevent attribute caching issues)
grep -q "/shared" /etc/fstab || echo "$HEAD_IP:$NFS_ROOT /shared nfs defaults,noac,_netdev 0 0" | sudo tee -a /etc/fstab

echo "  Setting up Python (conda de_funk env)..."
# Install miniconda if not present
if [ ! -d ~/anaconda3 ] && [ ! -d ~/miniconda3 ]; then
    echo "  Installing Miniconda..."
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p ~/miniconda3
    rm /tmp/miniconda.sh
    export PATH=~/miniconda3/bin:\$PATH
fi

# Set conda path
if [ -d ~/anaconda3 ]; then
    CONDA_PATH=~/anaconda3
elif [ -d ~/miniconda3 ]; then
    CONDA_PATH=~/miniconda3
fi

# Create de_funk env if not present
if [ ! -d \$CONDA_PATH/envs/de_funk ]; then
    echo "  Creating de_funk conda env..."
    \$CONDA_PATH/bin/conda create -n de_funk python=3.12 pip setuptools wheel -y -q
fi

# Install packages
echo "  Installing packages..."
\$CONDA_PATH/envs/de_funk/bin/python -m pip install -q \
    'pyspark==4.0.1' 'delta-spark==4.0.0' pandas numpy pyarrow networkx \
    scikit-learn statsmodels

JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
SPARK_HOME=\$(\$CONDA_PATH/envs/de_funk/bin/python -c "import pyspark; print(pyspark.__path__[0])")
echo "  JAVA_HOME=\$JAVA_HOME"
echo "  SPARK_HOME=\$SPARK_HOME"

echo "  Creating systemd service..."
# Create a wrapper script that uses official start-worker.sh
# Uses shared Spark distribution from NFS at /shared/spark
# IMPORTANT: Explicitly set SPARK_LOCAL_IP to LAN IP to avoid Tailscale interference
cat > ~/start-spark-worker.sh << STARTWRAPPER
#!/bin/bash
export SPARK_HOME=/shared/spark
export JAVA_HOME=\\\$(dirname \\\$(dirname \\\$(readlink -f \\\$(which java))))
export SPARK_SCALA_VERSION=2.13
export PYSPARK_PYTHON=\\\$(ls ~/anaconda3/envs/de_funk/bin/python ~/miniconda3/envs/de_funk/bin/python 2>/dev/null | head -1)

# Get LAN IP (route to master) - avoids Tailscale/VPN IPs
SPARK_LOCAL_IP=\\\$(ip route get $HEAD_IP | grep -oP 'src \K[0-9.]+')
export SPARK_LOCAL_IP

# Run worker directly (not via start-worker.sh which daemonizes)
# This keeps it in foreground for systemd Type=simple
# Note: Java classpath wildcard must NOT be quoted and must NOT have .jar extension
exec \\\$JAVA_HOME/bin/java -cp \\\$SPARK_HOME/jars/'*' -Xmx${mem}g -Dspark.worker.host=\\\$SPARK_LOCAL_IP org.apache.spark.deploy.worker.Worker --host \\\$SPARK_LOCAL_IP --cores $cores --memory ${mem}g spark://$HEAD_IP:$SPARK_MASTER_PORT
STARTWRAPPER
chmod +x ~/start-spark-worker.sh

# Systemd service with environment variables for executor spawning
printf '%s\n' \
    "[Unit]" \
    "Description=Apache Spark Worker" \
    "After=network.target" \
    "" \
    "[Service]" \
    "Type=simple" \
    "User=\$(whoami)" \
    "WorkingDirectory=/home/\$(whoami)" \
    "Environment=SPARK_HOME=/shared/spark" \
    "Environment=SPARK_SCALA_VERSION=2.13" \
    "Environment=JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))" \
    "Environment=PYSPARK_PYTHON=/home/\$(whoami)/\$(ls -d anaconda3 miniconda3 2>/dev/null | head -1)/envs/de_funk/bin/python" \
    "ExecStart=/home/\$(whoami)/start-spark-worker.sh" \
    "Restart=on-failure" \
    "RestartSec=5" \
    "" \
    "[Install]" \
    "WantedBy=multi-user.target" \
    | sudo tee /etc/systemd/system/spark-worker.service

sudo systemctl daemon-reload
sudo systemctl enable spark-worker

echo "  ✓ $name configured"
WORKER_SCRIPT
    then
        warn "Failed to setup $name - continuing with next worker"
    else
        log "  ✓ $name ready"
    fi
    ((worker_idx++)) || true  # Prevent set -e exit when idx was 0
done

# =============================================================================
# Step 5: Start Spark Master
# =============================================================================

section "Step 5: Start Spark Master"

# Ensure firewall allows Spark Master port from workers
if command -v ufw &> /dev/null && sudo ufw status | grep -q "Status: active"; then
    if ! sudo ufw status | grep -q "7077.*ALLOW.*192.168.1.0/24"; then
        log "Adding firewall rule for Spark Master port 7077..."
        sudo ufw allow from 192.168.1.0/24 to any port 7077 > /dev/null
        log "  ✓ Firewall rule added"
    fi
fi

log "Starting Spark Master..."

source "$SPARK_VENV/bin/activate"
JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
# Use standalone Spark distribution (has sbin scripts)
SPARK_HOME="$HOME/spark-4.0.1-bin-hadoop3"
if [ ! -d "$SPARK_HOME" ]; then
    SPARK_HOME="$NFS_ROOT/spark"
fi

export JAVA_HOME SPARK_HOME
# IMPORTANT: Set SPARK_LOCAL_IP to LAN IP to avoid Tailscale/VPN interference
export SPARK_LOCAL_IP=$HEAD_IP
export SPARK_MASTER_HOST=$HEAD_IP
export SPARK_MASTER_PORT=$SPARK_MASTER_PORT
export SPARK_MASTER_WEBUI_PORT=$SPARK_UI_PORT

mkdir -p "$LOCAL_STORAGE/logs"

# Use official start-master.sh for proper initialization
# The -h flag explicitly binds to LAN IP
"$SPARK_HOME/sbin/start-master.sh" -h $HEAD_IP

sleep 5

if curl -s "http://$HEAD_IP:$SPARK_UI_PORT" > /dev/null; then
    log "  ✓ Spark Master running at spark://$HEAD_IP:$SPARK_MASTER_PORT"
    log "  ✓ Web UI: http://$HEAD_IP:$SPARK_UI_PORT"
else
    fail "Spark Master failed to start. Check: $LOCAL_STORAGE/logs/spark-master.out"
fi

# Start History Server for viewing completed job logs
log "Starting Spark History Server..."
mkdir -p "$LOCAL_STORAGE/spark-events"

# Kill existing history server if running
pkill -f "org.apache.spark.deploy.history.HistoryServer" 2>/dev/null || true
sleep 1

nohup "$JAVA_HOME/bin/java" \
    -cp "$SPARK_HOME/jars/*" \
    -Xmx512m \
    -Dspark.history.fs.logDirectory="$LOCAL_STORAGE/spark-events" \
    -Dspark.history.ui.port=18080 \
    org.apache.spark.deploy.history.HistoryServer \
    > "$LOCAL_STORAGE/logs/spark-history.out" 2>&1 &

echo $! > "$LOCAL_STORAGE/logs/spark-history.pid"
sleep 2

if curl -s "http://$HEAD_IP:18080" > /dev/null; then
    log "  ✓ History Server: http://$HEAD_IP:18080"
else
    warn "History Server may not have started. Check: $LOCAL_STORAGE/logs/spark-history.out"
fi

# =============================================================================
# Step 6: Start Workers
# =============================================================================

section "Step 6: Start Spark Workers"

# Start local worker on head node first
# IMPORTANT: Set SPARK_LOCAL_IP to LAN IP to avoid Tailscale/VPN interference
log "Starting local worker on head node..."
export SPARK_LOCAL_IP=$HEAD_IP
"$SPARK_HOME/sbin/start-worker.sh" "spark://$HEAD_IP:$SPARK_MASTER_PORT" -h $HEAD_IP
sleep 2

# Start remote workers via systemd with diagnostics
for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    log "Starting worker on $name..."

    # First verify NFS is mounted and Spark is accessible
    if ! ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "ls /shared/spark/jars/*.jar >/dev/null 2>&1"; then
        warn "$name: NFS/Spark not accessible, attempting repair..."

        # Remount NFS
        ssh "$DE_FUNK_USER@$ip" "sudo umount -l /shared 2>/dev/null; sudo mount -t nfs -o vers=4,noac $HEAD_IP:$NFS_ROOT /shared" || true
        sleep 2

        # Verify again
        if ! ssh "$DE_FUNK_USER@$ip" "ls /shared/spark/jars/*.jar >/dev/null 2>&1"; then
            warn "$name: NFS repair failed - skipping this worker"
            continue
        fi
        log "  ✓ $name NFS repaired"
    fi

    # Check if systemd service exists
    if ! ssh "$DE_FUNK_USER@$ip" "systemctl list-unit-files | grep -q spark-worker"; then
        warn "$name: spark-worker service not found, re-running setup..."
        # Re-run worker setup for this node
        ssh "$DE_FUNK_USER@$ip" bash -s "$HEAD_IP" "$cores" "$mem" <<'REPAIR_SCRIPT'
HEAD_IP=$1
CORES=$2
MEM=$3

# Create wrapper script
cat > ~/start-spark-worker.sh << WRAPPER
#!/bin/bash
export SPARK_HOME=/shared/spark
export JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))
export SPARK_SCALA_VERSION=2.13
export PYSPARK_PYTHON=\\\$(ls ~/anaconda3/envs/de_funk/bin/python ~/miniconda3/envs/de_funk/bin/python 2>/dev/null | head -1)
SPARK_LOCAL_IP=\$(ip route get $HEAD_IP | grep -oP 'src \K[0-9.]+')
export SPARK_LOCAL_IP
exec \$JAVA_HOME/bin/java -cp \$SPARK_HOME/jars/'*' -Xmx${MEM}g -Dspark.worker.host=\$SPARK_LOCAL_IP org.apache.spark.deploy.worker.Worker --host \$SPARK_LOCAL_IP --cores $CORES --memory ${MEM}g spark://$HEAD_IP:7077
WRAPPER
chmod +x ~/start-spark-worker.sh

# Create systemd service
cat << SERVICE | sudo tee /etc/systemd/system/spark-worker.service
[Unit]
Description=Apache Spark Worker
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=/home/$(whoami)
Environment=SPARK_HOME=/shared/spark
Environment=SPARK_SCALA_VERSION=2.13
ExecStart=/home/$(whoami)/start-spark-worker.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable spark-worker
REPAIR_SCRIPT
        log "  ✓ $name service created"
    fi

    # Start the service
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "sudo -n systemctl restart spark-worker"; then
        log "  ✓ $name started"
    else
        warn "$name: Failed to start, checking logs..."
        ssh "$DE_FUNK_USER@$ip" "sudo journalctl -u spark-worker -n 10 --no-pager" 2>/dev/null || true
    fi
done

sleep 5

# Verify workers connected
log "Verifying workers..."
WORKER_COUNT=$(curl -s "http://$HEAD_IP:$SPARK_UI_PORT/json/" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('workers',[])))" 2>/dev/null || echo "0")

# Expected count is workers array + 1 for head node local worker
EXPECTED_COUNT=$((${#WORKERS[@]} + 1))
log "  ✓ $WORKER_COUNT workers connected (expected $EXPECTED_COUNT)"

if [ "$WORKER_COUNT" -lt "$EXPECTED_COUNT" ]; then
    warn "Some workers missing. Troubleshoot with:"
    echo "  ssh <worker> 'sudo journalctl -u spark-worker -f'"
    echo "  ssh <worker> 'ls -la /shared/spark/jars/ | head'"
fi

# =============================================================================
# Step 7: Start Airflow (if configured)
# =============================================================================

section "Step 7: Start Airflow"

if [ -d "$AIRFLOW_VENV" ]; then
    source "$AIRFLOW_VENV/bin/activate"
    export AIRFLOW_HOME="/home/$DE_FUNK_USER/airflow"

    log "Starting Airflow scheduler..."
    nohup airflow scheduler > "$AIRFLOW_HOME/logs/scheduler.log" 2>&1 &
    echo $! > "$AIRFLOW_HOME/scheduler.pid"

    # Airflow 3.x uses api-server instead of webserver
    log "Starting Airflow API server..."
    nohup airflow api-server --port $AIRFLOW_PORT > "$AIRFLOW_HOME/logs/apiserver.log" 2>&1 &
    echo $! > "$AIRFLOW_HOME/apiserver.pid"

    sleep 5
    log "  ✓ Airflow running at http://$HEAD_IP:$AIRFLOW_PORT"
    log "  ✓ Check password: cat $AIRFLOW_HOME/simple_auth_manager_passwords.json.generated"
else
    warn "Airflow not installed. Run: ./orchestration/airflow/setup-airflow.sh"
fi

# =============================================================================
# Step 8: Start Cluster Monitoring Dashboard
# =============================================================================

section "Step 8: Start Cluster Monitoring"

MONITOR_PORT=8082
MONITOR_SCRIPT="$SCRIPT_DIR/monitoring/dashboard_server.py"

if [ -f "$MONITOR_SCRIPT" ]; then
    log "Starting Cluster Monitoring Dashboard..."

    # Kill existing monitor if running
    pkill -f "dashboard_server.py" 2>/dev/null || true

    # Start the monitor
    source "$SPARK_VENV/bin/activate"
    cd "$SCRIPT_DIR/monitoring"
    nohup python3 dashboard_server.py --port $MONITOR_PORT > "$LOCAL_STORAGE/logs/cluster-monitor.out" 2>&1 &
    echo $! > "$LOCAL_STORAGE/logs/cluster-monitor.pid"
    cd "$REPO_ROOT"

    sleep 2

    if curl -s "http://$HEAD_IP:$MONITOR_PORT" > /dev/null; then
        log "  ✓ Monitoring Dashboard: http://$HEAD_IP:$MONITOR_PORT"
    else
        warn "Monitoring dashboard may not have started. Check: $LOCAL_STORAGE/logs/cluster-monitor.out"
    fi
else
    warn "Monitoring script not found: $MONITOR_SCRIPT"
fi

# =============================================================================
# Summary
# =============================================================================

section "Cluster Ready!"

echo "Services:"
echo "  Spark Master:  spark://$HEAD_IP:$SPARK_MASTER_PORT"
echo "  Spark UI:      http://$HEAD_IP:$SPARK_UI_PORT"
echo "  History Server: http://$HEAD_IP:18080"
echo "  Monitoring:    http://$HEAD_IP:$MONITOR_PORT"
if [ -d "$AIRFLOW_VENV" ]; then
echo "  Airflow UI:    http://$HEAD_IP:$AIRFLOW_PORT"
fi
echo ""
echo "Workers: $WORKER_COUNT connected"
for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip cores mem <<< "$w"
    echo "  - $name ($ip): $cores cores, ${mem}GB"
done
echo ""
echo "Storage:"
echo "  Local:  $LOCAL_STORAGE"
echo "  NFS:    $NFS_ROOT -> /shared on workers"
echo ""
echo "Commands:"
echo "  Status:  curl -s http://$HEAD_IP:$SPARK_UI_PORT/json/ | python3 -m json.tool"
echo "  Monitor: http://$HEAD_IP:$MONITOR_PORT"
echo "  Stop:    ./scripts/cluster/stop-cluster.sh"
echo "  Submit:  ./scripts/spark-cluster/submit-job.sh <script.py>"
echo ""

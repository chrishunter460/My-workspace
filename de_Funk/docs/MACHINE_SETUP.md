# de_Funk Machine Setup Guide

**Last Updated**: 2025-12-17

This guide covers setting up a new Linux machine to run de_Funk for development or distributed processing.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Step 1: System Packages](#step-1-system-packages)
4. [Step 2: Java (for Spark)](#step-2-java-for-spark)
5. [Step 3: Python Environment](#step-3-python-environment)
6. [Step 4: Apache Spark](#step-4-apache-spark)
7. [Step 5: Clone Repository](#step-5-clone-repository)
8. [Step 6: Python Dependencies](#step-6-python-dependencies)
9. [Step 7: Environment Configuration](#step-7-environment-configuration)
10. [Step 8: Validation](#step-8-validation)
11. [Step 9: Connect to Central Machine](#step-9-connect-to-central-machine)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Linux (Ubuntu 22.04+ recommended, also works on Debian, RHEL, Fedora)
- sudo access
- Internet connection
- 8GB+ RAM (16GB recommended for Spark)
- 50GB+ disk space

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16+ GB |
| CPU | 4 cores | 8+ cores |
| Disk | 50 GB | 200+ GB (for data) |
| Python | 3.10+ | 3.11+ |
| Java | 11 | 17 (LTS) |
| Spark | 4.0+ | 4.0.1 |

---

## Step 1: System Packages

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential build tools
sudo apt install -y \
    build-essential \
    curl \
    wget \
    git \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates

# Install additional utilities
sudo apt install -y \
    htop \
    tree \
    jq \
    vim \
    tmux
```

### Validation
```bash
git --version
curl --version
```

---

## Step 2: Java (for Spark)

Spark 4.x requires Java 17.

```bash
# Install OpenJDK 17
sudo apt install -y openjdk-17-jdk openjdk-17-jre

# Set JAVA_HOME
echo 'export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64' >> ~/.bashrc
echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Validation
```bash
java -version
# Should show: openjdk version "17.x.x"

echo $JAVA_HOME
# Should show: /usr/lib/jvm/java-17-openjdk-amd64
```

---

## Step 3: Python Environment

### Option A: System Python (Simple)

```bash
# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Create alias (optional)
echo 'alias python=python3.11' >> ~/.bashrc
echo 'alias pip="python3.11 -m pip"' >> ~/.bashrc
source ~/.bashrc
```

### Option B: Miniconda (Recommended for isolation)

```bash
# Download Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# Install
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3

# Initialize
~/miniconda3/bin/conda init bash
source ~/.bashrc

# Create de_funk environment
conda create -n de_funk python=3.11 -y
conda activate de_funk
```

### Validation
```bash
python --version
# Should show: Python 3.11.x

pip --version
```

---

## Step 4: Apache Spark

```bash
# Set Spark version
SPARK_VERSION=4.0.1
HADOOP_VERSION=3

# Download Spark
cd ~
wget https://dlcdn.apache.org/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz

# Extract
tar -xzf spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz

# Move to /opt (optional, or keep in home)
sudo mv spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} /opt/spark
# OR keep in home:
# mv spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} ~/spark

# Set environment variables
cat >> ~/.bashrc << 'EOF'
export SPARK_HOME=/opt/spark
export PATH=$SPARK_HOME/bin:$SPARK_HOME/sbin:$PATH
export PYSPARK_PYTHON=python3
EOF
source ~/.bashrc

# Clean up
rm spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz
```

### Validation
```bash
spark-submit --version
# Should show: version 4.0.1

pyspark --version
```

---

## Step 5: Clone Repository

```bash
# Navigate to projects directory
mkdir -p ~/projects
cd ~/projects

# Clone repository (replace with your git URL)
git clone <repository-url> de_Funk
cd de_Funk

# Verify structure
ls -la
# Should see: app/, configs/, core/, datapipelines/, models/, scripts/, storage/, etc.
```

### Validation
```bash
# Check key directories exist
test -d configs/models && echo "✓ configs/models exists"
test -d models/implemented && echo "✓ models/implemented exists"
test -d storage && echo "✓ storage exists"
test -f requirements.txt && echo "✓ requirements.txt exists"
```

---

## Step 6: Python Dependencies

```bash
cd ~/projects/de_Funk

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install additional packages (if not in requirements.txt)
pip install \
    pyspark==4.0.1 \
    delta-spark==4.0.0 \
    duckdb \
    streamlit \
    plotly \
    networkx \
    pyyaml \
    python-dotenv \
    requests \
    pandas \
    pyarrow
```

### Validation
```bash
# Test imports
python -c "import pyspark; print(f'PySpark: {pyspark.__version__}')"
python -c "import duckdb; print(f'DuckDB: {duckdb.__version__}')"
python -c "import streamlit; print(f'Streamlit: {streamlit.__version__}')"
python -c "import delta; print('Delta Lake: OK')"
python -c "import networkx; print(f'NetworkX: {networkx.__version__}')"
```

---

## Step 7: Environment Configuration

### Create .env file

```bash
cd ~/projects/de_Funk

# Copy example (if exists)
cp .env.example .env 2>/dev/null || touch .env

# Edit .env with your API keys
cat > .env << 'EOF'
# API Keys
ALPHA_VANTAGE_API_KEYS=your_alpha_vantage_key_here
CHICAGO_API_KEYS=your_chicago_key_here
COOK_COUNTY_API_KEYS=your_cook_county_key_here

# Connection type (duckdb or spark)
CONNECTION_TYPE=duckdb

# Logging
LOG_LEVEL=INFO

# Spark settings (if using Spark)
SPARK_DRIVER_MEMORY=4g
SPARK_EXECUTOR_MEMORY=4g
SPARK_SHUFFLE_PARTITIONS=200

# DuckDB settings (if using DuckDB)
DUCKDB_MEMORY_LIMIT=4GB
DUCKDB_THREADS=4
EOF
```

### Create storage directories

```bash
cd ~/projects/de_Funk

# Create storage structure
mkdir -p storage/bronze
mkdir -p storage/silver
mkdir -p storage/duckdb
mkdir -p logs

# Set permissions
chmod -R 755 storage/
chmod -R 755 logs/
```

---

## Step 8: Validation

### Full System Test

```bash
cd ~/projects/de_Funk

# Test 1: Python imports
echo "=== Testing Python imports ==="
python -c "
import sys
sys.path.insert(0, '.')
from config import ConfigLoader
from de_funk.app import DeFunk
print('✓ Core imports working')
"

# Test 2: Model registry
echo "=== Testing Model Registry ==="
python -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
from de_funk.app import DeFunk
app = DeFunk.from_config("configs/")
models = registry.list_models()
print(f'✓ Found {len(models)} models: {models}')
"

# Test 3: Spark connectivity
echo "=== Testing Spark ==="
python -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder \
    .appName('test') \
    .master('local[2]') \
    .config('spark.driver.memory', '2g') \
    .getOrCreate()
print(f'✓ Spark version: {spark.version}')
spark.stop()
"

# Test 4: DuckDB
echo "=== Testing DuckDB ==="
python -c "
import duckdb
conn = duckdb.connect(':memory:')
result = conn.execute('SELECT 42 as answer').fetchone()
print(f'✓ DuckDB working: {result[0]}')
conn.close()
"

# Test 5: Streamlit (non-blocking check)
echo "=== Testing Streamlit ==="
python -c "import streamlit; print('✓ Streamlit importable')"
```

### Run Application Test

```bash
cd ~/projects/de_Funk

# Quick UI test (will open browser)
# Press Ctrl+C after verifying it starts
streamlit run app/ui/notebook_app_duckdb.py --server.headless true &
sleep 5
curl -s http://localhost:8501 > /dev/null && echo "✓ Streamlit server responding"
pkill -f streamlit
```

---

## Step 9: Connect to Central Machine

### Option A: Shared Storage (NFS/CIFS)

```bash
# Install NFS client
sudo apt install -y nfs-common

# Mount shared storage (replace with your NFS server)
sudo mkdir -p /mnt/de_funk_data
sudo mount -t nfs central-server:/data/de_funk /mnt/de_funk_data

# Create symlink to storage
cd ~/projects/de_Funk
rm -rf storage  # Remove local storage
ln -s /mnt/de_funk_data storage

# Add to fstab for persistence
echo "central-server:/data/de_funk /mnt/de_funk_data nfs defaults 0 0" | sudo tee -a /etc/fstab
```

### Option B: Rsync from Central

```bash
# Sync bronze/silver data from central machine
rsync -avz --progress user@central-server:/path/to/de_Funk/storage/ ~/projects/de_Funk/storage/

# Schedule periodic sync (crontab -e)
# 0 * * * * rsync -az user@central-server:/path/to/de_Funk/storage/ ~/projects/de_Funk/storage/
```

### Option C: SSH Tunnel for Spark Master

```bash
# If connecting to central Spark cluster
ssh -L 7077:localhost:7077 user@central-server

# Then submit jobs to spark://localhost:7077
```

### Validate Central Connection

```bash
# Check storage is accessible
ls -la ~/projects/de_Funk/storage/bronze/
ls -la ~/projects/de_Funk/storage/silver/

# Verify data exists
python -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
bronze = Path('storage/bronze')
silver = Path('storage/silver')
print(f'Bronze tables: {list(bronze.glob(\"*\"))}')
print(f'Silver tables: {list(silver.glob(\"*\"))}')
"
```

---

## Quick Start Commands

After setup, these are the common commands:

```bash
# Activate environment (if using conda)
conda activate de_funk

# Navigate to project
cd ~/projects/de_Funk

# Run the UI
python run_app.py
# OR
streamlit run app/ui/notebook_app_duckdb.py

# Run full pipeline (with data)
python -m scripts.run_full_pipeline --max-tickers 100

# Build silver layer only
python -m scripts.build_silver_layer

# Test all models
python -m scripts.test_all_models
```

---

## Troubleshooting

### Java not found
```bash
# Check Java installation
which java
java -version

# If not found, reinstall
sudo apt install -y openjdk-17-jdk
```

### Spark memory errors
```bash
# Increase driver memory in .env
SPARK_DRIVER_MEMORY=8g

# Or pass directly
spark-submit --driver-memory 8g your_script.py
```

### DuckDB permission errors
```bash
# Check storage permissions
ls -la storage/duckdb/
chmod 755 storage/duckdb/
```

### Module not found errors
```bash
# Ensure you're in the project root
cd ~/projects/de_Funk

# Add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Streamlit port in use
```bash
# Find and kill existing process
lsof -i :8501
kill -9 <PID>

# Or use different port
streamlit run app/ui/notebook_app_duckdb.py --server.port 8502
```

### Delta Lake jar issues
```bash
# Verify Delta jar is being loaded
python -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder \
    .config('spark.jars.packages', 'io.delta:delta-spark_2.13:4.0.0') \
    .getOrCreate()
print(spark.conf.get('spark.jars.packages'))
spark.stop()
"
```

---

## Environment Summary

After successful setup, your environment should have:

| Component | Version | Check Command |
|-----------|---------|---------------|
| Ubuntu | 22.04+ | `lsb_release -a` |
| Java | 17 | `java -version` |
| Python | 3.11+ | `python --version` |
| Spark | 4.0.1 | `spark-submit --version` |
| PySpark | 4.0.1 | `python -c "import pyspark; print(pyspark.__version__)"` |
| DuckDB | Latest | `python -c "import duckdb; print(duckdb.__version__)"` |
| Delta Lake | 4.0.0 | `python -c "import delta; print('OK')"` |
| Streamlit | Latest | `streamlit --version` |

---

## Next Steps

1. **Get API Keys**: Register for free API keys:
   - [Alpha Vantage](https://www.alphavantage.co/support/#api-key) (free tier: 5 calls/min)
   - [Chicago Data Portal](https://data.cityofchicago.org/) (free app token)
   - [Cook County Data Portal](https://datacatalog.cookcountyil.gov/) (same Socrata token)

2. **Run Initial Ingestion**:
   ```bash
   python -m scripts.run_full_pipeline --max-tickers 100 --skip-forecasts
   ```

3. **Launch UI**:
   ```bash
   python run_app.py
   ```

4. **Explore Models**:
   ```bash
   python -m scripts.test_all_models
   ```

#!/bin/bash
#
# Production Pipeline (Standalone Spark)
#
# Alternative to Ray-based pipeline. Uses:
# - Simple Python for API ingestion (no orchestrator needed - APIs are throttled)
# - Standalone Spark cluster for Silver builds
#
# Usage:
#   ./run_pipeline.sh                      # Full pipeline
#   ./run_pipeline.sh --skip-ingestion     # Silver only
#   ./run_pipeline.sh --skip-silver        # Ingestion only
#   ./run_pipeline.sh --max-tickers 100    # Limited run
#
# Prerequisites:
#   1. Spark cluster running: ./start-master.sh && ./start-all-workers.sh
#   2. NFS mounted at /shared/storage
#   3. API keys in .env
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/spark-env.sh"

# Defaults
STORAGE_PATH="${SHARED_STORAGE:-/shared/storage}"
MAX_TICKERS=""
SKIP_SEED=false
SKIP_INGESTION=false
SKIP_SILVER=false
SKIP_TECHNICALS=false
FORCE_SEED=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --max-tickers)
            MAX_TICKERS="$2"
            shift 2
            ;;
        --skip-seed)
            SKIP_SEED=true
            shift
            ;;
        --skip-ingestion)
            SKIP_INGESTION=true
            shift
            ;;
        --skip-silver)
            SKIP_SILVER=true
            shift
            ;;
        --skip-technicals)
            SKIP_TECHNICALS=true
            shift
            ;;
        --force-seed)
            FORCE_SEED=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --storage-path PATH    Storage location (default: /shared/storage)"
            echo "  --max-tickers N        Limit tickers to process"
            echo "  --skip-seed            Skip seeding step"
            echo "  --skip-ingestion       Skip Bronze ingestion"
            echo "  --skip-silver          Skip Silver build"
            echo "  --skip-technicals      Skip technicals computation"
            echo "  --force-seed           Force re-seed even if data exists"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "======================================================================"
echo "  de_Funk Production Pipeline (Standalone Spark)"
echo "======================================================================"
echo ""
echo "Storage Path: $STORAGE_PATH"
echo "Max Tickers: ${MAX_TICKERS:-all}"
echo "Skip Seed: $SKIP_SEED"
echo "Skip Ingestion: $SKIP_INGESTION"
echo "Skip Silver: $SKIP_SILVER"
echo "Skip Technicals: $SKIP_TECHNICALS"
echo ""

cd "$PROJECT_ROOT"
source "$VENV_PATH/bin/activate"

# -----------------------------------------------------------------------------
# Step 0: Verify Spark Cluster
# -----------------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "Step 0: Verifying Spark Cluster"
echo "----------------------------------------------------------------------"

if ! curl -s "http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT/json/" > /dev/null 2>&1; then
    echo "ERROR: Spark master not responding at $SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
    echo ""
    echo "Start the cluster first:"
    echo "  ./scripts/spark-cluster/start-master.sh"
    echo "  ./scripts/spark-cluster/start-all-workers.sh"
    exit 1
fi

WORKER_COUNT=$(curl -s "http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT/json/" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('workers',[])))" 2>/dev/null || echo "0")
echo "  ✓ Spark Master running"
echo "  ✓ Workers registered: $WORKER_COUNT"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Seed Data
# -----------------------------------------------------------------------------
if [ "$SKIP_SEED" = false ]; then
    echo "----------------------------------------------------------------------"
    echo "Step 1: Seeding Data"
    echo "----------------------------------------------------------------------"

    SEED_ARGS="--storage-path $STORAGE_PATH"
    if [ "$FORCE_SEED" = true ]; then
        SEED_ARGS="$SEED_ARGS --force"
    fi

    # Seed tickers (from LISTING_STATUS - 1 API call)
    echo "Seeding tickers..."
    python -m scripts.seed.seed_tickers $SEED_ARGS

    # Seed calendar (2000-2050)
    echo "Seeding calendar..."
    python -m scripts.seed.seed_calendar $SEED_ARGS

    echo "  ✓ Seeding complete"
    echo ""
fi

# -----------------------------------------------------------------------------
# Step 2: Bronze Ingestion (Simple Python - no Spark needed)
# -----------------------------------------------------------------------------
if [ "$SKIP_INGESTION" = false ]; then
    echo "----------------------------------------------------------------------"
    echo "Step 2: Bronze Ingestion (Python)"
    echo "----------------------------------------------------------------------"
    echo ""
    echo "API ingestion runs as simple Python - no cluster needed."
    echo "Rate limits are the bottleneck, not compute."
    echo ""

    INGEST_ARGS="--storage-path $STORAGE_PATH"
    if [ -n "$MAX_TICKERS" ]; then
        INGEST_ARGS="$INGEST_ARGS --max-tickers $MAX_TICKERS"
    fi

    # Run ingestion (this is I/O bound, single process is fine)
    python -m scripts.ingest.run_bronze_ingestion $INGEST_ARGS

    echo "  ✓ Bronze ingestion complete"
    echo ""
fi

# -----------------------------------------------------------------------------
# Step 3: Silver Build (Spark Cluster)
# -----------------------------------------------------------------------------
if [ "$SKIP_SILVER" = false ]; then
    echo "----------------------------------------------------------------------"
    echo "Step 3: Silver Build (Spark Cluster)"
    echo "----------------------------------------------------------------------"
    echo ""
    echo "Submitting to Spark cluster at $SPARK_MASTER_URL"
    echo ""

    # Submit Silver build to Spark cluster
    "$SCRIPT_DIR/submit-job.sh" \
        scripts/build/build_models.py \
        --storage-root "$STORAGE_PATH" \
        --models temporal company stocks

    echo "  ✓ Silver build complete"
    echo ""
fi

# -----------------------------------------------------------------------------
# Step 4: Technical Indicators (Spark Cluster, Batched)
# -----------------------------------------------------------------------------
if [ "$SKIP_TECHNICALS" = false ] && [ "$SKIP_SILVER" = false ]; then
    echo "----------------------------------------------------------------------"
    echo "Step 4: Technical Indicators (Spark Cluster, Batched)"
    echo "----------------------------------------------------------------------"

    "$SCRIPT_DIR/submit-job.sh" \
        scripts/build/compute_technicals.py \
        --storage-path "$STORAGE_PATH"

    echo "  ✓ Technicals complete"
    echo ""
fi

echo "======================================================================"
echo "  Pipeline Complete"
echo "======================================================================"
echo ""
echo "Summary:"
echo "  Bronze: $STORAGE_PATH/bronze/"
echo "  Silver: $STORAGE_PATH/silver/"
echo ""
echo "Spark UI: http://$SPARK_MASTER_HOST:$SPARK_MASTER_WEBUI_PORT"
echo ""

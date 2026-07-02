#!/bin/bash
# ==============================================================================
# Unified Pipeline Test Script
# ==============================================================================
# Tests the full pipeline using IngestorEngine paradigm on Spark cluster.
# Configuration loaded from run_config.json profiles.
#
# Usage:
#   ./scripts/test/test_pipeline.sh --profile <PROFILE> [OPTIONS]
#
# Options:
#   --profile PROFILE    Use named profile (quick_test, dev, silver_only, staging, production)
#   --models MODELS      Specify models to build (space-separated, e.g., "temporal stocks")
#   --max-tickers N      Override max tickers to process
#   --skip-seed          Skip ticker seeding (use existing Bronze data)
#   --force-seed         Force re-seed even if ticker data exists
#   --skip-ingest        Skip Bronze ingestion
#   --skip-deps          Skip building model dependencies (assumes they exist in Silver)
#   --save-raw           Save raw API responses to raw/{provider}/ before transformation
#   --storage-path PATH  Override storage path (default: from run_config.json)
#   --local              Run locally (ignore SPARK_MASTER_URL)
#   --help               Show this help message
#
# Profiles (defined in run_config.json):
#   dev          - Bronze only: alpha_vantage + chicago + cook_county
#   silver_only  - Silver only: build models from existing bronze data
#   staging      - Full pipeline: bronze + silver (500 tickers)
#   production   - Full pipeline: all tickers
#
# Endpoints are configured in run_config.json providers.{provider}.endpoints
#
# Examples:
#   ./scripts/test/test_pipeline.sh --profile dev                    # Bronze ingestion only
#   ./scripts/test/test_pipeline.sh --profile silver_only            # Build silver from existing bronze
#   ./scripts/test/test_pipeline.sh --profile silver_only --models temporal  # Build specific model
#   ./scripts/test/test_pipeline.sh --profile silver_only --models forecast --skip-deps  # Build only forecast
#   ./scripts/test/test_pipeline.sh --profile staging                # Full pipeline
#   ./scripts/test/test_pipeline.sh --profile dev --save-raw         # Save raw API responses
#
# Author: de_Funk Team
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROFILE=""
MAX_TICKERS=""
SKIP_SEED=false
FORCE_SEED=false
SKIP_INGEST=false
BUILD_SILVER=false
MODELS=""
STORAGE_PATH=""
RUN_LOCAL=false
SAVE_RAW=false
SKIP_DEPS=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
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
        --force-seed)
            FORCE_SEED=true
            shift
            ;;
        --skip-ingest)
            SKIP_INGEST=true
            shift
            ;;
        --save-raw)
            SAVE_RAW=true
            shift
            ;;
        --models)
            MODELS="$2"
            shift 2
            ;;
        --storage-path)
            STORAGE_PATH="$2"
            shift 2
            ;;
        --local)
            RUN_LOCAL=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --help)
            head -50 "$0" | grep -E "^#" | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Determine repo root first (needed for config loading)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# Source .env file if it exists (for API keys)
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

# Auto-detect storage path if not explicitly set
# Priority: 1) --storage-path arg, 2) /shared/storage (NFS), 3) $REPO_ROOT/storage (local)
if [ -z "$STORAGE_PATH" ]; then
    if [ -d "/shared/storage" ]; then
        STORAGE_PATH="/shared/storage"
        echo -e "${GREEN}Using NFS storage: /shared/storage${NC}"
    else
        STORAGE_PATH="$REPO_ROOT/storage"
        echo -e "${YELLOW}Using local storage: $REPO_ROOT/storage${NC}"
    fi
fi

# Load profile settings from run_config.json if profile is specified
PROFILE_PROVIDERS=""
PROFILE_HAS_PROVIDERS="false"
PROFILE_BUILD_SILVER=""
if [ -n "$PROFILE" ] && [ -f "$REPO_ROOT/configs/pipelines/run_config.json" ]; then
    export REPO_ROOT PROFILE

    eval $(python3 << 'PYEOF'
import json
import os

repo_root = os.environ.get('REPO_ROOT', '.')
profile_name = os.environ.get('PROFILE', '')

with open(f'{repo_root}/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)

profile = cfg.get('profiles', {}).get(profile_name, {})

# max_tickers
max_tickers = profile.get('max_tickers')
if max_tickers:
    print(f'PROFILE_MAX_TICKERS="{max_tickers}"')
else:
    print('PROFILE_MAX_TICKERS=""')

# build_silver from profile
if profile.get('build_silver'):
    print('PROFILE_BUILD_SILVER="true"')
else:
    print('PROFILE_BUILD_SILVER="false"')

# providers list
if 'providers' in profile:
    providers = profile.get('providers', [])
    print(f'PROFILE_PROVIDERS="{" ".join(providers)}"')
    print('PROFILE_HAS_PROVIDERS="true"')
else:
    print('PROFILE_PROVIDERS=""')
    print('PROFILE_HAS_PROVIDERS="false"')

# write_batch_size
write_batch_size = profile.get('write_batch_size', 500000)
print(f'PROFILE_WRITE_BATCH_SIZE="{write_batch_size}"')

# max_pending_writes (0 = synchronous, 2 = default async)
max_pending_writes = profile.get('max_pending_writes', 2)
print(f'PROFILE_MAX_PENDING_WRITES="{max_pending_writes}"')
PYEOF
)

    [ -z "$MAX_TICKERS" ] && [ -n "$PROFILE_MAX_TICKERS" ] && MAX_TICKERS="$PROFILE_MAX_TICKERS"
    [ "$PROFILE_BUILD_SILVER" = "true" ] && BUILD_SILVER=true
fi

# If --models is specified, we want to build them
if [ -n "$MODELS" ]; then
    BUILD_SILVER=true
fi

# Print header
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}     de_Funk Pipeline Test - IngestorEngine Paradigm        ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

echo -e "Repository root: ${GREEN}$REPO_ROOT${NC}"

# Check Spark environment
if [ "$RUN_LOCAL" = false ]; then
    if [ -z "$SPARK_MASTER_URL" ] && [ -f "$REPO_ROOT/configs/cluster.yaml" ]; then
        CLUSTER_HEAD=$(python3 -c "
import yaml
with open('$REPO_ROOT/configs/cluster.yaml') as f:
    cfg = yaml.safe_load(f)
cluster = cfg.get('cluster', {})
head_cfg = cluster.get('head', {})
head = head_cfg.get('ip') or head_cfg.get('hostname', '')
port = cfg.get('spark', {}).get('master', {}).get('port', 7077)
print(f'spark://{head}:{port}' if head else '')
" 2>/dev/null || echo "")
        [ -n "$CLUSTER_HEAD" ] && export SPARK_MASTER_URL="$CLUSTER_HEAD"
    fi
fi

if [ "$RUN_LOCAL" = false ] && [ -n "$SPARK_MASTER_URL" ]; then
    echo -e "Spark master: ${GREEN}$SPARK_MASTER_URL${NC}"
    SPARK_MODE="cluster"
else
    echo -e "Spark mode: ${YELLOW}local${NC}"
    SPARK_MODE="local"
    unset SPARK_MASTER_URL
fi

# Display configuration
echo ""
echo -e "${YELLOW}Configuration:${NC}"
[ -n "$PROFILE" ] && echo "  Profile: $PROFILE"
[ -n "$MAX_TICKERS" ] && echo "  Max tickers: $MAX_TICKERS"
[ -n "$STORAGE_PATH" ] && echo "  Storage path: $STORAGE_PATH"
echo "  Skip seed: $SKIP_SEED"
echo "  Skip ingest: $SKIP_INGEST"
echo "  Save raw: $SAVE_RAW"
echo "  Build silver: $([ "$BUILD_SILVER" = true ] && echo 'yes' || echo 'no')"
[ -n "$MODELS" ] && echo "  Models to build: $MODELS"
echo ""

# Check if Alpha Vantage is enabled
if [ "$PROFILE_HAS_PROVIDERS" = "true" ]; then
    if [ -n "$PROFILE_PROVIDERS" ] && echo "$PROFILE_PROVIDERS" | grep -qw "alpha_vantage"; then
        ALPHA_VANTAGE_ENABLED="true"
    else
        ALPHA_VANTAGE_ENABLED="false"
        if [ -z "$PROFILE_PROVIDERS" ]; then
            echo -e "${YELLOW}Profile has no providers (silver-only mode)${NC}"
        else
            echo -e "${YELLOW}Alpha Vantage not in profile providers: $PROFILE_PROVIDERS${NC}"
        fi
    fi
else
    ALPHA_VANTAGE_ENABLED=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
print('true' if cfg.get('providers', {}).get('alpha_vantage', {}).get('enabled') else 'false')
" 2>/dev/null || echo "false")

    if [ "$ALPHA_VANTAGE_ENABLED" = "false" ]; then
        echo -e "${YELLOW}Alpha Vantage is disabled in run_config.json${NC}"
    fi
fi

# ==============================================================================
# Task 1: Seed Tickers (Alpha Vantage)
# ==============================================================================
if [ "$SKIP_SEED" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ]; then
    LISTING_STATUS_PATH="${STORAGE_PATH:-/shared/storage}/bronze/alpha_vantage/listing_status"
    if [ -d "$LISTING_STATUS_PATH/_delta_log" ] && [ "$FORCE_SEED" != "true" ]; then
        echo -e "${YELLOW}○ Listing status exists at $LISTING_STATUS_PATH - skipping${NC}"
    else
        echo -e "${BLUE}============================================================${NC}"
        echo -e "${BLUE}Testing task: ingest listing_status (ticker reference)${NC}"
        echo -e "${BLUE}============================================================${NC}"

        python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_pipeline')

logger.info('Testing task: ingest listing_status')

from datapipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider
from datapipelines.ingestors.bronze_sink import BronzeSink
from orchestration.common.spark_session import get_spark
from pathlib import Path
import json

storage_path = '${STORAGE_PATH:-/shared/storage}'
logger.info(f'Storage path: {storage_path}')

docs_path = Path('$REPO_ROOT')
spark = get_spark(app_name='test_pipeline_listing_status')
provider = create_alpha_vantage_provider(spark=spark, docs_path=docs_path)

# Use seed_tickers method to get all US tickers from LISTING_STATUS endpoint
df = provider.seed_tickers(state='active', filter_us_exchanges=True)

with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

sink = BronzeSink(storage_cfg)
# Write to alpha_vantage/listing_status (the proper endpoint-based path)
# Partitions from endpoint markdown: Data Sources/Endpoints/Alpha Vantage/Core/Listing Status.md
sink.overwrite(df, 'alpha_vantage/listing_status', partitions=['asset_type'])

logger.info(f'Ingested {df.count()} tickers to alpha_vantage/listing_status')
spark.stop()
"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Seed tickers completed${NC}"
        else
            echo -e "${RED}✗ Seed tickers failed${NC}"
            exit 1
        fi
        echo ""
    fi
fi

# ==============================================================================
# Task 2: Bronze Ingestion (Alpha Vantage)
# ==============================================================================
if [ "$SKIP_INGEST" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Testing task: bronze ingestion (Alpha Vantage)${NC}"
    echo -e "${BLUE}============================================================${NC}"

    # Get config from run_config.json (with profile override support)
    eval $(python3 -c "
import json
import os
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
profile_name = os.environ.get('PROFILE', '$PROFILE')
profile = cfg.get('profiles', {}).get(profile_name, {})
av = cfg.get('providers', {}).get('alpha_vantage', {})
# Use profile-specific endpoints if defined, otherwise default
endpoints = profile.get('alpha_vantage_endpoints', av.get('endpoints', []))
ticker_source = av.get('ticker_source', 'market_cap')
print(f'AV_ENDPOINTS=\"{\" \".join(endpoints)}\"')
print(f'AV_TICKER_SOURCE=\"{ticker_source}\"')
" 2>/dev/null)

    echo -e "Ticker source: ${GREEN}$AV_TICKER_SOURCE${NC}"
    echo -e "Endpoints: ${GREEN}$AV_ENDPOINTS${NC}"

    python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_pipeline')

logger.info('Testing task: bronze ingestion (Alpha Vantage)')

from datapipelines.base.ingestor_engine import IngestorEngine
from datapipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider
from orchestration.common.spark_session import get_spark
from pathlib import Path
import json

storage_path = '${STORAGE_PATH:-/shared/storage}'
# Handle null/empty max_tickers - None means no limit
max_tickers_str = '${MAX_TICKERS}'
max_tickers = int(max_tickers_str) if max_tickers_str.strip() else None

logger.info(f'Storage path: {storage_path}')
logger.info(f'Max tickers: {max_tickers if max_tickers else \"ALL (no limit)\"}')

docs_path = Path('$REPO_ROOT')
spark = get_spark(app_name='test_pipeline_ingest')

with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)
storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    run_config = json.load(f)

# Always pass storage_path so provider can read from raw cache
# Raw cache is checked automatically - use --force-api to bypass
provider = create_alpha_vantage_provider(spark=spark, docs_path=docs_path, storage_path=Path(storage_path))
logger.info(f'Raw cache path: {storage_path}/raw/alpha_vantage/')

max_pending_writes = int('${PROFILE_MAX_PENDING_WRITES:-2}')
engine = IngestorEngine(provider, storage_cfg, max_pending_writes=max_pending_writes)
logger.info(f'Max pending writes: {max_pending_writes} (0=sync, 2=async)')

# Get ticker_source from config: 'market_cap' or 'seed'
av_config = run_config.get('providers', {}).get('alpha_vantage', {})
ticker_source = av_config.get('ticker_source', 'market_cap')
logger.info(f'Ticker source: {ticker_source}')

tickers = []

if ticker_source == 'market_cap':
    # Try to get tickers ranked by market cap from company_reference
    tickers = provider.get_tickers_by_market_cap(max_tickers=max_tickers, storage_cfg=storage_cfg)
    if tickers:
        logger.info(f'Loaded {len(tickers)} tickers ranked by market cap')

# Fall back to seed if market_cap returned nothing, or if ticker_source is 'seed'
if not tickers:
    ticker_seed_path = Path(storage_cfg['roots']['bronze']) / 'seeds' / 'tickers'
    if ticker_seed_path.exists():
        if ticker_source == 'market_cap':
            logger.warning('⚠ No market cap data available - falling back to ticker_seed. Run company_overview ingestion first for market_cap ranking.')
        else:
            logger.info('Using ticker_seed as configured')
        if (ticker_seed_path / '_delta_log').exists():
            df = spark.read.format('delta').load(str(ticker_seed_path))
        else:
            df = spark.read.parquet(str(ticker_seed_path))
        # Apply limit only if max_tickers is set
        ticker_df = df.select('ticker').distinct()
        if max_tickers:
            ticker_df = ticker_df.limit(max_tickers)
        tickers = [row.ticker for row in ticker_df.collect()]
        logger.info(f'Loaded {len(tickers)} tickers from ticker_seed')
    else:
        logger.error('No tickers found. Run seed first.')
        sys.exit(1)

if not tickers:
    logger.error('No tickers available for ingestion.')
    sys.exit(1)

logger.info(f'Found {len(tickers)} tickers for ingestion')
provider.set_tickers(tickers)

# Get endpoints from config - check profile override first
profile_name = '${PROFILE}'
profile = run_config.get('profiles', {}).get(profile_name, {})
av_config_endpoints = run_config.get('providers', {}).get('alpha_vantage', {}).get('endpoints', ['time_series_daily'])
# Profile-specific endpoints override the default
endpoints = profile.get('alpha_vantage_endpoints', av_config_endpoints)
logger.info(f'Endpoints from config (profile={profile_name}): {endpoints}')

# Map endpoint names to work item types
# Note: listing_status is a BULK endpoint (handled in Task 1), not per-ticker
endpoint_to_work_item = {
    'time_series_daily': 'prices',
    'time_series_daily_adjusted': 'prices',
    'company_overview': 'reference',
    'income_statement': 'income',
    'balance_sheet': 'balance',
    'cash_flow': 'cashflow',
    'earnings': 'earnings',
    'dividends': 'dividends',
    'splits': 'splits',
    # listing_status is NOT here - it's a bulk endpoint seeded in Task 1
}

work_items = []
unmapped_endpoints = []
for ep in endpoints:
    work_item = endpoint_to_work_item.get(ep)
    if work_item and work_item not in work_items:
        work_items.append(work_item)
    elif ep not in ['listing_status'] and not work_item:
        unmapped_endpoints.append(ep)

if unmapped_endpoints:
    logger.warning(f'⚠ Unmapped endpoints (not in endpoint_to_work_item): {unmapped_endpoints}')

logger.info(f'Work items: {work_items}')

if not work_items:
    logger.info('No per-ticker endpoints to ingest (only bulk endpoints like listing_status). Skipping Task 2.')
    spark.stop()
    sys.exit(0)

write_batch_size = int('${PROFILE_WRITE_BATCH_SIZE:-500000}')
logger.info(f'write_batch_size: {write_batch_size}')

results = engine.run(
    work_items=work_items,
    write_batch_size=write_batch_size,
    silent=False
)

logger.info(f'Ingestion complete. Completed: {results.completed_work_items}/{results.total_work_items}, Records: {results.total_records:,}')
spark.stop()
"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Bronze ingestion completed${NC}"
    else
        echo -e "${RED}✗ Bronze ingestion failed${NC}"
        exit 1
    fi
    echo ""
fi

# ==============================================================================
# Task 2b: Chicago/Cook County Ingestion (Bulk Providers)
# ==============================================================================
if [ "$SKIP_INGEST" = false ]; then
    if [ "$PROFILE_HAS_PROVIDERS" = "true" ]; then
        BULK_PROVIDERS=""
        for p in $PROFILE_PROVIDERS; do
            if [ "$p" = "chicago" ] || [ "$p" = "cook_county" ]; then
                BULK_PROVIDERS="$BULK_PROVIDERS $p"
            fi
        done
        BULK_PROVIDERS=$(echo "$BULK_PROVIDERS" | xargs)
    else
        BULK_PROVIDERS=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
providers = cfg.get('providers', {})
enabled = []
if providers.get('chicago', {}).get('enabled'):
    enabled.append('chicago')
if providers.get('cook_county', {}).get('enabled'):
    enabled.append('cook_county')
print(' '.join(enabled))
" 2>/dev/null || echo "")
    fi

    if [ -n "$BULK_PROVIDERS" ]; then
        echo -e "${BLUE}============================================================${NC}"
        echo -e "${BLUE}Testing task: bulk provider ingestion (Chicago/Cook County)${NC}"
        echo -e "${BLUE}============================================================${NC}"
        echo -e "Enabled providers: ${GREEN}$BULK_PROVIDERS${NC}"

        python -c "
import sys
sys.path.insert(0, '$REPO_ROOT')

from config.logging import setup_logging, get_logger
setup_logging()
logger = get_logger('test_pipeline')

logger.info('Testing task: bulk provider ingestion')

from datapipelines.base.ingestor_engine import IngestorEngine
from datapipelines.providers.chicago.chicago_provider import create_chicago_provider
from datapipelines.providers.cook_county.cook_county_provider import create_cook_county_provider
from orchestration.common.spark_session import get_spark
from pathlib import Path
import json

storage_path = '${STORAGE_PATH:-/shared/storage}'

with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    run_config = json.load(f)

with open('$REPO_ROOT/configs/storage.json') as f:
    storage_cfg = json.load(f)

storage_cfg['roots'] = {k: v.replace('storage/', f'{storage_path}/') for k, v in storage_cfg['roots'].items()}

logger.info(f'Storage path: {storage_path}')

spark = get_spark(app_name='test_pipeline_bulk')
docs_path = Path('$REPO_ROOT')

provider_factories = {
    'chicago': create_chicago_provider,
    'cook_county': create_cook_county_provider,
}

bulk_providers = '$BULK_PROVIDERS'.split()
logger.info(f'Bulk providers to process: {bulk_providers}')

for provider_name in bulk_providers:
    try:
        provider_cfg = run_config.get('providers', {}).get(provider_name, {})
        logger.info(f'Processing provider: {provider_name}')

        factory = provider_factories.get(provider_name)
        if not factory:
            logger.warning(f'Unknown provider: {provider_name} - skipping')
            continue

        # ALWAYS pass storage_path to enable BULK ingestion path (Spark-native CSV reading)
        # storage_path is required for get_raw_path() to return a path instead of None
        # Without it, the provider falls back to INCREMENTAL path with Python CSV streaming
        provider = factory(spark=spark, docs_path=docs_path, storage_path=Path(storage_path))
        logger.info(f'Created provider: {provider.provider_id}')
        logger.info(f'BULK ingestion enabled: raw CSVs at {storage_path}/raw/{provider_name}/')

        max_pending_writes = int('${PROFILE_MAX_PENDING_WRITES:-2}')
        engine = IngestorEngine(provider, storage_cfg, max_pending_writes=max_pending_writes)

        # Check for profile-specific endpoint override (e.g., cook_county_endpoints in dev_fill)
        profile_cfg = run_config.get('profiles', {}).get('${PROFILE}', {})
        profile_endpoints_key = f'{provider_name}_endpoints'
        work_items = profile_cfg.get(profile_endpoints_key) or provider_cfg.get('endpoints', []) or None
        if work_items:
            # Filter out #-prefixed endpoints (comments)
            skipped = [w for w in work_items if w.startswith('#')]
            work_items = [w for w in work_items if not w.startswith('#')]
            if skipped:
                logger.info(f'Skipping commented endpoints: {skipped}')
            if profile_endpoints_key in profile_cfg:
                logger.info(f'Work items from profile override: {work_items}')
            else:
                logger.info(f'Work items from global config: {len(work_items)} endpoints')
        else:
            logger.info('Work items: auto-discover from provider')
        max_records = profile_cfg.get('max_records_per_endpoint')

        if max_records is None:
            logger.info(f'max_records_per_endpoint is null - fetching ALL records (no limit)')

        write_batch_size = int('${PROFILE_WRITE_BATCH_SIZE:-500000}')
        logger.info(f'write_batch_size: {write_batch_size}')

        results = engine.run(
            work_items=work_items,
            write_batch_size=write_batch_size,
            max_records=max_records,
            silent=False
        )

        logger.info(f'{provider_name}: {results.completed_work_items}/{results.total_work_items} work items, {results.total_records:,} total records')

        # Shutdown executor between providers to release thread-local memory
        IngestorEngine.shutdown_executor()
        logger.info(f'Shutdown ThreadPoolExecutor after {provider_name}')

    except Exception as e:
        logger.error(f'Error processing {provider_name}: {e}', exc_info=True)
        raise

spark.stop()
logger.info('Bulk provider ingestion complete')
"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Bulk provider ingestion completed${NC}"
        else
            echo -e "${RED}✗ Bulk provider ingestion failed${NC}"
            exit 1
        fi
        echo ""
    fi
fi

# ==============================================================================
# Task 3: Silver Build
# ==============================================================================
if [ "$BUILD_SILVER" = true ]; then
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Testing task: silver model build${NC}"
    echo -e "${BLUE}============================================================${NC}"

    if [ -z "$MODELS" ]; then
        MODELS=$(python3 -c "
import json
with open('$REPO_ROOT/configs/pipelines/run_config.json') as f:
    cfg = json.load(f)
models = cfg.get('silver_models', {}).get('models', [])
print(' '.join(models))
" 2>/dev/null || echo "")
    fi

    BUILD_STORAGE="${STORAGE_PATH:-/shared/storage}"
    BUILD_ARGS="--storage-root $BUILD_STORAGE"
    [ -n "$MODELS" ] && BUILD_ARGS="$BUILD_ARGS --models $MODELS"
    [ "$SKIP_DEPS" = true ] && BUILD_ARGS="$BUILD_ARGS --skip-deps"

    echo -e "Building models: ${GREEN}${MODELS:-all discovered}${NC}"
    [ "$SKIP_DEPS" = true ] && echo -e "  ${YELLOW}(skipping dependencies)${NC}"

    "$REPO_ROOT/scripts/spark-cluster/submit-job.sh" "$REPO_ROOT/scripts/build/build_models.py" $BUILD_ARGS --verbose

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Silver build completed${NC}"
    else
        echo -e "${RED}✗ Silver build failed${NC}"
        exit 1
    fi
    echo ""
fi

# ==============================================================================
# Summary
# ==============================================================================
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}Pipeline test completed successfully!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "Results:"
[ "$SKIP_SEED" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ] && echo "  ✓ Tickers seeded (Alpha Vantage)"
[ "$SKIP_SEED" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "false" ] && echo "  ○ Ticker seed skipped (Alpha Vantage disabled)"
[ "$SKIP_INGEST" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "true" ] && echo "  ✓ Bronze data ingested (Alpha Vantage)"
[ "$SKIP_INGEST" = false ] && [ "$ALPHA_VANTAGE_ENABLED" = "false" ] && echo "  ○ Alpha Vantage ingestion skipped (disabled)"
[ "$SKIP_INGEST" = false ] && [ -n "$BULK_PROVIDERS" ] && echo "  ✓ Bulk providers ingested ($BULK_PROVIDERS)"
[ "$BUILD_SILVER" = true ] && echo "  ✓ Silver models built"
[ "$BUILD_SILVER" = false ] && echo "  ○ Silver build skipped"
if [ "$SAVE_RAW" = true ]; then
    echo ""
    echo "Raw data locations:"
    [ "$ALPHA_VANTAGE_ENABLED" = "true" ] && echo "  Alpha Vantage: ${STORAGE_PATH:-/shared/storage}/raw/alpha_vantage/"
    [ -n "$BULK_PROVIDERS" ] && echo "  Bulk providers: ${STORAGE_PATH:-/shared/storage}/raw/{chicago,cook_county}/"
fi
echo ""

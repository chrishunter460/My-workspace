#!/usr/bin/env python3
"""
Deep diagnostic script for forecast view creation issues.
This will trace every step of the process.
"""

import sys
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("FORECAST VIEW CREATION DIAGNOSTIC")
print("=" * 80)

# Step 1: Initialize repo context and create session
print("\n[STEP 1] Loading UniversalSession...")
try:
from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession

    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )
    print("✓ Session loaded successfully")
    print(f"  - Has model_graph: {hasattr(session, 'model_graph')}")
    if hasattr(session, 'model_graph'):
        print(f"  - Graph models: {list(session.model_graph.graph.nodes())}")
except Exception as e:
    print(f"✗ Failed to load session: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 2: Load company model first
print("\n[STEP 2] Loading company model...")
try:
    company_model = session.load_model('company')
    print(f"✓ Company model loaded: {type(company_model)}")
    print(f"  - Has _facts attr: {hasattr(company_model, '_facts')}")

    # Build it to populate _facts
    print("  - Building company model...")
    company_model.ensure_built()

    if hasattr(company_model, '_facts'):
        print(f"  - Company _facts keys: {list(company_model._facts.keys())}")
        print(f"  - Has fact_prices: {'fact_prices' in company_model._facts}")

        if 'fact_prices' in company_model._facts:
            fact_prices = company_model._facts['fact_prices']
            print(f"  - fact_prices type: {type(fact_prices)}")

            # Try to get schema
            try:
                if hasattr(fact_prices, 'columns'):
                    print(f"  - fact_prices columns: {fact_prices.columns}")
                else:
                    print(f"  - fact_prices schema: {fact_prices}")
            except Exception as e:
                print(f"  - Could not inspect schema: {e}")
except Exception as e:
    print(f"✗ Failed to load company model: {e}")
    traceback.print_exc()
    company_model = None

# Step 3: Load forecast model
print("\n[STEP 3] Loading forecast model...")
try:
    forecast_model = session.load_model('forecast')
    print(f"✓ Forecast model loaded: {type(forecast_model)}")
    print(f"  - Has _facts attr: {hasattr(forecast_model, '_facts')}")
    print(f"  - Has session attr: {hasattr(forecast_model, 'session')}")
    print(f"  - Has connection attr: {hasattr(forecast_model, 'connection')}")

    if hasattr(forecast_model, 'connection'):
        conn = forecast_model.connection
        print(f"  - Connection type: {type(conn)}")
        print(f"  - Has execute: {hasattr(conn, 'execute')}")
        print(f"  - Has conn: {hasattr(conn, 'conn')}")
except Exception as e:
    print(f"✗ Failed to load forecast model: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 4: Build forecast model (will trigger register_views)
print("\n[STEP 4] Building forecast model (triggers register_views)...")
print("-" * 80)
try:
    forecast_model.ensure_built()
    print("-" * 80)
    print("✓ Forecast model built")

    if hasattr(forecast_model, '_facts'):
        print(f"  - Forecast _facts keys: {list(forecast_model._facts.keys())}")
        print(f"  - Has vw_price_predictions: {'vw_price_predictions' in forecast_model._facts}")
except Exception as e:
    print("-" * 80)
    print(f"✗ Failed to build forecast model: {e}")
    traceback.print_exc()

# Step 5: Inspect fact_forecasts table schema
print("\n[STEP 5] Inspecting fact_forecasts schema...")
if hasattr(forecast_model, '_facts') and 'fact_forecasts' in forecast_model._facts:
    try:
        fact_forecasts = forecast_model._facts['fact_forecasts']
        print(f"  - fact_forecasts type: {type(fact_forecasts)}")

        # Get connection
        if hasattr(forecast_model.connection, 'conn'):
            duckdb_conn = forecast_model.connection.conn
        else:
            duckdb_conn = forecast_model.connection

        # Register and inspect
        duckdb_conn.register('fact_forecasts_debug', fact_forecasts)
        result = duckdb_conn.execute("SELECT * FROM fact_forecasts_debug LIMIT 0").description
        columns = [col[0] for col in result]
        print(f"  - Columns: {columns}")
        print(f"  - Has predicted_close: {'predicted_close' in columns}")
        print(f"  - Has predicted_value: {'predicted_value' in columns}")

        # Check actual data
        try:
            sample = duckdb_conn.execute("SELECT * FROM fact_forecasts_debug LIMIT 1").fetchdf()
            print(f"  - Sample row count: {len(sample)}")
            if len(sample) > 0:
                print(f"  - Sample columns: {list(sample.columns)}")
        except Exception as e:
            print(f"  - Could not fetch sample: {e}")

    except Exception as e:
        print(f"✗ Failed to inspect fact_forecasts: {e}")
        traceback.print_exc()
else:
    print("✗ fact_forecasts not in _facts")

# Step 6: Try to access the view directly
print("\n[STEP 6] Testing view access...")
try:
    if hasattr(forecast_model.connection, 'conn'):
        duckdb_conn = forecast_model.connection.conn
    else:
        duckdb_conn = forecast_model.connection

    # Check if view exists
    views = duckdb_conn.execute("""
        SELECT schema_name, view_name
        FROM information_schema.views
        WHERE schema_name = 'forecast'
    """).fetchdf()

    print(f"  - Views in forecast schema: {list(views['view_name']) if len(views) > 0 else 'none'}")

    # Try to query the view
    if 'vw_price_predictions' in views['view_name'].values:
        try:
            result = duckdb_conn.execute("SELECT * FROM forecast.vw_price_predictions LIMIT 1").fetchdf()
            print(f"  - ✓ View is queryable, columns: {list(result.columns)}")
        except Exception as e:
            print(f"  - ✗ View exists but not queryable: {e}")
    else:
        print("  - View vw_price_predictions does not exist")

except Exception as e:
    print(f"✗ Failed to check views: {e}")
    traceback.print_exc()

# Step 7: Check the actual register_views code
print("\n[STEP 7] Checking register_views method...")
try:
    import inspect
    source = inspect.getsource(forecast_model.register_views)

    # Check for f-string usage
    if 'f"""' in source or "f'''" in source:
        print("  ✓ Method uses f-strings for SQL generation")
    else:
        print("  ✗ Method does NOT use f-strings (this is the bug!)")

    # Check for column detection
    if 'predicted_col' in source:
        print("  ✓ Method has column detection logic")
    else:
        print("  ✗ Method missing column detection logic")

    # Check for fact_prices loading
    if 'load_model' in source:
        print("  ✓ Method tries to load company model")
    else:
        print("  ✗ Method doesn't load company model")

    # Show the first 50 lines
    print("\n  First 50 lines of register_views:")
    lines = source.split('\n')
    for i, line in enumerate(lines[:50], 1):
        print(f"    {i:3d}: {line}")

except Exception as e:
    print(f"✗ Failed to inspect register_views: {e}")
    traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)

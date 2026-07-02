#!/usr/bin/env python3
"""
Deep diagnostic for session injection in forecast model.
This will trace the exact sequence of set_session() and ensure_built() calls.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("SESSION INJECTION DIAGNOSTIC")
print("=" * 80)

# Check BaseModel has the method
print("\n[STEP 1] Checking BaseModel.set_session() method exists...")
from de_funk.models.base.model import BaseModel
import inspect

if hasattr(BaseModel, 'set_session'):
    print("✓ BaseModel.set_session() method exists")
    source = inspect.getsource(BaseModel.set_session)
    print(f"  Source:\n{source}")
else:
    print("✗ BaseModel.set_session() method DOES NOT EXIST")
    print("  This is the problem! Need to pull latest model.py")
    sys.exit(1)

# Check BaseModel.__init__ has self.session
print("\n[STEP 2] Checking BaseModel.__init__ initializes self.session...")
init_source = inspect.getsource(BaseModel.__init__)
if 'self.session' in init_source:
    print("✓ BaseModel.__init__ initializes self.session")
    # Show the line
    for i, line in enumerate(init_source.split('\n'), 1):
        if 'self.session' in line and '=' in line:
            print(f"  Line {i}: {line.strip()}")
else:
    print("✗ BaseModel.__init__ does NOT initialize self.session")
    print("  This is a problem! Need to pull latest model.py")
    sys.exit(1)

# Load session and check injection logic
print("\n[STEP 3] Loading UniversalSession and checking load_model logic...")
from de_funk.models.api.session import UniversalSession
from de_funk.core.context import RepoContext

# Check if session.load_model() has the injection code
load_model_source = inspect.getsource(UniversalSession.load_model)
if "set_session" in load_model_source:
    print("✓ UniversalSession.load_model() has set_session injection code")
    for i, line in enumerate(load_model_source.split('\n'), 1):
        if 'set_session' in line:
            print(f"  Line {i}: {line.strip()}")
else:
    print("⚠ UniversalSession.load_model() missing set_session injection")

# Create session and load forecast model
print("\n[STEP 4] Creating session and loading forecast model...")
ctx = RepoContext.from_repo_root(connection_type="duckdb")
session = UniversalSession(
    connection=ctx.connection,
    storage_cfg=ctx.storage,
    repo_root=ctx.repo
)
print(f"✓ Session created: {session}")

# Monkey-patch to trace calls
print("\n[STEP 5] Tracing model instantiation and method calls...")

original_set_session = BaseModel.set_session
original_ensure_built = None

def traced_set_session(self, session):
    print(f"  → set_session() called on {self.__class__.__name__}")
    print(f"    Before: self.session = {getattr(self, 'session', 'ATTR_MISSING')}")
    result = original_set_session(self, session)
    print(f"    After: self.session = {self.session}")
    return result

BaseModel.set_session = traced_set_session

print("  Loading forecast model...")
forecast_model = session.load_model('forecast')

print(f"\n  After load_model():")
print(f"    - Model class: {forecast_model.__class__.__name__}")
print(f"    - Has session attr: {hasattr(forecast_model, 'session')}")
if hasattr(forecast_model, 'session'):
    print(f"    - session value: {forecast_model.session}")
    print(f"    - session is None: {forecast_model.session is None}")
    print(f"    - session type: {type(forecast_model.session)}")
else:
    print(f"    - session attribute MISSING")

# Now build it
print("\n[STEP 6] Building forecast model (will trigger register_views)...")

# Trace ensure_built calls on all models
from de_funk.models.implemented.forecast.company_forecast_model import CompanyForecastModel

original_ensure_built = CompanyForecastModel.ensure_built

def traced_ensure_built(self):
    print(f"  → ensure_built() called on {self.__class__.__name__}")
    print(f"    self.session at this point: {getattr(self, 'session', 'ATTR_MISSING')}")
    if hasattr(self, 'session') and self.session:
        print(f"    ✓ Session is available")
    else:
        print(f"    ✗ Session is None or missing")
    return original_ensure_built(self)

CompanyForecastModel.ensure_built = traced_ensure_built

print("-" * 80)
forecast_model.ensure_built()
print("-" * 80)

print("\n[STEP 7] Final state check...")
print(f"  - forecast_model.session: {getattr(forecast_model, 'session', 'ATTR_MISSING')}")
if hasattr(forecast_model, '_facts'):
    print(f"  - _facts keys: {list(forecast_model._facts.keys())}")
    print(f"  - Has vw_price_predictions: {'vw_price_predictions' in forecast_model._facts}")

# Try to load company model through the session
print("\n[STEP 8] Attempting to load company model via session...")
if hasattr(forecast_model, 'session') and forecast_model.session:
    try:
        print("  Loading company model...")
        company_model = forecast_model.session.load_model('company')
        print(f"  ✓ Company model loaded: {type(company_model)}")

        print("  Building company model...")
        company_model.ensure_built()

        if hasattr(company_model, '_facts') and 'fact_prices' in company_model._facts:
            print(f"  ✓ fact_prices is available in company model")
            print(f"    Type: {type(company_model._facts['fact_prices'])}")
        else:
            print(f"  ✗ fact_prices NOT in company model")
    except Exception as e:
        print(f"  ✗ Error loading company model: {e}")
        import traceback
        traceback.print_exc()
else:
    print("  ✗ Cannot load company model - session is None or missing")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)

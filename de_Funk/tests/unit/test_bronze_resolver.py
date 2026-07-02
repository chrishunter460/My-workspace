"""
BronzeResolver unit tests — ref parsing, index building, resolve, and catalog.

Tests use temporary filesystem fixtures that mirror the data_sources/ structure
with provider and endpoint markdown files.

Usage:
    pytest tests/unit/test_bronze_resolver.py -v
"""
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()

import pytest

from de_funk.api.bronze_resolver import BronzeResolver, BronzeEndpointInfo


# ---------------------------------------------------------------------------
# Fixtures — build a minimal data_sources/ + bronze/ tree in tmp
# ---------------------------------------------------------------------------

PROVIDER_MD = """\
---
type: api-provider
provider_id: chicago
provider: Chicago Data Portal
base_url: https://data.cityofchicago.org
---
"""

ENDPOINT_CRIMES_MD = """\
---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: crimes
bronze: chicago
schema:
  - [id, string]
  - [case_number, string]
  - [primary_type, string]
  - [arrest, boolean]
  - [year, int]
---
"""

ENDPOINT_PERMITS_MD = """\
---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: building_permits
bronze: chicago
schema:
  - [permit_number, string]
  - [issue_date, timestamp]
  - [work_type, string]
---
"""

ENDPOINT_NO_SCHEMA_MD = """\
---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: missing_schema
bronze: chicago
---
"""


@pytest.fixture
def bronze_tree(tmp_path):
    """Build a minimal data_sources/ and bronze/ tree for testing."""
    data_sources = tmp_path / "data_sources"
    bronze_root = tmp_path / "bronze"

    # Provider file
    providers_dir = data_sources / "Providers"
    providers_dir.mkdir(parents=True)
    (providers_dir / "Chicago Data Portal.md").write_text(PROVIDER_MD)

    # Endpoint files
    eps_dir = data_sources / "Endpoints" / "Chicago Data Portal" / "Public Safety"
    eps_dir.mkdir(parents=True)
    (eps_dir / "Crimes.md").write_text(ENDPOINT_CRIMES_MD)

    housing_dir = data_sources / "Endpoints" / "Chicago Data Portal" / "Housing"
    housing_dir.mkdir(parents=True)
    (housing_dir / "Building Permits.md").write_text(ENDPOINT_PERMITS_MD)

    # Endpoint with no schema (should be skipped)
    ops_dir = data_sources / "Endpoints" / "Chicago Data Portal" / "Operational"
    ops_dir.mkdir(parents=True)
    (ops_dir / "MissingSchema.md").write_text(ENDPOINT_NO_SCHEMA_MD)

    # Bronze data dirs (must exist on disk for resolver to include them)
    (bronze_root / "chicago" / "crimes").mkdir(parents=True)
    (bronze_root / "chicago" / "building_permits").mkdir(parents=True)
    # Intentionally do NOT create missing_schema dir

    return data_sources, bronze_root


@pytest.fixture
def resolver(bronze_tree):
    """Create a BronzeResolver with the test fixture tree."""
    data_sources, bronze_root = bronze_tree
    return BronzeResolver(data_sources_root=data_sources, bronze_root=bronze_root)


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

class TestIndexBuilding:
    def test_builds_on_first_resolve(self, resolver):
        """Index is lazily built on first resolve call."""
        assert not resolver._built
        resolver.resolve("chicago.crimes.primary_type")
        assert resolver._built

    def test_discovers_providers(self, resolver):
        """Known providers populated from Providers/*.md."""
        resolver._build_index()
        assert "chicago" in resolver._known_providers

    def test_discovers_endpoints(self, resolver):
        """Endpoints with schema and bronze path on disk are indexed."""
        resolver._build_index()
        assert "crimes" in resolver._index.get("chicago", {})
        assert "building_permits" in resolver._index.get("chicago", {})

    def test_skips_endpoint_without_schema(self, resolver):
        """Endpoints missing schema field are not indexed."""
        resolver._build_index()
        assert "missing_schema" not in resolver._index.get("chicago", {})

    def test_skips_endpoint_without_bronze_dir(self, bronze_tree):
        """Endpoints whose bronze path doesn't exist on disk are skipped."""
        data_sources, bronze_root = bronze_tree
        # Add endpoint whose dir does NOT exist
        eps_dir = data_sources / "Endpoints" / "Chicago Data Portal" / "Finance"
        eps_dir.mkdir(parents=True)
        (eps_dir / "Payments.md").write_text("""\
---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: payments
bronze: chicago
schema:
  - [payment_id, string]
---
""")
        r = BronzeResolver(data_sources_root=data_sources, bronze_root=bronze_root)
        r._build_index()
        assert "payments" not in r._index.get("chicago", {})

    def test_field_types_captured(self, resolver):
        """Schema column types are stored in the endpoint info."""
        resolver._build_index()
        info = resolver._index["chicago"]["crimes"]
        assert info.fields["primary_type"] == "string"
        assert info.fields["year"] == "int"


# ---------------------------------------------------------------------------
# Reference parsing
# ---------------------------------------------------------------------------

class TestRefParsing:
    def test_three_part_split(self, resolver):
        """Standard provider.endpoint.field parsing."""
        resolver._build_index()
        pid, eid, field = resolver._parse_ref("chicago.crimes.primary_type")
        assert (pid, eid, field) == ("chicago", "crimes", "primary_type")

    def test_unknown_provider_falls_back(self, resolver):
        """Unknown provider falls back to naive 3-part dot split."""
        resolver._build_index()
        pid, eid, field = resolver._parse_ref("unknown.endpoint.field")
        assert (pid, eid, field) == ("unknown", "endpoint", "field")

    def test_too_few_parts_raises(self, resolver):
        """References with fewer than 3 dot segments raise ValueError."""
        resolver._build_index()
        with pytest.raises(ValueError, match="endpoint.field"):
            resolver._parse_ref("chicago.crimes")

    def test_too_few_parts_single_segment(self, resolver):
        """Single-segment reference raises ValueError."""
        resolver._build_index()
        with pytest.raises(ValueError, match="provider.endpoint.field"):
            resolver._parse_ref("crimes")


# ---------------------------------------------------------------------------
# resolve()
# ---------------------------------------------------------------------------

class TestResolve:
    def test_resolve_valid_ref(self, resolver):
        """resolve() returns a ResolvedField with correct attributes."""
        resolved = resolver.resolve("chicago.crimes.primary_type")
        assert resolved.table_name == "crimes"
        assert resolved.column == "primary_type"
        assert resolved.format_code is None
        assert "chicago" in str(resolved.silver_path)
        assert "crimes" in str(resolved.silver_path)

    def test_resolve_domain_is_provider(self, resolver):
        """ResolvedField.domain returns the provider_id."""
        resolved = resolver.resolve("chicago.crimes.arrest")
        assert resolved.domain == "chicago"

    def test_resolve_caches(self, resolver):
        """Repeated resolve() returns cached object."""
        r1 = resolver.resolve("chicago.crimes.id")
        r2 = resolver.resolve("chicago.crimes.id")
        assert r1 is r2

    def test_resolve_unknown_provider(self, resolver):
        """resolve() raises ValueError for unknown provider."""
        with pytest.raises(ValueError, match="not found"):
            resolver.resolve("unknown.endpoint.field")

    def test_resolve_unknown_endpoint(self, resolver):
        """resolve() raises ValueError for unknown endpoint."""
        with pytest.raises(ValueError, match="not found"):
            resolver.resolve("chicago.unknown.field")

    def test_resolve_unknown_field(self, resolver):
        """resolve() raises ValueError for unknown field on a known endpoint."""
        with pytest.raises(ValueError, match="not found"):
            resolver.resolve("chicago.crimes.nonexistent")

    def test_resolve_different_endpoint(self, resolver):
        """resolve() works across different endpoints of the same provider."""
        resolved = resolver.resolve("chicago.building_permits.work_type")
        assert resolved.table_name == "building_permits"
        assert resolved.column == "work_type"


# ---------------------------------------------------------------------------
# Interface compatibility (same methods as FieldResolver)
# ---------------------------------------------------------------------------

class TestInterfaceCompat:
    def test_reachable_domains_passthrough(self, resolver):
        """reachable_domains() returns input unchanged."""
        inp = {"chicago", "alpha_vantage"}
        assert resolver.reachable_domains(inp) == inp

    def test_find_join_path_always_none(self, resolver):
        """find_join_path() always returns None."""
        assert resolver.find_join_path("crimes", "building_permits") is None
        assert resolver.find_join_path("a", "b", allowed_domains={"chicago"}) is None


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_catalog_structure(self, resolver):
        """get_endpoint_catalog() returns nested provider → endpoint → fields."""
        cat = resolver.get_endpoint_catalog()
        assert "chicago" in cat
        assert "endpoints" in cat["chicago"]
        assert "crimes" in cat["chicago"]["endpoints"]
        crimes = cat["chicago"]["endpoints"]["crimes"]
        assert "fields" in crimes
        assert "primary_type" in crimes["fields"]
        assert crimes["fields"]["primary_type"]["type"] == "string"

    def test_catalog_ref_format(self, resolver):
        """Catalog entries include a 'ref' in provider.endpoint format."""
        cat = resolver.get_endpoint_catalog()
        assert cat["chicago"]["endpoints"]["crimes"]["ref"] == "chicago.crimes"

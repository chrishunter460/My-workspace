"""
Unit tests for config/markdown_loader.py

Tests the YAML frontmatter parsing, schema extraction, and config loading
from markdown files.
"""
from __future__ import annotations

import pytest
import tempfile
from pathlib import Path

from de_funk.config.markdown_loader import (
    MarkdownConfigLoader,
    SchemaField,
    BronzeConfig,
    EndpointConfig,
    ProviderConfig,
)


class TestFrontmatterParsing:
    """Test YAML frontmatter extraction from markdown files."""

    def test_parse_valid_frontmatter(self, tmp_path):
        """Test parsing a valid markdown file with frontmatter."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
type: api-endpoint
provider: Test Provider
endpoint_id: test_endpoint
---

## Description

This is a test endpoint.
""")
        loader = MarkdownConfigLoader(tmp_path)
        frontmatter, body = loader.parse_frontmatter(md_file)

        assert frontmatter['type'] == 'api-endpoint'
        assert frontmatter['provider'] == 'Test Provider'
        assert frontmatter['endpoint_id'] == 'test_endpoint'
        assert '## Description' in body

    def test_parse_missing_frontmatter(self, tmp_path):
        """Test that missing frontmatter raises ValueError."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""# No frontmatter here

Just regular markdown.
""")
        loader = MarkdownConfigLoader(tmp_path)

        with pytest.raises(ValueError, match="No YAML frontmatter"):
            loader.parse_frontmatter(md_file)

    def test_parse_invalid_yaml(self, tmp_path):
        """Test that invalid YAML raises ValueError."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
type: api-endpoint
invalid: yaml: here: broken
  - not
 - properly
- indented
---

Content.
""")
        loader = MarkdownConfigLoader(tmp_path)

        with pytest.raises(ValueError, match="Invalid YAML"):
            loader.parse_frontmatter(md_file)


class TestSchemaArrayParsing:
    """Test array-format schema parsing."""

    def test_parse_full_schema_row(self, tmp_path):
        """Test parsing a complete schema row with all fields."""
        loader = MarkdownConfigLoader(tmp_path)

        schema_list = [
            ['ticker', 'string', 'Symbol', False, 'Stock ticker symbol'],
            ['market_cap', 'double', 'MarketCapitalization', True, 'Market cap in USD'],
        ]

        fields = loader.parse_schema_array(schema_list)

        assert len(fields) == 2
        assert fields[0].name == 'ticker'
        assert fields[0].type == 'string'
        assert fields[0].source == 'Symbol'
        assert fields[0].nullable is False
        assert fields[0].description == 'Stock ticker symbol'

        assert fields[1].name == 'market_cap'
        assert fields[1].type == 'double'
        assert fields[1].nullable is True

    def test_parse_minimal_schema_row(self, tmp_path):
        """Test parsing minimal schema row (3 elements)."""
        loader = MarkdownConfigLoader(tmp_path)

        schema_list = [
            ['ticker', 'string', 'Symbol'],  # Only required fields
        ]

        fields = loader.parse_schema_array(schema_list)

        assert len(fields) == 1
        assert fields[0].name == 'ticker'
        assert fields[0].nullable is True  # Default
        assert fields[0].description == ''  # Default

    def test_parse_invalid_schema_row(self, tmp_path):
        """Test that invalid rows are skipped with warning."""
        loader = MarkdownConfigLoader(tmp_path)

        schema_list = [
            ['valid', 'string', 'Valid'],
            ['too_short', 'string'],  # Invalid - only 2 elements
            'not_a_list',  # Invalid - not a list
        ]

        fields = loader.parse_schema_array(schema_list)

        assert len(fields) == 1
        assert fields[0].name == 'valid'


class TestSchemaBlockExtraction:
    """Test extracting schema from markdown body code blocks."""

    def test_extract_schema_from_yaml_block(self, tmp_path):
        """Test extracting schema from ```yaml code block."""
        loader = MarkdownConfigLoader(tmp_path)

        body = """
## Description

Some description text.

## Schema

```yaml
schema:
  - [ticker, string, Symbol, false, "Stock ticker"]
  - [price, double, Price, true, "Current price"]
```

## Notes

More text.
"""
        schema = loader.parse_schema_block(body)

        assert schema is not None
        assert len(schema) == 2
        assert schema[0][0] == 'ticker'
        assert schema[1][0] == 'price'

    def test_no_schema_block(self, tmp_path):
        """Test that missing schema block returns None."""
        loader = MarkdownConfigLoader(tmp_path)

        body = """
## Description

No schema here.

## Notes

Just text.
"""
        schema = loader.parse_schema_block(body)
        assert schema is None

    def test_schema_in_non_yaml_block_ignored(self, tmp_path):
        """Test that schema in non-yaml blocks is ignored."""
        loader = MarkdownConfigLoader(tmp_path)

        body = """
```python
schema = [
    ('ticker', 'string'),
]
```
"""
        schema = loader.parse_schema_block(body)
        assert schema is None


class TestBronzeConfigParsing:
    """Test bronze layer configuration parsing."""

    def test_parse_full_bronze_config(self, tmp_path):
        """Test parsing complete bronze config."""
        loader = MarkdownConfigLoader(tmp_path)

        bronze_dict = {
            'table': 'company_reference',
            'partitions': ['asset_type'],
            'write_strategy': 'upsert',
            'key_columns': ['ticker', 'cik'],
            'date_column': 'last_updated',
            'comment': 'Company fundamentals',
        }

        config = loader.parse_bronze_config(bronze_dict)

        assert config.table == 'company_reference'
        assert config.partitions == ['asset_type']
        assert config.write_strategy == 'upsert'
        assert config.key_columns == ['ticker', 'cik']
        assert config.date_column == 'last_updated'
        assert config.comment == 'Company fundamentals'

    def test_parse_minimal_bronze_config(self, tmp_path):
        """Test parsing bronze config with defaults."""
        loader = MarkdownConfigLoader(tmp_path)

        bronze_dict = {
            'table': 'my_table',
        }

        config = loader.parse_bronze_config(bronze_dict)

        assert config.table == 'my_table'
        assert config.partitions == []
        assert config.write_strategy == 'upsert'
        assert config.key_columns == []
        assert config.date_column is None


class TestProviderLoading:
    """Test provider configuration loading."""

    def test_load_provider(self, tmp_path):
        """Test loading a provider markdown file."""
        providers_dir = tmp_path / "Data Sources" / "Providers"
        providers_dir.mkdir(parents=True)

        provider_file = providers_dir / "Alpha Vantage.md"
        provider_file.write_text("""---
type: api-provider
provider_id: alpha_vantage
provider: Alpha Vantage
api_type: rest
base_url: https://www.alphavantage.co/query
auth_model: api-key
env_api_key: ALPHA_VANTAGE_API_KEYS
rate_limit_per_sec: 1.0
models: [stocks, company]
status: active
---

## Description

Alpha Vantage provides stock market data.
""")

        loader = MarkdownConfigLoader(tmp_path)
        providers = loader.load_providers()

        assert 'alpha_vantage' in providers
        prov = providers['alpha_vantage']
        assert prov.provider == 'Alpha Vantage'
        assert prov.base_url == 'https://www.alphavantage.co/query'
        assert prov.rate_limit_per_sec == 1.0
        assert prov.models == ['stocks', 'company']

    def test_load_provider_auto_id(self, tmp_path):
        """Test that provider_id is auto-generated from filename."""
        providers_dir = tmp_path / "Data Sources" / "Providers"
        providers_dir.mkdir(parents=True)

        provider_file = providers_dir / "Chicago Data Portal.md"
        provider_file.write_text("""---
type: api-provider
provider: Chicago Data Portal
base_url: https://data.cityofchicago.org
---

## Description

Chicago open data.
""")

        loader = MarkdownConfigLoader(tmp_path)
        providers = loader.load_providers()

        assert 'chicago_data_portal' in providers

    def test_skip_non_provider_files(self, tmp_path):
        """Test that non-provider files are skipped."""
        providers_dir = tmp_path / "Data Sources" / "Providers"
        providers_dir.mkdir(parents=True)

        # A file without type: api-provider
        other_file = providers_dir / "README.md"
        other_file.write_text("""---
type: documentation
---

# Provider Docs
""")

        loader = MarkdownConfigLoader(tmp_path)
        providers = loader.load_providers()

        assert len(providers) == 0


class TestEndpointLoading:
    """Test endpoint configuration loading."""

    def test_load_endpoint_with_schema(self, tmp_path):
        """Test loading an endpoint with embedded schema."""
        endpoints_dir = tmp_path / "Data Sources" / "Endpoints" / "Alpha Vantage" / "Core"
        endpoints_dir.mkdir(parents=True)

        endpoint_file = endpoints_dir / "Company Overview.md"
        endpoint_file.write_text("""---
type: api-endpoint
provider: Alpha Vantage
endpoint_id: company_overview
method: GET
endpoint_pattern: ""
default_query:
  function: OVERVIEW
required_params: [symbol]
response_key: null
domain: securities
data_tags: [reference, fundamentals]
bronze:
  table: company_reference
  partitions: []
  write_strategy: upsert
  key_columns: [cik]
---

## Description

Company fundamentals.

## Schema

```yaml
schema:
  - [ticker, string, Symbol, false, "Stock ticker"]
  - [cik, string, CIK, true, "SEC CIK"]
  - [market_cap, double, MarketCapitalization, true, "Market cap"]
```
""")

        loader = MarkdownConfigLoader(tmp_path)
        endpoints = loader.load_endpoints()

        assert 'company_overview' in endpoints
        ep = endpoints['company_overview']
        assert ep.provider == 'Alpha Vantage'
        assert ep.default_query == {'function': 'OVERVIEW'}
        assert ep.required_params == ['symbol']
        assert ep.bronze.table == 'company_reference'
        assert ep.bronze.key_columns == ['cik']
        assert len(ep.schema) == 3
        assert ep.schema[0].name == 'ticker'
        assert ep.schema[2].name == 'market_cap'

    def test_recursive_endpoint_discovery(self, tmp_path):
        """Test that endpoints are found in nested directories."""
        base = tmp_path / "Data Sources" / "Endpoints" / "Test Provider"

        # Create endpoints in different subdirectories
        (base / "Core").mkdir(parents=True)
        (base / "Nested" / "Deep").mkdir(parents=True)

        (base / "Core" / "Endpoint1.md").write_text("""---
type: api-endpoint
provider: Test Provider
endpoint_id: endpoint1
---
""")
        (base / "Nested" / "Deep" / "Endpoint2.md").write_text("""---
type: api-endpoint
provider: Test Provider
endpoint_id: endpoint2
---
""")

        loader = MarkdownConfigLoader(tmp_path)
        endpoints = loader.load_endpoints()

        assert 'endpoint1' in endpoints
        assert 'endpoint2' in endpoints

    def test_filter_endpoints_by_provider(self, tmp_path):
        """Test filtering endpoints by provider name."""
        endpoints_dir = tmp_path / "Data Sources" / "Endpoints"
        (endpoints_dir / "Provider A").mkdir(parents=True)
        (endpoints_dir / "Provider B").mkdir(parents=True)

        (endpoints_dir / "Provider A" / "EP1.md").write_text("""---
type: api-endpoint
provider: Provider A
endpoint_id: ep1
---
""")
        (endpoints_dir / "Provider B" / "EP2.md").write_text("""---
type: api-endpoint
provider: Provider B
endpoint_id: ep2
---
""")

        loader = MarkdownConfigLoader(tmp_path)

        all_endpoints = loader.load_endpoints()
        assert len(all_endpoints) == 2

        provider_a_endpoints = loader.load_endpoints(provider="Provider A")
        assert len(provider_a_endpoints) == 1
        assert 'ep1' in provider_a_endpoints

    def test_skip_template_files(self, tmp_path):
        """Test that files starting with _ are skipped."""
        endpoints_dir = tmp_path / "Data Sources" / "Endpoints"
        endpoints_dir.mkdir(parents=True)

        (endpoints_dir / "_Template.md").write_text("""---
type: api-endpoint
provider: Template
endpoint_id: template
---
""")
        (endpoints_dir / "Real Endpoint.md").write_text("""---
type: api-endpoint
provider: Real
endpoint_id: real
---
""")

        loader = MarkdownConfigLoader(tmp_path)
        endpoints = loader.load_endpoints()

        assert 'real' in endpoints
        assert 'template' not in endpoints


class TestCombinedConfig:
    """Test getting combined provider config (JSON-compatible format)."""

    def test_get_provider_config(self, tmp_path):
        """Test getting combined config matching JSON format."""
        # Create provider
        providers_dir = tmp_path / "Data Sources" / "Providers"
        providers_dir.mkdir(parents=True)

        (providers_dir / "Test Provider.md").write_text("""---
type: api-provider
provider_id: test_provider
provider: Test Provider
base_url: https://api.test.com
rate_limit_per_sec: 2.0
default_headers:
  X-API-Key: "${API_KEY}"
env_api_key: TEST_API_KEY
---
""")

        # Create endpoint
        endpoints_dir = tmp_path / "Data Sources" / "Endpoints" / "Test Provider"
        endpoints_dir.mkdir(parents=True)

        (endpoints_dir / "Get Data.md").write_text("""---
type: api-endpoint
provider: Test Provider
endpoint_id: get_data
method: GET
endpoint_pattern: /data/{id}
required_params: [id]
default_query:
  format: json
---
""")

        loader = MarkdownConfigLoader(tmp_path)
        config = loader.get_provider_config('test_provider')

        assert config is not None
        assert config['base_urls'] == {'core': 'https://api.test.com'}
        assert config['rate_limit_per_sec'] == 2.0
        assert config['headers'] == {'X-API-Key': '${API_KEY}'}
        assert 'get_data' in config['endpoints']
        assert config['endpoints']['get_data']['method'] == 'GET'
        assert config['endpoints']['get_data']['required_params'] == ['id']


class TestBronzeConfigExtraction:
    """Test extracting bronze configs from all endpoints."""

    def test_get_bronze_configs(self, tmp_path):
        """Test extracting all bronze table configs."""
        endpoints_dir = tmp_path / "Data Sources" / "Endpoints"
        endpoints_dir.mkdir(parents=True)

        (endpoints_dir / "EP1.md").write_text("""---
type: api-endpoint
provider: Test
endpoint_id: ep1
bronze:
  table: table_one
  partitions: [date]
  write_strategy: append
  key_columns: [id, date]
---
""")
        (endpoints_dir / "EP2.md").write_text("""---
type: api-endpoint
provider: Test
endpoint_id: ep2
bronze:
  table: table_two
  write_strategy: upsert
  key_columns: [id]
---
""")

        loader = MarkdownConfigLoader(tmp_path)
        bronze_configs = loader.get_bronze_configs()

        assert 'table_one' in bronze_configs
        assert bronze_configs['table_one']['partitions'] == ['date']
        assert bronze_configs['table_one']['write_strategy'] == 'append'
        assert bronze_configs['table_one']['_source_endpoint'] == 'ep1'

        assert 'table_two' in bronze_configs
        assert bronze_configs['table_two']['write_strategy'] == 'upsert'


class TestCaching:
    """Test configuration caching behavior."""

    def test_cache_is_used(self, tmp_path):
        """Test that subsequent calls use cache."""
        providers_dir = tmp_path / "Data Sources" / "Providers"
        providers_dir.mkdir(parents=True)

        (providers_dir / "Test.md").write_text("""---
type: api-provider
provider: Test
---
""")

        loader = MarkdownConfigLoader(tmp_path)

        # First call populates cache
        providers1 = loader.load_providers()

        # Modify file (shouldn't affect result due to cache)
        (providers_dir / "Test.md").write_text("""---
type: api-provider
provider: Modified
---
""")

        # Second call uses cache
        providers2 = loader.load_providers()
        assert providers2['test'].provider == 'Test'  # Original value

    def test_force_reload_bypasses_cache(self, tmp_path):
        """Test that force_reload bypasses cache."""
        providers_dir = tmp_path / "Data Sources" / "Providers"
        providers_dir.mkdir(parents=True)

        (providers_dir / "Test.md").write_text("""---
type: api-provider
provider: Test
---
""")

        loader = MarkdownConfigLoader(tmp_path)

        # First call
        providers1 = loader.load_providers()
        assert providers1['test'].provider == 'Test'

        # Modify file
        (providers_dir / "Test.md").write_text("""---
type: api-provider
provider: Modified
---
""")

        # Force reload
        providers2 = loader.load_providers(force_reload=True)
        assert providers2['test'].provider == 'Modified'

    def test_clear_cache(self, tmp_path):
        """Test cache clearing."""
        providers_dir = tmp_path / "Data Sources" / "Providers"
        providers_dir.mkdir(parents=True)

        (providers_dir / "Test.md").write_text("""---
type: api-provider
provider: Test
---
""")

        loader = MarkdownConfigLoader(tmp_path)
        loader.load_providers()

        assert loader._providers_cache is not None

        loader.clear_cache()

        assert loader._providers_cache is None
        assert loader._endpoints_cache is None

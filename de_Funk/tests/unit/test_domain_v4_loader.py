"""
Domain V4 Loader Tests — test suite for the multi-file domain config system.

Tests are organized by phase to match the implementation plan in
docs/proposals/015-domain-model-v4-implementation.md.

Usage:
    pytest tests/unit/test_domain_v4_loader.py -v
    pytest tests/unit/test_domain_v4_loader.py -v -k "phase0"
    pytest tests/unit/test_domain_v4_loader.py -v -k "phase1"
"""

import sys
from pathlib import Path

# Bootstrap repo imports
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()

import pytest
import yaml


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "domain_v4"


@pytest.fixture
def fixtures_dir():
    """Path to domain_v4 test fixtures."""
    return FIXTURES_DIR


def _parse_front_matter(file_path: Path) -> dict:
    """Minimal front matter parser for fixture validation."""
    import re
    content = file_path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


# ===========================================================================
# Phase 0: Fixture validation — all test markdown files parse correctly
# ===========================================================================

class TestPhase0FixtureValidation:
    """Verify test fixtures are well-formed before testing loader code."""

    def test_fixtures_dir_exists(self, fixtures_dir):
        assert fixtures_dir.exists(), f"Fixtures dir not found: {fixtures_dir}"

    def test_all_fixture_files_parse(self, fixtures_dir):
        """Every .md file in fixtures should have valid YAML front matter."""
        md_files = list(fixtures_dir.rglob("*.md"))
        assert len(md_files) >= 10, f"Expected 10+ fixture files, found {len(md_files)}"

        errors = []
        for md_file in md_files:
            try:
                config = _parse_front_matter(md_file)
                if not config:
                    errors.append(f"{md_file.name}: no front matter")
                elif "type" not in config:
                    errors.append(f"{md_file.name}: missing 'type' key")
            except Exception as e:
                errors.append(f"{md_file.name}: {e}")

        assert not errors, f"Fixture parse errors:\n" + "\n".join(errors)

    def test_file_type_distribution(self, fixtures_dir):
        """Verify fixtures cover all 5 file types."""
        type_counts = {}
        for md_file in fixtures_dir.rglob("*.md"):
            config = _parse_front_matter(md_file)
            file_type = config.get("type", "unknown")
            type_counts[file_type] = type_counts.get(file_type, 0) + 1

        assert "domain-base" in type_counts, "Missing domain-base fixtures"
        assert "domain-model" in type_counts, "Missing domain-model fixtures"
        assert "domain-model-table" in type_counts, "Missing domain-model-table fixtures"
        assert "domain-model-source" in type_counts, "Missing domain-model-source fixtures"
        assert "domain-model-view" in type_counts, "Missing domain-model-view fixtures"
        assert "reference" in type_counts, "Missing reference fixtures"

    def test_base_template_has_required_keys(self, fixtures_dir):
        """Base template should have canonical_fields, tables, subsets."""
        config = _parse_front_matter(fixtures_dir / "_base/simple/base_template.md")
        assert config["type"] == "domain-base"
        assert "canonical_fields" in config
        assert "tables" in config
        assert "subsets" in config
        assert "auto_edges" in config

    def test_subset_children_have_required_keys(self, fixtures_dir):
        """Subset children should have subset_of, subset_value, canonical_fields."""
        for child_name in ["subset_a.md", "subset_b.md"]:
            config = _parse_front_matter(
                fixtures_dir / f"_base/simple/child/{child_name}"
            )
            assert config["type"] == "domain-base"
            assert "subset_of" in config, f"{child_name} missing subset_of"
            assert "subset_value" in config, f"{child_name} missing subset_value"
            assert "canonical_fields" in config, f"{child_name} missing canonical_fields"
            assert "measures" in config, f"{child_name} missing measures"

    def test_model_has_required_keys(self, fixtures_dir):
        """Domain model should have extends, depends_on, graph, build."""
        config = _parse_front_matter(fixtures_dir / "models/test_model/model.md")
        assert config["type"] == "domain-model"
        assert config["model"] == "test_model"
        assert "extends" in config
        assert "depends_on" in config
        assert "graph" in config
        assert "build" in config
        assert "measures" in config

    def test_table_files_have_required_keys(self, fixtures_dir):
        """Table files should have table, extends, table_type."""
        for table_file in (fixtures_dir / "models/test_model/tables").glob("*.md"):
            config = _parse_front_matter(table_file)
            assert config["type"] == "domain-model-table", f"{table_file.name}"
            assert "table" in config, f"{table_file.name} missing table"
            assert "extends" in config, f"{table_file.name} missing extends"
            assert "table_type" in config, f"{table_file.name} missing table_type"

    def test_source_files_have_required_keys(self, fixtures_dir):
        """Source files should have maps_to, from, aliases."""
        source_dir = fixtures_dir / "models/test_model/sources"
        source_files = list(source_dir.rglob("*.md"))
        assert len(source_files) >= 2, f"Expected 2+ source files, found {len(source_files)}"

        for source_file in source_files:
            config = _parse_front_matter(source_file)
            assert config["type"] == "domain-model-source", f"{source_file.name}"
            assert "maps_to" in config, f"{source_file.name} missing maps_to"
            assert "from" in config, f"{source_file.name} missing from"
            assert "aliases" in config or "maps_to" in config, f"{source_file.name}"

    def test_view_file_has_required_keys(self, fixtures_dir):
        """View files should have view, view_type."""
        config = _parse_front_matter(
            fixtures_dir / "models/test_model/views/view_entity_summary.md"
        )
        assert config["type"] == "domain-model-view"
        assert "view" in config
        assert "view_type" in config
        assert config["view_type"] in ("derived", "rollup")

    def test_reference_file_not_a_model(self, fixtures_dir):
        """Reference files should have type: reference and no model: key."""
        config = _parse_front_matter(fixtures_dir / "_model_guides_/test_guide.md")
        assert config["type"] == "reference"
        assert "model" not in config


# ===========================================================================
# Phase 1: Core loader — multi-file discovery (tests added when loader exists)
# ===========================================================================

class TestPhase1CoreLoader:
    """Tests for DomainConfigLoader multi-file discovery."""

    @pytest.fixture
    def loader(self, fixtures_dir):
        """Create V4 loader pointed at test fixtures."""
        try:
            from de_funk.config.domain import DomainConfigLoader
            return DomainConfigLoader(fixtures_dir)
        except ImportError:
            pytest.skip("Phase 1 not yet implemented")

    def test_build_index_discovers_all_types(self, loader):
        """Index should categorize files by type."""
        index = loader._type_index
        assert "domain-base" in index
        assert "domain-model" in index
        assert "domain-model-table" in index
        assert "domain-model-source" in index
        assert "domain-model-view" in index
        assert "reference" in index

    def test_reference_files_not_in_models(self, loader):
        """Reference files should be indexed but not listed as models."""
        models = loader.list_models()
        for m in models:
            config = loader.load_model_config(m)
            assert config.get("type") != "reference"

    def test_load_model_assembles_tables(self, loader):
        """Loading test_model should auto-discover tables/*.md."""
        config = loader.load_model_config("test_model")
        assert "tables" in config
        assert "dim_entity" in config["tables"]
        assert "fact_events" in config["tables"]

    def test_load_model_assembles_sources(self, loader):
        """Loading test_model should auto-discover sources/**/*.md."""
        config = loader.load_model_config("test_model")
        assert "sources" in config
        source_names = [s.get("source") for s in config["sources"].values()]
        assert "events" in source_names
        assert "entities" in source_names

    def test_load_model_assembles_views(self, loader):
        """Loading test_model should auto-discover views/*.md."""
        config = loader.load_model_config("test_model")
        assert "views" in config
        assert "view_entity_summary" in config["views"]

    def test_extends_on_table_file(self, loader):
        """Table with extends: should inherit base schema."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        # Should have inherited schema from _base.simple.base_template._dim_entity
        assert "schema" in dim_entity
        # Should have entity_id from base
        col_names = [col[0] for col in dim_entity["schema"]]
        assert "entity_id" in col_names

    def test_extends_dot_notation(self, loader):
        """Dotted extends references should resolve correctly."""
        config = loader.load_model_config("test_model")
        # The model extends _base.simple.base_template
        assert "canonical_fields" in config or "tables" in config

    def test_deep_merge_preserves_child_overrides(self, loader):
        """Child config values should override parent values."""
        config = loader.load_model_config("test_model")
        # Model should have its own version, not parent's
        assert config.get("model") == "test_model"

    def test_model_metadata_preserved(self, loader):
        """Model metadata should survive assembly."""
        config = loader.load_model_config("test_model")
        assert config.get("metadata", {}).get("domain") == "test"
        assert config.get("status") == "active"

    def test_list_models_returns_domain_models_only(self, loader):
        """list_models() should return domain-model types only."""
        models = loader.list_models()
        assert "test_model" in models
        # Base templates should NOT appear
        assert "simple_entity" not in models

    def test_get_dependencies(self, loader):
        """Dependencies should be readable."""
        deps = loader.get_dependencies("test_model")
        assert "temporal" in deps


# ===========================================================================
# Phase 2: Schema — canonical_fields, additional_schema, derivations, subsets
# ===========================================================================

class TestPhase2Schema:
    """Tests for schema processing mechanisms."""

    @pytest.fixture
    def loader(self, fixtures_dir):
        from de_funk.config.domain import DomainConfigLoader
        return DomainConfigLoader(fixtures_dir)

    def test_canonical_fields_to_schema(self):
        """canonical_fields keyword format converts to positional schema format."""
        from de_funk.config.domain.schema import canonical_fields_to_schema

        canonical = [
            ["field_a", "string", {"nullable": True, "description": "Test field A"}],
            ["field_b", "integer", {"nullable": False, "description": "Test field B"}],
        ]
        schema = canonical_fields_to_schema(canonical)
        assert len(schema) == 2
        assert schema[0] == ["field_a", "string", True, "Test field A"]
        assert schema[1] == ["field_b", "integer", False, "Test field B"]

    def test_additional_schema_appended(self, loader):
        """additional_schema columns should be appended to inherited schema."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        col_names = [col[0] for col in dim_entity["schema"]]
        # region_code and priority from additional_schema
        assert "region_code" in col_names
        assert "priority" in col_names

    def test_additional_schema_after_inherited(self, loader):
        """additional_schema columns appear after inherited base columns."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        col_names = [col[0] for col in dim_entity["schema"]]
        # Base has entity_id, entity_name, entity_type, created_date
        # additional_schema has region_code, priority — they should come after
        assert col_names.index("entity_id") < col_names.index("region_code")
        assert col_names.index("entity_name") < col_names.index("priority")

    def test_derivations_override_derived(self, loader):
        """derivations: {col: "expr"} should update matching column's derived."""
        config = loader.load_model_config("test_model")
        dim_entity = config["tables"]["dim_entity"]
        # Find entity_id column — should have derivation "ABS(HASH(name))" from dim_entity.md
        found = False
        for col in dim_entity["schema"]:
            if col[0] == "entity_id":
                options = col[4] if len(col) > 4 else {}
                assert options.get("derived") == "ABS(HASH(name))"
                found = True
                break
        assert found, "entity_id column not found in dim_entity schema"

    def test_derivations_missing_column_ignored(self):
        """Derivation for nonexistent column is a safe no-op."""
        from de_funk.config.domain.schema import apply_derivations

        schema = [["col_a", "string", True, "desc"]]
        result = apply_derivations(schema, {"nonexistent_col": "EXPR()"})
        assert len(result) == 1
        assert result[0][0] == "col_a"

    def test_subset_absorption_discovers_children(self):
        """Loader should find subset children by subset_of reference."""
        base_config = _parse_front_matter(
            FIXTURES_DIR / "_base/simple/base_template.md"
        )
        assert "subsets" in base_config
        assert base_config["subsets"]["target_table"] == "_dim_entity"

    def test_subset_absorption_adds_nullable_columns(self, loader):
        """Absorbed subset columns should be nullable with {subset: VALUE}."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_schema = config["tables"]["_dim_entity"]["schema"]
        col_names = [col[0] for col in dim_entity_schema]
        # field_a1, field_a2 from subset_a and field_b1, field_b2, field_b3 from subset_b
        assert "field_a1" in col_names
        assert "field_a2" in col_names
        assert "field_b1" in col_names

    def test_subset_columns_have_metadata(self, loader):
        """Absorbed subset columns should have {subset: VALUE} metadata."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_schema = config["tables"]["_dim_entity"]["schema"]

        for col in dim_entity_schema:
            if col[0] == "field_a1":
                assert len(col) >= 5
                assert isinstance(col[4], dict)
                assert col[4].get("subset") == "TYPE_A"
                break
        else:
            pytest.fail("field_a1 not found in absorbed schema")

    def test_subset_absorption_merges_measures(self, loader):
        """Child measures should be absorbed into parent target table."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_measures = config["tables"]["_dim_entity"]["measures"]
        measure_names = [m[0] for m in dim_entity_measures if isinstance(m, list)]
        # avg_field_a2 from subset_a
        assert "avg_field_a2" in measure_names

    def test_subset_columns_are_nullable(self, loader):
        """All absorbed subset columns should be forced nullable."""
        config = loader.load_base("_base.simple.base_template", with_subsets=True)
        dim_entity_schema = config["tables"]["_dim_entity"]["schema"]

        for col in dim_entity_schema:
            if col[0] in ("field_a1", "field_a2", "field_b1", "field_b2", "field_b3"):
                assert col[2] is True, f"{col[0]} should be nullable but is {col[2]}"


# ===========================================================================
# Phase 3: Sources (placeholder — tests added with implementation)
# ===========================================================================

class TestPhase3Sources:
    """Tests for source file processing."""

    def test_aliases_to_select_list(self):
        """Alias pairs should convert to SQL SELECT expressions."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [
            ["entity_id", "ABS(HASH(name))"],
            ["entity_name", "name"],
            ["created_date", "create_dt"],
        ]
        select_list = build_select_expressions(aliases)
        assert "ABS(HASH(name)) AS entity_id" in select_list
        assert "name AS entity_name" in select_list
        assert "create_dt AS created_date" in select_list

    def test_domain_source_injected(self):
        """domain_source literal should be added to SELECT."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [["entity_name", "name"]]
        domain_source = "'test_provider'"
        select_list = build_select_expressions(aliases, domain_source=domain_source)
        assert "'test_provider' AS domain_source" in select_list

    def test_entry_type_injected(self):
        """entry_type discriminator should be added to SELECT."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [["entity_name", "name"]]
        select_list = build_select_expressions(aliases, entry_type="VENDOR_PAYMENT")
        assert "'VENDOR_PAYMENT' AS entry_type" in select_list

    def test_event_type_injected(self):
        """event_type discriminator should be added to SELECT."""
        from de_funk.config.domain.sources import build_select_expressions

        aliases = [["entity_name", "name"]]
        select_list = build_select_expressions(aliases, event_type="APPROPRIATION")
        assert "'APPROPRIATION' AS event_type" in select_list

    def test_multi_source_grouped(self):
        """Two sources with same maps_to should be grouped."""
        from de_funk.config.domain.sources import group_sources_by_target

        sources = {
            "source_a": {"maps_to": "fact_events", "from": "bronze.a"},
            "source_b": {"maps_to": "fact_events", "from": "bronze.b"},
            "source_c": {"maps_to": "dim_entity", "from": "bronze.c"},
        }
        grouped = group_sources_by_target(sources)
        assert len(grouped["fact_events"]) == 2
        assert len(grouped["dim_entity"]) == 1

    def test_unpivot_plan_generated(self):
        """unpivot config should produce correct column mapping."""
        from de_funk.config.domain.sources import build_unpivot_plan

        source_config = {
            "transform": "unpivot",
            "unpivot_aliases": [
                ["totalRevenue", "TOTAL_REVENUE"],
                ["costOfRevenue", "COST_OF_REVENUE"],
                ["grossProfit", "GROSS_PROFIT"],
            ],
        }
        plan = build_unpivot_plan(source_config)
        assert plan["transform"] == "unpivot"
        assert len(plan["mappings"]) == 3
        assert ("totalRevenue", "TOTAL_REVENUE") in plan["mappings"]
        assert "totalRevenue" in plan["source_columns"]
        assert "TOTAL_REVENUE" in plan["key_values"]

    def test_unpivot_plan_empty_for_non_unpivot(self):
        """Non-unpivot source should return empty plan."""
        from de_funk.config.domain.sources import build_unpivot_plan

        source_config = {"from": "bronze.some_table"}
        plan = build_unpivot_plan(source_config)
        assert plan == {}

    def test_process_source_config(self):
        """process_source_config should enrich config with select expressions."""
        from de_funk.config.domain.sources import process_source_config

        source = {
            "aliases": [["col_a", "source_col_a"], ["col_b", "source_col_b"]],
            "domain_source": "'test'",
            "maps_to": "fact_test",
            "from": "bronze.test",
        }
        result = process_source_config(source)
        assert "_select_expressions" in result
        assert "source_col_a AS col_a" in result["_select_expressions"]
        assert "'test' AS domain_source" in result["_select_expressions"]

    def test_loader_discovers_sources_with_aliases(self):
        """Loader should discover sources with their alias configurations."""
        from de_funk.config.domain import DomainConfigLoader

        loader = DomainConfigLoader(FIXTURES_DIR)
        config = loader.load_model_config("test_model")
        sources = config.get("sources", {})
        assert len(sources) >= 2

        # Check events source has aliases
        events_source = sources.get("events", {})
        assert "aliases" in events_source
        assert events_source.get("maps_to") == "fact_events"


# ===========================================================================
# Phases 4-8: Placeholder test classes (tests added with each phase)
# ===========================================================================

class TestPhase4Build:
    """Tests for phased build, enrich, generated, seed."""

    def test_phases_ordered_correctly(self):
        """Phase numbers should produce correct ordering."""
        from de_funk.config.domain.build import parse_build_config

        model_config = {
            "build": {
                "phases": {
                    2: {"tables": ["fact_events"]},
                    1: {"tables": ["dim_entity"]},
                },
            },
            "tables": {"dim_entity": {}, "fact_events": {}},
        }
        build = parse_build_config(model_config)
        assert build["phases"][0]["phase_num"] == 1
        assert build["phases"][0]["tables"] == ["dim_entity"]
        assert build["phases"][1]["phase_num"] == 2
        assert build["phases"][1]["tables"] == ["fact_events"]

    def test_phase_flags_extracted(self):
        """Phase-level persist and enrich flags should be extracted."""
        from de_funk.config.domain.build import parse_build_config

        model_config = {
            "build": {
                "phases": {
                    1: {"tables": ["fact_a"], "persist": True},
                    2: {"tables": ["dim_a"], "persist": True, "enrich": True},
                },
            },
            "tables": {"fact_a": {}, "dim_a": {}},
        }
        build = parse_build_config(model_config)
        assert build["phases"][0]["enrich"] is False
        assert build["phases"][1]["enrich"] is True

    def test_seed_table_from_data(self):
        """Inline data block should be extractable from static tables."""
        from de_funk.config.domain.build import extract_seed_data

        table_config = {
            "static": True,
            "data": [
                {"code": "A", "name": "Alpha"},
                {"code": "B", "name": "Beta"},
            ],
        }
        rows = extract_seed_data(table_config)
        assert len(rows) == 2
        assert rows[0]["code"] == "A"
        assert rows[1]["name"] == "Beta"

    def test_seed_empty_for_non_static(self):
        """Non-static table should return empty seed data."""
        from de_funk.config.domain.build import extract_seed_data

        table_config = {"schema": [["col", "string"]]}
        rows = extract_seed_data(table_config)
        assert rows == []

    def test_table_build_flags(self):
        """Table-level build flags should be extracted."""
        from de_funk.config.domain.build import get_table_build_flags

        table_config = {
            "static": True,
            "generated": False,
            "transform": "distinct",
            "group_by": ["name"],
            "primary_key": ["entity_id"],
        }
        flags = get_table_build_flags(table_config)
        assert flags["static"] is True
        assert flags["generated"] is False
        assert flags["transform"] == "distinct"
        assert flags["group_by"] == ["name"]

    def test_enrich_single_source(self):
        """Single enrich spec should parse correctly."""
        from de_funk.config.domain.build import process_enrich_specs

        table_config = {
            "enrich": [
                {
                    "from": "fact_events",
                    "join": ["entity_id=entity_id"],
                    "columns": [
                        ["total_amount", "decimal(18,2)", True, "Total", {"derived": "SUM(amount)"}],
                    ],
                }
            ]
        }
        specs = process_enrich_specs(table_config)
        assert len(specs) == 1
        assert specs[0]["type"] == "join"
        assert specs[0]["from"] == "fact_events"
        assert specs[0]["join"] == [("entity_id", "entity_id")]

    def test_enrich_with_filter(self):
        """Enrich spec with filter should preserve the filter."""
        from de_funk.config.domain.build import process_enrich_specs

        table_config = {
            "enrich": [
                {
                    "from": "fact_budget_events",
                    "join": ["dept_id=org_unit_id"],
                    "filter": "event_type = 'APPROPRIATION'",
                    "columns": [["total", "decimal", True, "Total"]],
                }
            ]
        }
        specs = process_enrich_specs(table_config)
        assert specs[0]["filter"] == "event_type = 'APPROPRIATION'"

    def test_enrich_derived_columns(self):
        """Derived-only enrich block should be recognized."""
        from de_funk.config.domain.build import process_enrich_specs

        table_config = {
            "enrich": [
                {"derived": [["variance", "decimal", True, "Budget variance"]]}
            ]
        }
        specs = process_enrich_specs(table_config)
        assert len(specs) == 1
        assert specs[0]["type"] == "derived"

    def test_enrich_compact_lookup(self):
        """Compact enrich syntax should parse correctly."""
        from de_funk.config.domain.build import process_enrich_specs

        table_config = {
            "enrich": [
                {"join": "dim_property_class", "on": ["property_class=property_class_code"], "fields": ["property_category"]}
            ]
        }
        specs = process_enrich_specs(table_config)
        assert len(specs) == 1
        assert specs[0]["type"] == "lookup"
        assert specs[0]["join"] == "dim_property_class"
        assert specs[0]["fields"] == ["property_category"]

    def test_validate_build_catches_missing_table(self):
        """Validation should catch tables referenced in phases but not defined."""
        from de_funk.config.domain.build import validate_build_config

        model_config = {
            "build": {"phases": {1: {"tables": ["nonexistent_table"]}}},
            "tables": {"dim_entity": {}},
        }
        warnings = validate_build_config(model_config)
        assert any("nonexistent_table" in w for w in warnings)

    def test_loader_build_config_from_fixtures(self):
        """Loader should preserve build config from model.md fixtures."""
        from de_funk.config.domain import DomainConfigLoader
        from de_funk.config.domain.build import parse_build_config

        loader = DomainConfigLoader(FIXTURES_DIR)
        config = loader.load_model_config("test_model")
        build = parse_build_config(config)
        assert len(build["phases"]) == 2
        assert "dim_entity" in build["phases"][0]["tables"]
        assert "fact_events" in build["phases"][1]["tables"]


class TestPhase5Views:
    """Tests for derived and rollup view materialization."""

    def test_parse_derived_view(self):
        """Derived view config should have view_type, from, assumptions."""
        from de_funk.config.domain.views import parse_view_config

        view_config = {
            "view_type": "derived",
            "from": "fact_events",
            "assumptions": {
                "factor": {
                    "type": "decimal(10,6)",
                    "default": 1.0,
                    "source": "dim_entity.factor",
                    "join_on": ["entity_id=entity_id"],
                }
            },
            "schema": [
                ["entity_id", "integer", False, "PK"],
                ["adjusted_amount", "decimal(18,2)", False, "Adjusted",
                 {"derived": "amount * factor"}],
            ],
        }
        parsed = parse_view_config(view_config)
        assert parsed["view_type"] == "derived"
        assert parsed["from"] == "fact_events"
        assert "factor" in parsed["assumptions"]
        assert parsed["assumptions"]["factor"]["default"] == 1.0
        assert parsed["assumptions"]["factor"]["join_on"] == [("entity_id", "entity_id")]

    def test_parse_rollup_view(self):
        """Rollup view should have grain and aggregate columns."""
        from de_funk.config.domain.views import parse_view_config

        view_config = {
            "view_type": "rollup",
            "from": "fact_events",
            "grain": ["entity_id", "category"],
            "schema": [
                ["entity_id", "integer", False, "Entity"],
                ["category", "string", False, "Category"],
                ["event_count", "integer", False, "Count",
                 {"derived": "COUNT(DISTINCT event_id)"}],
            ],
        }
        parsed = parse_view_config(view_config)
        assert parsed["view_type"] == "rollup"
        assert parsed["grain"] == ["entity_id", "category"]

    def test_view_chain_resolution(self):
        """Views referencing other views should be ordered correctly."""
        from de_funk.config.domain.views import resolve_view_chain

        views = {
            "view_estimated_tax": {"from": "view_equalized_values"},
            "view_equalized_values": {"from": "fact_assessed_values"},
            "view_township_summary": {"from": "fact_assessed_values"},
        }
        order = resolve_view_chain(views)
        # view_equalized_values must come before view_estimated_tax
        idx_eq = order.index("view_equalized_values")
        idx_tax = order.index("view_estimated_tax")
        assert idx_eq < idx_tax

    def test_view_chain_independent_views(self):
        """Views with no dependencies on each other should all appear."""
        from de_funk.config.domain.views import resolve_view_chain

        views = {
            "view_a": {"from": "fact_table"},
            "view_b": {"from": "fact_table"},
        }
        order = resolve_view_chain(views)
        assert len(order) == 2

    def test_assumption_override(self):
        """Model assumption binding should override base defaults."""
        from de_funk.config.domain.views import assemble_views

        base_views = {
            "_view_equalized": {
                "type": "derived",
                "from": "_fact_values",
                "assumptions": {
                    "eq_factor": {
                        "type": "decimal(10,6)",
                        "default": 1.0,
                        "source": "base default",
                    }
                },
            }
        }
        model_views = {
            "view_equalized": {
                "assumptions": {
                    "eq_factor": {
                        "source": "dim_tax_district.equalization_factor",
                        "join_on": ["township=township"],
                    }
                }
            }
        }
        merged = assemble_views(model_views, base_views)
        eq = merged["view_equalized"]["assumptions"]["eq_factor"]
        # Source overridden by model
        assert eq["source"] == "dim_tax_district.equalization_factor"
        # Type preserved from base
        assert eq["type"] == "decimal(10,6)"
        # Default preserved from base
        assert eq["default"] == 1.0

    def test_get_derived_columns(self):
        """Should extract columns with {derived: expr} from schema."""
        from de_funk.config.domain.views import get_derived_columns

        schema = [
            ["entity_id", "integer", False, "PK"],
            ["amount", "decimal(18,2)", False, "Raw amount"],
            ["adjusted", "decimal(18,2)", False, "Adjusted",
             {"derived": "amount * factor"}],
            ["total", "decimal(18,2)", False, "Total",
             {"derived": "SUM(amount)"}],
        ]
        derived = get_derived_columns(schema)
        assert len(derived) == 2
        assert derived[0]["name"] == "adjusted"
        assert derived[0]["expression"] == "amount * factor"
        assert derived[1]["name"] == "total"

    def test_view_from_loader_fixtures(self):
        """Loader should discover and assemble views from fixtures."""
        from de_funk.config.domain import DomainConfigLoader
        from de_funk.config.domain.views import parse_view_config

        loader = DomainConfigLoader(FIXTURES_DIR)
        config = loader.load_model_config("test_model")
        views = config.get("views", {})
        assert "view_entity_summary" in views

        view = views["view_entity_summary"]
        parsed = parse_view_config(view)
        assert parsed["view_type"] == "rollup"
        assert parsed["from"] == "fact_events"

    def test_view_measures_preserved(self):
        """View measures should be preserved through assembly."""
        from de_funk.config.domain import DomainConfigLoader

        loader = DomainConfigLoader(FIXTURES_DIR)
        config = loader.load_model_config("test_model")
        view = config["views"]["view_entity_summary"]
        measures = view.get("measures", [])
        measure_names = [m[0] for m in measures if isinstance(m, list)]
        assert "grand_total" in measure_names


class TestPhase6Federation:
    """Tests for cross-model union tables."""

    def test_federation_participant_detected(self):
        """Model with federation.enabled should be recognized."""
        from de_funk.config.domain.federation import is_federation_participant

        config = {"federation": {"enabled": True, "union_key": "domain_source"}}
        assert is_federation_participant(config) is True

    def test_non_federation_model(self):
        """Model without federation should not be flagged."""
        from de_funk.config.domain.federation import is_federation_participant

        config = {"model": "plain_model", "tables": {}}
        assert is_federation_participant(config) is False

    def test_federation_model_detected(self):
        """Model with federation.children is a federation model."""
        from de_funk.config.domain.federation import is_federation_model

        config = {
            "federation": {
                "union_key": "domain_source",
                "children": [
                    {"model": "municipal_finance", "domain_source": "chicago"},
                ],
            }
        }
        assert is_federation_model(config) is True

    def test_union_of_extracted(self):
        """Tables with union_of should be extracted correctly."""
        from de_funk.config.domain.federation import get_federation_config

        config = {
            "federation": {
                "union_key": "domain_source",
                "children": [{"model": "child_a", "domain_source": "a"}],
            },
            "tables": {
                "v_all_entries": {
                    "union_of": [
                        "child_a.fact_entries",
                        "child_b.fact_entries",
                    ],
                    "schema": "inherited",
                    "primary_key": ["entry_id"],
                },
                "dim_regular": {"schema": [["col", "string"]]},
            },
        }
        fed = get_federation_config(config)
        assert "v_all_entries" in fed["union_tables"]
        assert len(fed["union_tables"]["v_all_entries"]["union_of"]) == 2
        assert fed["union_tables"]["v_all_entries"]["schema_mode"] == "inherited"
        assert "dim_regular" not in fed["union_tables"]

    def test_resolve_union_references(self):
        """union_of references should parse to model+table pairs."""
        from de_funk.config.domain.federation import resolve_union_references

        refs = resolve_union_references([
            "municipal_finance.fact_ledger_entries",
            "corporate_finance.fact_financial_statements",
        ])
        assert len(refs) == 2
        assert refs[0] == {"model": "municipal_finance", "table": "fact_ledger_entries"}
        assert refs[1] == {"model": "corporate_finance", "table": "fact_financial_statements"}

    def test_validate_federation_missing_child(self):
        """Validation should warn about children not in depends_on."""
        from de_funk.config.domain.federation import validate_federation

        config = {
            "depends_on": ["temporal"],
            "federation": {
                "children": [{"model": "child_a", "domain_source": "a"}],
            },
            "tables": {},
        }
        warnings = validate_federation(config)
        assert any("child_a" in w and "depends_on" in w for w in warnings)

    def test_validate_federation_valid(self):
        """Valid federation config should produce no warnings."""
        from de_funk.config.domain.federation import validate_federation

        config = {
            "depends_on": ["child_a"],
            "federation": {
                "children": [{"model": "child_a", "domain_source": "a"}],
            },
            "tables": {
                "v_all": {
                    "union_of": ["child_a.fact_entries"],
                    "schema": "inherited",
                }
            },
        }
        warnings = validate_federation(config)
        assert len(warnings) == 0

    def test_real_federation_model(self):
        """Real accounting_federation should parse correctly."""
        from de_funk.config.domain import DomainConfigLoader
        from de_funk.config.domain.federation import get_federation_config

        loader = DomainConfigLoader(Path(__file__).resolve().parent.parent.parent / "domains")
        try:
            config = loader.load_model_config("accounting_federation")
        except FileNotFoundError:
            pytest.skip("domains not available")

        fed = get_federation_config(config)
        assert fed["is_federation_model"] is True
        assert fed["union_key"] == "domain_source"
        assert len(fed["children"]) >= 2
        assert len(fed["union_tables"]) >= 1


class TestPhase7Graph:
    """Tests for auto_edges, optional edges, paths."""

    def test_parse_edge_basic(self):
        """Basic edge should parse correctly."""
        from de_funk.config.domain.graph import parse_edge

        edge = ["prices_to_stock", "fact_prices", "dim_stock",
                ["security_id=security_id"], "many_to_one", "null"]
        parsed = parse_edge(edge)
        assert parsed["name"] == "prices_to_stock"
        assert parsed["from"] == "fact_prices"
        assert parsed["to"] == "dim_stock"
        assert parsed["on"] == [("security_id", "security_id")]
        assert parsed["type"] == "many_to_one"
        assert parsed["optional"] is False

    def test_parse_edge_cross_model(self):
        """Cross-model edge should detect target model."""
        from de_funk.config.domain.graph import parse_edge

        edge = ["stock_to_company", "dim_stock", "company.dim_company",
                ["company_id=company_id"], "many_to_one", "company"]
        parsed = parse_edge(edge)
        assert parsed["cross_model"] is True
        assert parsed["target_model"] == "company"
        assert parsed["target_table"] == "dim_company"

    def test_parse_edge_optional(self):
        """Edge with optional: true should be detected."""
        from de_funk.config.domain.graph import parse_edge

        edge = ["entry_to_contract", "fact_entries", "dim_contract",
                ["contract_id=contract_id"], "many_to_one", "null",
                {"optional": True}]
        parsed = parse_edge(edge)
        assert parsed["optional"] is True

    def test_parse_graph_config(self):
        """Full graph config should be parsed from model config."""
        from de_funk.config.domain.graph import parse_graph_config

        model_config = {
            "graph": {
                "edges": [
                    ["e1", "fact_a", "dim_b", ["b_id=b_id"], "many_to_one", "null"],
                    ["e2", "fact_a", "dim_c", ["c_id=c_id"], "many_to_one", "null"],
                ],
                "paths": {
                    "a_to_c": {
                        "description": "A to C via B",
                        "steps": [
                            {"from": "fact_a", "to": "dim_b", "via": "b_id"},
                            {"from": "dim_b", "to": "dim_c", "via": "c_id"},
                        ],
                    }
                },
            }
        }
        parsed = parse_graph_config(model_config)
        assert len(parsed["edges"]) == 2
        assert "a_to_c" in parsed["paths"]
        assert len(parsed["paths"]["a_to_c"]["steps"]) == 2

    def test_resolve_auto_edges(self):
        """Auto-edges should generate edges for matching fact tables."""
        from de_funk.config.domain.graph import resolve_auto_edges

        model_config = {
            "auto_edges": [
                ["date_id", "temporal.dim_calendar", ["date_id=date_id"],
                 "many_to_one", "temporal"],
            ]
        }
        tables = {
            "fact_events": {
                "type": "fact",
                "table_type": "fact",
                "schema": [
                    ["event_id", "integer", False, "PK"],
                    ["date_id", "integer", False, "FK to calendar"],
                ],
            },
            "dim_entity": {
                "type": "dimension",
                "table_type": "dimension",
                "schema": [
                    ["entity_id", "integer", False, "PK"],
                ],
            },
        }
        generated = resolve_auto_edges(model_config, tables)
        assert len(generated) == 1
        assert generated[0]["from"] == "fact_events"
        assert "dim_calendar" in generated[0]["name"]
        assert generated[0]["auto_generated"] is True

    def test_auto_edge_skip_missing_column(self):
        """Auto-edge should be skipped if fact table lacks FK column."""
        from de_funk.config.domain.graph import resolve_auto_edges

        model_config = {
            "auto_edges": [
                ["location_id", "geo._dim_location", ["location_id=location_id"],
                 "many_to_one", "geo"],
            ]
        }
        tables = {
            "fact_events": {
                "table_type": "fact",
                "schema": [["event_id", "integer", False, "PK"]],
            },
        }
        generated = resolve_auto_edges(model_config, tables)
        assert len(generated) == 0

    def test_path_validation(self):
        """Path steps should have via column."""
        from de_funk.config.domain.graph import validate_paths

        paths = {
            "broken_path": {
                "steps": [{"from": "a", "to": "b"}],  # missing via
            }
        }
        warnings = validate_paths(paths, [])
        assert any("via" in w for w in warnings)

    def test_loader_graph_from_fixtures(self):
        """Loader should preserve graph config from model.md."""
        from de_funk.config.domain import DomainConfigLoader
        from de_funk.config.domain.graph import parse_graph_config

        loader = DomainConfigLoader(FIXTURES_DIR)
        config = loader.load_model_config("test_model")
        graph = parse_graph_config(config)
        assert len(graph["edges"]) >= 2
        assert "event_to_type" in graph["paths"]


class TestPhase8Migration:
    """Tests for domains/ directory (v4 format) after migration."""

    DOMAINS_DIR = Path(__file__).resolve().parent.parent.parent / "domains"

    def test_domains_dir_has_v4_structure(self):
        """domains/ should have v4 structure (_base, models)."""
        if not self.DOMAINS_DIR.exists():
            pytest.skip("domains not available")
        assert (self.DOMAINS_DIR / "_base").is_dir()
        assert (self.DOMAINS_DIR / "models").is_dir()
        # _model_guides_ moved to docs/guides/yaml/

    def test_all_168_files_parse(self):
        """Every .md file in domains/ should parse without error."""
        if not self.DOMAINS_DIR.exists():
            pytest.skip("domains not available")
        from de_funk.config.domain.extends import parse_front_matter

        errors = []
        md_files = sorted(self.DOMAINS_DIR.rglob("*.md"))
        for md_file in md_files:
            if md_file.name.lower() == "readme.md":
                continue
            try:
                config = parse_front_matter(md_file)
                if not config:
                    errors.append(f"{md_file.name}: empty front matter")
            except Exception as e:
                errors.append(f"{md_file.name}: {e}")

        assert len(errors) == 0, f"Parse errors:\n" + "\n".join(errors)
        assert len(md_files) >= 100, f"Expected 100+ files, got {len(md_files)}"

    def test_build_order_resolves(self):
        """Topological sort should succeed for all models."""
        if not self.DOMAINS_DIR.exists():
            pytest.skip("domains not available")
        from de_funk.config.domain import DomainConfigLoader

        loader = DomainConfigLoader(self.DOMAINS_DIR)
        models = loader.list_models()
        assert len(models) >= 5, f"Expected 5+ models, got {len(models)}"

        build_order = loader.get_build_order()
        assert len(build_order) == len(models)
        assert set(build_order) == set(models)

    def test_factory_returns_v4_for_domains(self):
        """get_domain_loader should return V4 loader for domains/."""
        if not self.DOMAINS_DIR.exists():
            pytest.skip("domains not available")
        from de_funk.config.domain import get_domain_loader, DomainConfigLoader

        loader = get_domain_loader(self.DOMAINS_DIR)
        assert isinstance(loader, DomainConfigLoader)

    def test_cross_model_extends_resolve(self):
        """Extends references across models should resolve."""
        if not self.DOMAINS_DIR.exists():
            pytest.skip("domains not available")
        from de_funk.config.domain import DomainConfigLoader

        loader = DomainConfigLoader(self.DOMAINS_DIR)
        models = loader.list_models()

        # Try loading each model — extends failures would raise
        errors = []
        for model_name in models:
            try:
                config = loader.load_model_config(model_name)
                assert "tables" in config or "views" in config or "sources" in config, \
                    f"{model_name}: no tables, views, or sources"
            except Exception as e:
                errors.append(f"{model_name}: {e}")

        assert len(errors) == 0, f"Load errors:\n" + "\n".join(errors)

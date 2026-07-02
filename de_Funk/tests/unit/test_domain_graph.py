"""Tests for DomainGraph — queryable join graph built from EdgeSpec."""
import pytest
from de_funk.core.graph import DomainGraph


@pytest.fixture
def sample_models():
    """Create sample models with graph edges for testing."""
    return {
        "securities.stocks": {
            "model": "securities.stocks",
            "depends_on": ["temporal", "corporate.entity"],
            "graph": {
                "edges": [
                    ["prices_to_calendar", "fact_stock_prices", "temporal.dim_calendar", ["date_id=date_id"], "many_to_one", "temporal"],
                    ["stock_to_company", "dim_stock", "corporate.entity.dim_company", ["company_id=company_id"], "many_to_one", "corporate.entity"],
                    ["stock_to_prices", "dim_stock", "fact_stock_prices", ["security_id=security_id"], "one_to_many", None],
                ],
            },
        },
        "temporal": {
            "model": "temporal",
            "depends_on": [],
            "graph": {"edges": []},
        },
        "corporate.entity": {
            "model": "corporate.entity",
            "depends_on": ["temporal"],
            "graph": {
                "edges": [
                    ["company_to_calendar", "dim_company", "temporal.dim_calendar", ["date_id=date_id"], "many_to_one", "temporal"],
                ],
            },
        },
    }


@pytest.fixture
def graph(sample_models):
    return DomainGraph(sample_models)


class TestGraphBuilding:
    def test_builds_from_models(self, graph):
        assert len(graph.all_tables()) > 0

    def test_discovers_tables(self, graph):
        tables = graph.all_tables()
        assert "dim_stock" in tables
        assert "fact_stock_prices" in tables
        assert "dim_calendar" in tables
        assert "dim_company" in tables

    def test_bidirectional_edges(self, graph):
        # If dim_stock → fact_stock_prices exists, reverse should too
        neighbors_of_stock = graph.neighbors("dim_stock")
        assert "fact_stock_prices" in neighbors_of_stock

        neighbors_of_prices = graph.neighbors("fact_stock_prices")
        assert "dim_stock" in neighbors_of_prices

    def test_all_edges_deduped(self, graph):
        edges = graph.all_edges()
        # Each edge should appear once (not both A→B and B→A)
        assert len(edges) > 0
        pairs = [(e[0], e[1]) for e in edges]
        reverse_pairs = [(e[1], e[0]) for e in edges]
        # No edge should have both (A,B) and (B,A)
        for p in pairs:
            assert p not in reverse_pairs


class TestJoinPaths:
    def test_direct_join(self, graph):
        path = graph.find_join_path("dim_stock", "fact_stock_prices")
        assert path is not None
        assert len(path) == 1

    def test_multi_hop_join(self, graph):
        # dim_stock → fact_stock_prices → dim_calendar (2 hops)
        path = graph.find_join_path("dim_stock", "dim_calendar")
        assert path is not None
        assert len(path) >= 1

    def test_no_path(self, graph):
        path = graph.find_join_path("dim_stock", "nonexistent_table")
        assert path is None

    def test_same_table(self, graph):
        path = graph.find_join_path("dim_stock", "dim_stock")
        assert path == []

    def test_distance(self, graph):
        assert graph.distance("dim_stock", "fact_stock_prices") == 1
        assert graph.distance("dim_stock", "nonexistent") == -1


class TestDomainScoping:
    def test_reachable_domains(self, graph):
        reachable = graph.reachable_domains({"securities.stocks"})
        assert "temporal" in reachable
        assert "corporate.entity" in reachable

    def test_reachable_domains_no_deps(self, graph):
        reachable = graph.reachable_domains({"temporal"})
        assert reachable == {"temporal"}

    def test_domain_for_table(self, graph):
        domain = graph.domains_for_table("dim_stock")
        assert domain == "securities.stocks"


class TestConnectedComponents:
    def test_connected_components(self, graph):
        components = graph.connected_components()
        assert len(components) >= 1
        # All tables should be in some component
        all_tables = set()
        for comp in components:
            all_tables.update(comp)
        assert "dim_stock" in all_tables

    def test_neighbors(self, graph):
        neighbors = graph.neighbors("dim_stock")
        assert len(neighbors) >= 1
        assert isinstance(neighbors, list)


class TestEmptyGraph:
    def test_empty_graph(self):
        graph = DomainGraph()
        assert graph.all_tables() == []
        assert graph.all_edges() == []
        assert graph.connected_components() == []

    def test_no_path_empty(self):
        graph = DomainGraph()
        assert graph.find_join_path("a", "b") is None


class TestIntegration:
    def test_defunk_builds_graph(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        assert isinstance(app.graph, DomainGraph)
        tables = app.graph.all_tables()
        assert len(tables) > 0
        edges = app.graph.all_edges()
        assert len(edges) > 0

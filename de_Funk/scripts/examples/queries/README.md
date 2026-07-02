# Query Examples

This directory contains examples demonstrating various query capabilities in de_Funk.

## Examples

### 01_auto_join.py
Demonstrates transparent auto-join functionality where the system automatically figures out joins based on requested columns.

**Key Features:**
- Automatic join detection
- Materialized view optimization
- Column-based query interface

**Run:**
```bash
python -m scripts.examples.queries.01_auto_join
```

### 02_query_planner.py
Shows how to use the GraphQueryPlanner for dynamic joins without requiring materialized views.

**Key Features:**
- Dynamic table enrichment
- Graph-based join planning
- Cross-model queries

**Run:**
```bash
python -m scripts.examples.queries.02_query_planner
```

### 03_session_queries.py
Demonstrates UniversalSession usage for ad-hoc data analysis.

**Key Features:**
- Model-agnostic data access
- Cross-model queries and joins
- Pandas integration
- Flexible filtering and aggregation

**Run:**
```bash
python -m scripts.examples.queries.03_session_queries
```

## Prerequisites

- Built silver layer models (run `python -m scripts.build.build_all_models`)
- DuckDB or Spark backend configured
- Sample data loaded

## Related Documentation

- `/CLAUDE.md` - Main documentation
- `/scripts/examples/README.md` - Examples overview
- `/docs/guide/` - Detailed guides

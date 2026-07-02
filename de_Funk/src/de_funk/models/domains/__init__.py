"""
Domain models - business-specific data models organized by domain.

This is the unified location for ALL model implementations (v2.6+).

Domain Hierarchy (models/domains/):
- foundation/: Core infrastructure models (temporal, geospatial)
- securities/: Tradable financial instruments (stocks, options, etfs, futures)
- corporate/: Corporate legal entities (company)
- municipal/: Government/municipal data (city_finance)
- economic/: Economic indicators (macro)

Configuration files are in domains/ (markdown with YAML front matter).
Python implementations are in models/domains/{category}/{model}/.

Builder discovery uses:
    BuilderRegistry.discover(repo_root / "models" / "domains")
"""

__all__ = []

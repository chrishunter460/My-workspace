"""
Alpha Vantage Data Provider.

Provides stock market data from Alpha Vantage API:
- Company fundamentals (OVERVIEW)
- Daily time series (TIME_SERIES_DAILY_ADJUSTED)
- Financial statements (INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS)

Configuration loaded from markdown documentation (single source of truth):
- Data Sources/Providers/Alpha Vantage.md
- Data Sources/Endpoints/Alpha Vantage/**/*.md

API Key Required:
Set ALPHA_VANTAGE_API_KEYS environment variable with your API key(s).
Pro tier: 75 requests/minute (1.25/sec)
Free tier: 25 requests/day, 5 requests/minute

Usage:
    from de_funk.pipelines.providers.alpha_vantage import (
        AlphaVantageProvider,
        create_alpha_vantage_provider,
    )
    from de_funk.pipelines.base import IngestorEngine

    # Create provider
    provider = create_alpha_vantage_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Set tickers and run
    provider.set_tickers(["AAPL", "MSFT", "GOOGL"])
    results = engine.run(work_items=["prices", "reference"])
"""

from de_funk.pipelines.providers.alpha_vantage.alpha_vantage_provider import (
    AlphaVantageProvider,
    create_alpha_vantage_provider,
)

__all__ = [
    'AlphaVantageProvider',
    'create_alpha_vantage_provider',
]

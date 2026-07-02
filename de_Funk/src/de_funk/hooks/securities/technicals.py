"""Compute technical indicators (RSI, MACD) post-build.

Registered as post_build hook for securities.stocks model.
Replaces the old StocksBuilder.post_build() class override.
"""
from de_funk.core.hooks import pipeline_hook
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@pipeline_hook("post_build", model="securities.stocks")
def compute_technicals(df, engine, config, result=None, **params):
    """Add technical indicators to fact_stock_prices."""
    periods = params.get("periods", [14, 30])
    logger.info(f"Computing technical indicators with periods={periods}")

    # Will use engine.window() when Engine is implemented
    return result

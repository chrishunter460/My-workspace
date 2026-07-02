"""
Generate dim_calendar programmatically (no Bronze source).

Self-generating calendar dimension with all temporal attributes.

Trigger: custom_node_loading
Domain: temporal
"""
from __future__ import annotations

from typing import Any, Optional
from de_funk.core.hooks import pipeline_hook
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@pipeline_hook("custom_node_loading", model="temporal")
def generate_calendar(engine=None, config=None, model=None,
                      node_id=None, node_config=None, **params):
    """Generate dim_calendar if this is the calendar node.

    Trigger: custom_node_loading
    Domain: temporal
    """
    if node_id != "dim_calendar":
        return None

    calendar_config = config.get('calendar_config', {}) if config else {}
    start = calendar_config.get('start_date', '2000-01-01')
    end = calendar_config.get('end_date', '2050-12-31')
    fiscal_start = calendar_config.get('fiscal_year_start_month', 1)

    logger.info(f"Generating dim_calendar: {start} to {end}")

    backend = None
    if model and hasattr(model, 'backend'):
        backend = model.backend
    elif engine and hasattr(engine, 'backend'):
        backend = engine.backend

    if backend == 'spark':
        return _generate_spark(model, start, end, fiscal_start)
    else:
        return _generate_pandas(start, end, fiscal_start)


def _generate_spark(model, start: str, end: str, fiscal_start: int):
    """Generate calendar via Spark SQL."""
    from pyspark.sql import functions as F

    spark = model.connection

    df = spark.sql(f"""
        SELECT explode(sequence(
            to_date('{start}'), to_date('{end}'), interval 1 day
        )) as date
    """)

    df = df.select(
        F.date_format("date", "yyyyMMdd").cast("int").alias("date_id"),
        F.col("date"),
        F.year("date").alias("year"),
        F.quarter("date").alias("quarter"),
        F.month("date").alias("month"),
        F.date_format("date", "MMMM").alias("month_name"),
        F.date_format("date", "MMM").alias("month_abbr"),
        F.weekofyear("date").alias("week_of_year"),
        F.dayofmonth("date").alias("day_of_month"),
        F.dayofweek("date").alias("day_of_week"),
        F.date_format("date", "EEEE").alias("day_of_week_name"),
        F.date_format("date", "EEE").alias("day_of_week_abbr"),
        F.dayofyear("date").alias("day_of_year"),
        (F.dayofweek("date").isin([1, 7])).alias("is_weekend"),
        (~F.dayofweek("date").isin([1, 7])).alias("is_weekday"),
        (F.dayofmonth("date") == 1).alias("is_month_start"),
        (F.date_add(F.last_day("date"), 0) == F.col("date")).alias("is_month_end"),
        ((F.month("date").isin([1, 4, 7, 10])) & (F.dayofmonth("date") == 1)).alias("is_quarter_start"),
        ((F.month("date").isin([3, 6, 9, 12])) & (F.date_add(F.last_day("date"), 0) == F.col("date"))).alias("is_quarter_end"),
        ((F.month("date") == 1) & (F.dayofmonth("date") == 1)).alias("is_year_start"),
        ((F.month("date") == 12) & (F.dayofmonth("date") == 31)).alias("is_year_end"),
        F.when(F.month("date") >= fiscal_start, F.year("date"))
         .otherwise(F.year("date") - 1).alias("fiscal_year"),
        F.when(F.month("date") >= fiscal_start,
               F.ceil((F.month("date") - fiscal_start + 1) / 3))
         .otherwise(F.ceil((F.month("date") + 12 - fiscal_start + 1) / 3)).cast("int").alias("fiscal_quarter"),
        F.when(F.month("date") >= fiscal_start,
               F.month("date") - fiscal_start + 1)
         .otherwise(F.month("date") + 12 - fiscal_start + 1).alias("fiscal_month"),
        F.dayofmonth(F.last_day("date")).alias("days_in_month"),
        F.date_format("date", "yyyy-MM").alias("year_month"),
        F.concat(F.year("date"), F.lit("-Q"), F.quarter("date")).alias("year_quarter"),
        F.date_format("date", "yyyy-MM-dd").alias("date_str"),
    )

    logger.info(f"Generated {df.count():,} calendar rows")
    return df


def _generate_pandas(start: str, end: str, fiscal_start: int):
    """Generate calendar via pandas."""
    import pandas as pd

    dates = pd.date_range(start=start, end=end, freq='D')
    df = pd.DataFrame({'date': dates})
    df['date_id'] = df['date'].dt.strftime('%Y%m%d').astype(int)
    df['year'] = df['date'].dt.year
    df['quarter'] = df['date'].dt.quarter
    df['month'] = df['date'].dt.month
    df['month_name'] = df['date'].dt.month_name()
    df['month_abbr'] = df['date'].dt.strftime('%b')
    df['week_of_year'] = df['date'].dt.isocalendar().week
    df['day_of_month'] = df['date'].dt.day
    df['day_of_week'] = df['date'].dt.dayofweek + 1
    df['day_of_week_name'] = df['date'].dt.day_name()
    df['day_of_week_abbr'] = df['date'].dt.strftime('%a')
    df['day_of_year'] = df['date'].dt.dayofyear
    df['is_weekend'] = df['date'].dt.dayofweek >= 5
    df['is_weekday'] = df['date'].dt.dayofweek < 5
    df['is_month_start'] = df['date'].dt.is_month_start
    df['is_month_end'] = df['date'].dt.is_month_end
    df['is_quarter_start'] = df['date'].dt.is_quarter_start
    df['is_quarter_end'] = df['date'].dt.is_quarter_end
    df['is_year_start'] = df['date'].dt.is_year_start
    df['is_year_end'] = df['date'].dt.is_year_end
    df['fiscal_year'] = df.apply(
        lambda r: r['year'] if r['month'] >= fiscal_start else r['year'] - 1, axis=1)
    df['fiscal_quarter'] = df.apply(
        lambda r: ((r['month'] - fiscal_start) % 12) // 3 + 1, axis=1)
    df['fiscal_month'] = df.apply(
        lambda r: (r['month'] - fiscal_start) % 12 + 1, axis=1)
    df['days_in_month'] = df['date'].dt.days_in_month
    df['year_month'] = df['date'].dt.strftime('%Y-%m')
    df['year_quarter'] = df['year'].astype(str) + '-Q' + df['quarter'].astype(str)
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')

    logger.info(f"Generated {len(df):,} calendar rows")
    return df

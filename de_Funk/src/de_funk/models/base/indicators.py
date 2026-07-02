"""
Technical Indicators Library.

Maps indicator short codes to their full definitions and Spark window implementations.
Used by DomainModel._build_window_node() to drive transform: window table builds.

Usage in domain schema:
    - [sma_20,  double, true, "20-day SMA",  {indicator: sma,       period: 20, source: adjusted_close}]
    - [rsi_14,  double, true, "14-day RSI",  {indicator: rsi,       period: 14, source: adjusted_close}]
    - [atr_14,  double, true, "14-day ATR",  {indicator: atr,       period: 14}]
    - [bollinger_upper, double, true, "Upper BB", {indicator: bollinger, band: upper, period: 20}]
    - [macd,    double, true, "MACD line",   {indicator: macd_line, fast: 12, slow: 26}]

Schema column order matters for dependent indicators:
    sma must precede bollinger (bollinger reads sma_<period> column)
    ema_12, ema_26 must precede macd_line
    macd must precede macd_signal
    macd_signal must precede macd_histogram
    volume_sma_<N> must precede volume_ratio
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Indicator Catalog
# Every indicator an analyst can declare in a window-transform schema.
# ---------------------------------------------------------------------------

INDICATOR_CATALOG: Dict[str, Dict[str, Any]] = {

    "sma": {
        "name": "Simple Moving Average",
        "description": (
            "Rolling arithmetic mean of `source` over the last `period` bars. "
            "All bars weighted equally. Smooth but lags price action."
        ),
        "params": {
            "period": {"type": "int", "required": True,
                       "description": "Lookback window in trading days (e.g. 20, 50, 200)"},
            "source": {"type": "str", "required": True,
                       "description": "Column to average (adjusted_close, close, volume, …)"},
        },
        "example": "{indicator: sma, period: 20, source: adjusted_close}",
    },

    "ema": {
        "name": "Exponential Moving Average",
        "description": (
            "Weighted rolling mean that places more weight on recent bars. "
            "Smoothing factor α = 2/(period+1). Implemented as a windowed "
            "weighted sum over 3×period bars — converges to true EMA after "
            "~5×period bars of warm-up data."
        ),
        "params": {
            "period": {"type": "int", "required": True,
                       "description": "Smoothing period (standard: 12, 26)"},
            "source": {"type": "str", "required": True,
                       "description": "Column to smooth (adjusted_close, close)"},
        },
        "example": "{indicator: ema, period: 12, source: adjusted_close}",
    },

    "rsi": {
        "name": "Relative Strength Index",
        "description": (
            "Momentum oscillator ranging 0–100. "
            "RS = avg_gain / avg_loss over `period` bars; RSI = 100 − 100/(1+RS). "
            "Values >70 indicate overbought; <30 oversold. "
            "Returns 50 (neutral) when avg_loss is zero."
        ),
        "params": {
            "period": {"type": "int", "required": True,
                       "description": "Lookback window (standard: 14)"},
            "source": {"type": "str", "required": True,
                       "description": "Price column for period-over-period change"},
        },
        "example": "{indicator: rsi, period: 14, source: adjusted_close}",
    },

    "atr": {
        "name": "Average True Range",
        "description": (
            "Volatility indicator measuring price range over `period` bars. "
            "True Range = max(high−low, |high−prev_close|, |low−prev_close|). "
            "ATR = rolling SMA of TR. "
            "Requires high, low, and close columns in the source table."
        ),
        "params": {
            "period": {"type": "int", "required": True,
                       "description": "SMA lookback for true range (standard: 14)"},
        },
        "example": "{indicator: atr, period: 14}",
    },

    "bollinger": {
        "name": "Bollinger Band",
        "description": (
            "Price envelope around a `period`-day SMA. "
            "Upper = SMA + std_dev×σ, Middle = SMA, Lower = SMA − std_dev×σ. "
            "Requires the SMA column (sma_<period>) to already be computed."
        ),
        "params": {
            "period": {"type": "int", "required": True,
                       "description": "SMA period to base bands on (standard: 20)"},
            "band":   {"type": "str", "required": True,
                       "description": "Which band to produce: upper | middle | lower"},
            "std_dev": {"type": "float", "required": False, "default": 2.0,
                        "description": "Standard deviation multiplier (default: 2)"},
            "source": {"type": "str", "required": False, "default": "adjusted_close",
                       "description": "Price column used for σ calculation"},
        },
        "example": "{indicator: bollinger, band: upper, period: 20, std_dev: 2}",
    },

    "volatility": {
        "name": "Annualized Volatility",
        "description": (
            "Standard deviation of `period`-bar daily returns scaled by √252. "
            "Represents the annualized 1-σ price dispersion. "
            "Used in position sizing, VaR, and Sharpe ratio calculations."
        ),
        "params": {
            "period": {"type": "int", "required": True,
                       "description": "Rolling window in trading days (e.g. 20, 60)"},
            "source": {"type": "str", "required": True,
                       "description": "Price column for return calculation"},
        },
        "example": "{indicator: volatility, period: 20, source: adjusted_close}",
    },

    "macd_line": {
        "name": "MACD Line",
        "description": (
            "Moving Average Convergence/Divergence line = EMA(fast) − EMA(slow). "
            "Positive when short-term momentum exceeds long-term. "
            "Requires the ema_<fast> and ema_<slow> columns to already be computed."
        ),
        "params": {
            "fast":   {"type": "int", "required": False, "default": 12,
                       "description": "Fast EMA period — must match an ema_<N> column"},
            "slow":   {"type": "int", "required": False, "default": 26,
                       "description": "Slow EMA period — must match an ema_<N> column"},
            "source": {"type": "str", "required": False, "default": "adjusted_close",
                       "description": "Price column the ema_<N> columns were built from"},
        },
        "example": "{indicator: macd_line, fast: 12, slow: 26}",
    },

    "macd_signal": {
        "name": "MACD Signal Line",
        "description": (
            "EMA of the MACD line over `signal` periods. "
            "Crossovers between MACD and signal are classic entry/exit signals. "
            "Requires the macd (or `macd_col`) column to already be computed."
        ),
        "params": {
            "signal":   {"type": "int", "required": False, "default": 9,
                         "description": "EMA period for the signal line (standard: 9)"},
            "macd_col": {"type": "str", "required": False, "default": "macd",
                         "description": "MACD line column to smooth"},
        },
        "example": "{indicator: macd_signal, signal: 9}",
    },

    "macd_histogram": {
        "name": "MACD Histogram",
        "description": (
            "Difference between the MACD line and its signal line. "
            "Growing histogram = strengthening momentum; shrinking = fading momentum. "
            "Requires both macd and macd_signal columns to already be computed."
        ),
        "params": {
            "macd_col":   {"type": "str", "required": False, "default": "macd",
                           "description": "MACD line column"},
            "signal_col": {"type": "str", "required": False, "default": "macd_signal",
                           "description": "MACD signal line column"},
        },
        "example": "{indicator: macd_histogram}",
    },

    "volume_ratio": {
        "name": "Volume Ratio",
        "description": (
            "Current volume divided by a rolling volume SMA. "
            "Values >1 indicate above-average activity (possible breakout/reversal). "
            "Requires the volume SMA column (`sma_col`) to already be computed."
        ),
        "params": {
            "sma_col": {"type": "str", "required": False, "default": "volume_sma_20",
                        "description": "Volume SMA column to normalize against"},
        },
        "example": "{indicator: volume_ratio, sma_col: volume_sma_20}",
    },
}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def apply_indicator(
    df,
    col_name: str,
    config: Dict[str, Any],
    partition_col: str,
    order_col: str,
):
    """
    Apply a single indicator to a DataFrame, returning df with `col_name` added.

    Args:
        df:            Source Spark DataFrame
        col_name:      Output column name (e.g. "sma_20")
        config:        Indicator config dict from schema options, e.g.
                       {indicator: sma, period: 20, source: adjusted_close}
        partition_col: Column to partition window by (e.g. security_id)
        order_col:     Column to order window by    (e.g. date_id)

    Returns:
        DataFrame with `col_name` column added (intermediates dropped)

    Raises:
        ValueError: If indicator code is unknown or required params are missing
    """
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    code = config.get("indicator", "")
    if code not in INDICATOR_CATALOG:
        raise ValueError(
            f"Unknown indicator '{code}'. "
            f"Available: {', '.join(sorted(INDICATOR_CATALOG))}. "
            f"See INDICATOR_CATALOG for full definitions."
        )

    entry = INDICATOR_CATALOG[code]
    logger.debug(f"  {col_name}: {entry['name']} {config}")

    window_base = Window.partitionBy(partition_col).orderBy(order_col)

    dispatch = {
        "sma":             _sma,
        "ema":             _ema,
        "rsi":             _rsi,
        "atr":             _atr,
        "bollinger":       _bollinger,
        "volatility":      _volatility,
        "macd_line":       _macd_line,
        "macd_signal":     _macd_signal,
        "macd_histogram":  _macd_histogram,
        "volume_ratio":    _volume_ratio,
    }
    return dispatch[code](df, col_name, config, window_base, F)


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

def _sma(df, col_name, cfg, window_base, F):
    period = cfg["period"]
    source = cfg["source"]
    w = window_base.rowsBetween(-(period - 1), 0)
    return df.withColumn(col_name, F.avg(source).over(w))


def _ema(df, col_name, cfg, window_base, F):
    """
    Windowed EMA approximation: weighted sum of last 3×period values.
    α = 2/(period+1).  Accurate to <1% after 5×period bars of warm-up.
    """
    period = cfg["period"]
    source = cfg["source"]
    alpha = 2.0 / (period + 1)
    window_size = period * 3

    weights = [alpha * ((1 - alpha) ** i) for i in range(window_size)]
    total_w = sum(weights)
    norm = [w / total_w for w in weights]

    expr = sum(
        F.lag(source, i).over(window_base) * norm[i]
        for i in range(window_size)
    )
    return df.withColumn(col_name, expr)


def _rsi(df, col_name, cfg, window_base, F):
    period = cfg["period"]
    source = cfg["source"]
    w = window_base.rowsBetween(-(period - 1), 0)

    df = df.withColumn("_prev", F.lag(source, 1).over(window_base))
    df = df.withColumn("_chg",  F.col(source) - F.col("_prev"))
    df = df.withColumn("_gain", F.when(F.col("_chg") > 0, F.col("_chg")).otherwise(0))
    df = df.withColumn("_loss", F.when(F.col("_chg") < 0, F.abs(F.col("_chg"))).otherwise(0))
    df = df.withColumn("_ag",   F.avg("_gain").over(w))
    df = df.withColumn("_al",   F.avg("_loss").over(w))
    df = df.withColumn("_rs",
        F.when(F.col("_al") != 0, F.col("_ag") / F.col("_al")).otherwise(None)
    )
    df = df.withColumn(col_name,
        F.when(F.col("_rs").isNotNull(), 100 - (100 / (1 + F.col("_rs")))).otherwise(50)
    )
    return df.drop("_prev", "_chg", "_gain", "_loss", "_ag", "_al", "_rs")


def _atr(df, col_name, cfg, window_base, F):
    period = cfg["period"]
    w = window_base.rowsBetween(-(period - 1), 0)

    df = df.withColumn("_pc", F.lag("close", 1).over(window_base))
    df = df.withColumn("_tr", F.greatest(
        F.col("high") - F.col("low"),
        F.abs(F.col("high") - F.col("_pc")),
        F.abs(F.col("low")  - F.col("_pc")),
    ))
    df = df.withColumn(col_name, F.avg("_tr").over(w))
    return df.drop("_pc", "_tr")


def _bollinger(df, col_name, cfg, window_base, F):
    period  = cfg["period"]
    band    = cfg["band"]   # upper | middle | lower
    std_dev = cfg.get("std_dev", 2.0)
    source  = cfg.get("source", "adjusted_close")
    sma_col = f"sma_{period}"
    w = window_base.rowsBetween(-(period - 1), 0)

    if sma_col not in df.columns:
        df = df.withColumn(sma_col, F.avg(source).over(w))

    sigma = F.stddev(source).over(w)
    if band == "upper":
        return df.withColumn(col_name, F.col(sma_col) + (std_dev * sigma))
    if band == "lower":
        return df.withColumn(col_name, F.col(sma_col) - (std_dev * sigma))
    # middle
    return df.withColumn(col_name, F.col(sma_col))


def _volatility(df, col_name, cfg, window_base, F):
    period = cfg["period"]
    source = cfg["source"]
    w = window_base.rowsBetween(-(period - 1), 0)
    import math

    df = df.withColumn("_pp",  F.lag(source, 1).over(window_base))
    df = df.withColumn("_ret",
        F.when(F.col("_pp").isNotNull() & (F.col("_pp") != 0),
               (F.col(source) - F.col("_pp")) / F.col("_pp") * 100)
        .otherwise(None)
    )
    df = df.withColumn(col_name, F.stddev("_ret").over(w) * math.sqrt(252))
    return df.drop("_pp", "_ret")


def _macd_line(df, col_name, cfg, window_base, F):
    fast = cfg.get("fast", 12)
    slow = cfg.get("slow", 26)
    fast_col = f"ema_{fast}"
    slow_col = f"ema_{slow}"

    if fast_col not in df.columns or slow_col not in df.columns:
        raise ValueError(
            f"macd_line requires '{fast_col}' and '{slow_col}' columns — "
            f"declare those ema indicators before macd_line in the schema."
        )
    return df.withColumn(col_name, F.col(fast_col) - F.col(slow_col))


def _macd_signal(df, col_name, cfg, window_base, F):
    signal   = cfg.get("signal", 9)
    macd_col = cfg.get("macd_col", "macd")
    if macd_col not in df.columns:
        raise ValueError(
            f"macd_signal requires '{macd_col}' column — "
            f"declare macd_line before macd_signal in the schema."
        )
    # Reuse _ema logic on the macd column
    return _ema(df, col_name, {"period": signal, "source": macd_col}, window_base, F)


def _macd_histogram(df, col_name, cfg, window_base, F):
    macd_col   = cfg.get("macd_col",   "macd")
    signal_col = cfg.get("signal_col", "macd_signal")
    if macd_col not in df.columns or signal_col not in df.columns:
        raise ValueError(
            f"macd_histogram requires '{macd_col}' and '{signal_col}' columns."
        )
    return df.withColumn(col_name, F.col(macd_col) - F.col(signal_col))


def _volume_ratio(df, col_name, cfg, window_base, F):
    sma_col = cfg.get("sma_col", "volume_sma_20")
    if sma_col not in df.columns:
        raise ValueError(
            f"volume_ratio requires '{sma_col}' column — "
            f"declare the volume sma indicator before volume_ratio in the schema."
        )
    return df.withColumn(col_name,
        F.when(F.col(sma_col) != 0, F.col("volume") / F.col(sma_col)).otherwise(None)
    )

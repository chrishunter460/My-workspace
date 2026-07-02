"""
ML Training Methods for Time Series Forecasting.

This module provides training functions for ARIMA, Prophet, and Random Forest
models used in securities price forecasting.
"""
from __future__ import annotations

from typing import Tuple, Dict, Optional
import pandas as pd
import numpy as np
from datetime import datetime
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)


def train_arima_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str = 'close',
    lookback_days: int = 60,
    forecast_horizon: int = 7,
    day_of_week_adj: bool = True,
    seasonal: bool = False,
    auto: bool = True
) -> Tuple[object, Dict]:
    """
    Train ARIMA model for time series forecasting.

    Args:
        data_pdf: DataFrame with trade_date and target column
        ticker: Stock ticker symbol
        target: Column to forecast (close, volume)
        lookback_days: Training window days
        forecast_horizon: Forecast horizon days
        day_of_week_adj: Include day of week as exogenous variable
        seasonal: Use seasonal ARIMA
        auto: Use auto_arima for parameter selection

    Returns:
        Tuple of (fitted_model, metadata_dict)
    """
    # Prepare data
    df = data_pdf.copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date')

    # Use most recent lookback_days
    if len(df) > lookback_days:
        df = df.tail(lookback_days)

    # Set index
    df = df.set_index('trade_date')

    # Prepare exogenous variables
    exog = None
    if day_of_week_adj:
        exog = pd.DataFrame({'day_of_week': df.index.dayofweek}, index=df.index)

    # Target series
    y = df[target].dropna()

    if len(y) < 10:
        raise ValueError(f"Insufficient data for ARIMA: {len(y)} points, need at least 10")

    # Align exog with y
    if exog is not None:
        exog = exog.loc[y.index]

    # Train model
    if auto:
        try:
            from pmdarima import auto_arima
            model = auto_arima(
                y,
                exogenous=exog,
                seasonal=seasonal,
                m=5 if seasonal else 1,  # 5-day trading week
                trace=False,
                suppress_warnings=True,
                stepwise=True,
                max_order=10
            )
        except ImportError:
            # Fallback to statsmodels ARIMA if pmdarima not available
            from statsmodels.tsa.arima.model import ARIMA
            model = ARIMA(y, order=(1, 1, 1), exog=exog).fit()
    else:
        from statsmodels.tsa.arima.model import ARIMA
        model = ARIMA(y, order=(1, 1, 1), exog=exog).fit()

    metadata = {
        'model_type': 'ARIMA',
        'model_name': f"ARIMA_{lookback_days}d",
        'ticker': ticker,
        'target': target,
        'lookback_days': lookback_days,
        'forecast_horizon': forecast_horizon,
        'training_end': y.index[-1].strftime('%Y-%m-%d'),
        'training_samples': len(y),
        'day_of_week_adj': day_of_week_adj
    }

    return model, metadata


def train_prophet_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str = 'close',
    lookback_days: int = 60,
    forecast_horizon: int = 7,
    day_of_week_adj: bool = True,
    seasonality_mode: str = 'multiplicative'
) -> Tuple[object, Dict]:
    """
    Train Prophet model for time series forecasting.

    Args:
        data_pdf: DataFrame with trade_date and target column
        ticker: Stock ticker symbol
        target: Column to forecast
        lookback_days: Training window days
        forecast_horizon: Forecast horizon days
        day_of_week_adj: Include day of week seasonality
        seasonality_mode: 'additive' or 'multiplicative'

    Returns:
        Tuple of (fitted_model, metadata_dict)
    """
    try:
        from prophet import Prophet
    except ImportError:
        raise ImportError("Prophet not installed. Install with: pip install prophet")

    # Prepare data
    df = data_pdf.copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date')

    # Use most recent lookback_days
    if len(df) > lookback_days:
        df = df.tail(lookback_days)

    # Prophet requires 'ds' and 'y' columns
    prophet_df = pd.DataFrame({
        'ds': df['trade_date'],
        'y': df[target]
    }).dropna()

    if len(prophet_df) < 10:
        raise ValueError(f"Insufficient data for Prophet: {len(prophet_df)} points, need at least 10")

    # Configure model
    model = Prophet(
        seasonality_mode=seasonality_mode,
        yearly_seasonality=False,  # Not relevant for <1 year
        weekly_seasonality=day_of_week_adj,
        daily_seasonality=False
    )

    # Fit model (suppress logging)
    import logging
    logging.getLogger('prophet').setLevel(logging.ERROR)
    logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

    model.fit(prophet_df)

    metadata = {
        'model_type': 'Prophet',
        'model_name': f"Prophet_{lookback_days}d",
        'ticker': ticker,
        'target': target,
        'lookback_days': lookback_days,
        'forecast_horizon': forecast_horizon,
        'training_end': prophet_df['ds'].iloc[-1].strftime('%Y-%m-%d'),
        'training_samples': len(prophet_df),
        'day_of_week_adj': day_of_week_adj,
        'training_data': prophet_df
    }

    return model, metadata


def train_random_forest_model(
    data_pdf: pd.DataFrame,
    ticker: str,
    target: str = 'close',
    lookback_days: int = 60,
    forecast_horizon: int = 14,
    n_estimators: int = 100,
    max_depth: int = 10
) -> Tuple[object, Dict]:
    """
    Train Random Forest model for time series forecasting.

    Creates lag features and day-of-week features for prediction.

    Args:
        data_pdf: DataFrame with trade_date and target column
        ticker: Stock ticker symbol
        target: Column to forecast
        lookback_days: Training window days
        forecast_horizon: Forecast horizon days
        n_estimators: Number of trees
        max_depth: Maximum tree depth

    Returns:
        Tuple of (fitted_model, metadata_dict)
    """
    from sklearn.ensemble import RandomForestRegressor

    # Prepare data
    df = data_pdf.copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date')

    # Use most recent lookback_days
    if len(df) > lookback_days:
        df = df.tail(lookback_days)

    df = df.set_index('trade_date')

    # Create features
    feature_cols = []

    # Lag features
    for lag in [1, 2, 3, 5, 7, 14]:
        col_name = f'lag_{lag}'
        df[col_name] = df[target].shift(lag)
        feature_cols.append(col_name)

    # Day of week features
    df['day_of_week'] = df.index.dayofweek
    df['is_monday'] = (df.index.dayofweek == 0).astype(int)
    df['is_friday'] = (df.index.dayofweek == 4).astype(int)
    feature_cols.extend(['day_of_week', 'is_monday', 'is_friday'])

    # Rolling statistics
    for window in [5, 10, 20]:
        df[f'rolling_mean_{window}'] = df[target].rolling(window).mean()
        df[f'rolling_std_{window}'] = df[target].rolling(window).std()
        feature_cols.extend([f'rolling_mean_{window}', f'rolling_std_{window}'])

    # Drop rows with NaN
    df_clean = df.dropna()

    if len(df_clean) < 20:
        raise ValueError(f"Insufficient data for Random Forest: {len(df_clean)} points, need at least 20")

    # Prepare X and y
    X = df_clean[feature_cols]
    y = df_clean[target]

    # Train model
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X, y)

    metadata = {
        'model_type': 'RandomForest',
        'model_name': f"RF_{lookback_days}d",
        'ticker': ticker,
        'target': target,
        'lookback_days': lookback_days,
        'forecast_horizon': forecast_horizon,
        'training_end': df_clean.index[-1].strftime('%Y-%m-%d'),
        'training_samples': len(df_clean),
        'feature_cols': feature_cols,
        'training_data': df_clean,
        'n_estimators': n_estimators,
        'max_depth': max_depth
    }

    return model, metadata

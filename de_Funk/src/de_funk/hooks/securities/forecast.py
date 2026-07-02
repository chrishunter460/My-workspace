"""
Forecast plugin — train time series models and save via ArtifactStore.

Triggered by post_build hook in domain model config:
    hooks:
      post_build:
        - {fn: de_funk.hooks.securities.forecast.train_and_save,
           params: {methods: [arima, prophet], horizon: 30}}

Reads ml_models config from model.md for model definitions.
Uses ArtifactStore for versioned model persistence.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from de_funk.core.hooks import pipeline_hook
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@pipeline_hook("post_build", model="securities.forecast")
def train_and_save(engine=None, config=None, model=None,
                   methods: list = None, horizon: int = 30, **params):
    """Train forecast models defined in ml_models config and save via ArtifactStore.

    Args:
        engine: Engine instance for data reads
        config: Model config dict (has ml_models section)
        model: BaseModel instance
        methods: List of model types to train (arima, prophet, random_forest)
        horizon: Forecast horizon in days
    """
    if config is None:
        logger.warning("forecast.train_and_save: no config — skipping")
        return

    ml_models = config.get("ml_models", {})
    if not ml_models:
        logger.info("forecast.train_and_save: no ml_models in config — skipping")
        return

    # Filter by requested methods if specified
    if methods:
        ml_models = {k: v for k, v in ml_models.items()
                     if v.get("type", "") in methods or k in methods}

    logger.info(f"Training {len(ml_models)} forecast model(s): {list(ml_models.keys())}")

    for model_key, spec in ml_models.items():
        model_type = spec.get("type", "arima")
        target = spec.get("target", ["close"])
        lookback = spec.get("lookback_days", 90)
        forecast_horizon = spec.get("forecast_horizon", horizon)

        logger.info(f"  Training {model_key} ({model_type}): "
                     f"target={target}, lookback={lookback}, horizon={forecast_horizon}")

        try:
            _train_single_model(
                model_key=model_key,
                model_type=model_type,
                target=target,
                lookback=lookback,
                horizon=forecast_horizon,
                spec=spec,
                model=model,
            )
        except Exception as e:
            logger.warning(f"  Failed to train {model_key}: {e}")


def _train_single_model(model_key: str, model_type: str, target: list,
                        lookback: int, horizon: int, spec: dict,
                        model=None):
    """Train a single forecast model and save to ArtifactStore."""
    from pathlib import Path

    build_session = getattr(model, 'build_session', None) if model else None
    if build_session is None:
        logger.warning(f"  {model_key}: no build_session — cannot save artifact")
        return

    # Get training data from the model's source
    # For securities.forecast, source is securities.stocks.fact_stock_prices
    source_table = spec.get("source_table", "fact_stock_prices")
    training_df = model.get_table(source_table) if model else None

    if training_df is None:
        logger.info(f"  {model_key}: no training data from {source_table}")
        return

    # Train based on model type
    import numpy as np

    if model_type == "arima":
        try:
            from de_funk.models.domains.securities.forecast.training_methods import train_arima_model
            trained_model, metadata = train_arima_model(
                training_df if hasattr(training_df, 'to_pandas') else training_df,
                ticker="ALL",
                target=target[0] if target else "close",
                lookback_days=lookback,
                forecast_horizon=horizon,
            )
        except ImportError:
            logger.info(f"  {model_key}: pmdarima not available")
            return

    elif model_type == "prophet":
        try:
            from de_funk.models.domains.securities.forecast.training_methods import train_prophet_model
            trained_model, metadata = train_prophet_model(
                training_df if hasattr(training_df, 'to_pandas') else training_df,
                ticker="ALL",
                target=target[0] if target else "close",
                lookback_days=lookback,
                forecast_horizon=horizon,
            )
        except ImportError:
            logger.info(f"  {model_key}: prophet not available")
            return

    elif model_type == "random_forest":
        try:
            from sklearn.ensemble import RandomForestRegressor
            # Simple RF on available numeric features
            if hasattr(training_df, 'toPandas'):
                pdf = training_df.toPandas()
            else:
                pdf = training_df
            numeric = pdf.select_dtypes(include=[np.number]).dropna()
            if len(numeric) < 10:
                logger.info(f"  {model_key}: insufficient numeric data")
                return
            X = numeric.iloc[:, :-1].values
            y = numeric.iloc[:, -1].values
            trained_model = RandomForestRegressor(n_estimators=50, random_state=42)
            trained_model.fit(X, y)
            metadata = {"samples": len(X), "features": len(X[0])}
        except ImportError:
            logger.info(f"  {model_key}: sklearn not available")
            return
    else:
        logger.warning(f"  {model_key}: unknown model type '{model_type}'")
        return

    # Save via ArtifactStore
    from de_funk.core.artifacts import ModelArtifact, ArtifactStore

    store = ArtifactStore(models_root=Path(build_session.storage_router.models_root))
    version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    artifact = ModelArtifact(
        model_name=model_key,
        version=version,
        metrics=metadata,
        config=spec,
        status="active",
    )
    path = store.save(artifact, trained_model)
    logger.info(f"  Saved {model_key} {version} → {path}")

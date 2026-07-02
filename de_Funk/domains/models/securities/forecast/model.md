---
type: domain-model
model: securities.forecast
version: 3.0
description: "Time series forecasting for securities prices and volumes"
depends_on: [temporal, securities.stocks]

storage:
  format: delta
  silver:
    root: storage/silver/forecast/

ml_models:
  arima_7d: {type: arima, target: [close], lookback_days: 60, forecast_horizon: 7}
  arima_30d: {type: arima, target: [close], lookback_days: 180, forecast_horizon: 30}
  prophet_7d: {type: prophet, target: [close], lookback_days: 90, forecast_horizon: 7}
  prophet_30d: {type: prophet, target: [close], lookback_days: 365, forecast_horizon: 30}
  random_forest_14d: {type: random_forest, target: [close], lookback_days: 90, forecast_horizon: 14}

hooks:
  post_build:
    - {fn: de_funk.hooks.securities.forecast.train_and_save,
       params: {methods: [arima, prophet, random_forest], horizon: 30}}

graph:
  edges:
    - [forecast_price_to_prediction_cal, fact_forecast_price, temporal.dim_calendar, [prediction_date_id=date_id], many_to_one, temporal]
    - [forecast_price_to_forecast_cal, fact_forecast_price, temporal.dim_calendar, [forecast_date_id=date_id], many_to_one, temporal]


build:
  partitions: [forecast_date]
  sort_by: [security_id, forecast_date]
  optimize: true
  phases:
    1: { tables: [dim_model_registry] }
    2: { tables: [fact_forecast_price, fact_forecast_metrics] }

measures:
  simple:
    - [forecast_count, count_distinct, fact_forecast_price.forecast_price_id, "Number of forecasts", {format: "#,##0"}]
    - [avg_mape, avg, fact_forecast_metrics.mape, "Average MAPE", {format: "#,##0.00%"}]
  computed:
    - [avg_r2, expression, "AVG(r2_score)", "Average R2", {format: "#,##0.00", source_table: fact_forecast_metrics}]

metadata:
  domain: securities
  owner: data_engineering
status: active
---

## Forecast Model

Time series forecasting using ARIMA, Prophet, and Random Forest. All tables are generated (not from bronze).

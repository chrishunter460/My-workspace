---
type: domain-model
model: analytics.workbook
version: 1.0
description: "Cross-domain prediction workbook — stock price prediction from company financials"
depends_on: [temporal, securities.stocks, corporate.entity, corporate.finance]

storage:
  format: delta
  silver:
    root: storage/silver/analytics/workbook/

ml_models:
  stock_predictor:
    type: random_forest
    target: [next_30d_return]
    features: [pe_ratio, revenue_growth, debt_equity_ratio, avg_volume_30d, price_to_book]
    lookback_days: 365
    forecast_horizon: 30
    retrain_if_stale_days: 7
    parameters:
      n_estimators: 100
      max_depth: 10
      min_samples_split: 5

hooks:
  before_build:
    - {fn: de_funk.hooks._common.log_build.log_start, params: {}}
  post_build:
    - {fn: de_funk.hooks.analytics.workbook.train_and_save, params: {model_key: stock_predictor}}

graph:
  edges:
    - [features_to_calendar, fact_feature_set, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
    - [features_to_stock, fact_feature_set, securities.stocks.dim_stock, [security_id=security_id], many_to_one, securities.stocks]
    - [predictions_to_calendar, fact_predictions, temporal.dim_calendar, [prediction_date_id=date_id], many_to_one, temporal]

build:
  phases:
    1: { tables: [fact_feature_set] }
    2: { tables: [fact_predictions, dim_prediction_model] }

measures:
  simple:
    - [prediction_count, count_distinct, fact_predictions.prediction_id, "Total predictions", {format: "#,##0"}]
    - [avg_predicted_return, avg, fact_predictions.predicted_return, "Avg predicted return", {format: "0.00%"}]
  computed:
    - [model_accuracy, expression, "AVG(CASE WHEN ABS(predicted_return - actual_return) < 0.05 THEN 1 ELSE 0 END)", "Accuracy (±5%)", {format: "0.0%", source_table: fact_predictions}]

metadata:
  domain: analytics
  owner: data_engineering
  purpose: "End-to-end ML pipeline demo — cross-domain feature engineering + model training + artifact storage"
status: active
---

## Analytics Workbook

Cross-domain prediction model that demonstrates the full de_Funk ML pipeline:

1. **Feature Engineering**: Joins stock prices with company financial ratios
2. **Model Training**: Random forest trained on historical features → forward returns
3. **Artifact Storage**: Trained model saved via ArtifactStore with versioning
4. **Predictions**: Model generates predictions written back to Silver

### Data Flow

```
corporate.finance.fact_financial_statements ─┐
                                              ├─► fact_feature_set ─► train model ─► fact_predictions
securities.stocks.fact_stock_prices ──────────┘                          │
                                                                         ▼
                                                                   ArtifactStore
                                                                   /storage/models/stock_predictor/v{n}/
```

### ML Model Config

Models are declared in YAML `ml_models:` and trained via `post_build` hook.
No custom Python model class needed — the plugin handles everything.

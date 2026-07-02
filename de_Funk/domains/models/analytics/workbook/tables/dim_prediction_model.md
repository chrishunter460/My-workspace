---
type: domain-model-table
table: dim_prediction_model
table_type: dimension
generated: true
primary_key: [model_id]

schema:
  - [model_id, string, false, "Unique model identifier"]
  - [model_name, string, false, "Model name from ml_models config"]
  - [model_type, string, false, "Algorithm type (random_forest, arima, etc.)"]
  - [version, string, false, "Model version"]
  - [trained_at, string, false, "ISO datetime of training"]
  - [features, string, true, "JSON list of feature columns"]
  - [target, string, true, "Target column name"]
  - [lookback_days, integer, true, "Training window"]
  - [forecast_horizon, integer, true, "Prediction horizon days"]
  - [r2_score, double, true, "R-squared on holdout"]
  - [rmse, double, true, "Root mean squared error"]
  - [artifact_path, string, true, "Path to saved model artifact"]
  - [status, string, false, "active or retired"]

measures:
  - [model_count, count_distinct, model_id, "Number of models", {format: "#,##0"}]
---

## Prediction Model Registry

Tracks trained models with their parameters, metrics, and artifact paths.
Populated by the `train_and_save` post_build hook.

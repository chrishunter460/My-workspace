---
type: domain-model-table
table: dim_model_registry
table_type: dimension
generated: true
primary_key: [model_id]

schema:
  - [model_id, string, false, "Unique model identifier"]
  - [model_name, string, false, "Model name"]
  - [model_type, string, false, "ARIMA, Prophet, RandomForest"]
  - [ticker, string, false, "Stock ticker"]
  - [target_variable, string, false, "Target column"]
  - [lookback_days, integer, false, "Training window"]
  - [forecast_horizon, integer, false, "Forecast horizon days"]
  - [parameters, string, true, "JSON-encoded model parameters"]
  - [trained_date, string, false, "Date trained"]
  - [training_samples, integer, true, "Number of training samples"]
  - [status, string, false, "active or inactive"]

measures:
  - [model_count, count_distinct, model_id, "Number of models", {format: "#,##0"}]
---

## Model Registry Dimension

Trained model registry tracking parameters and status.

---
type: domain-model-table
table: fact_forecast_metrics
table_type: fact
generated: true
primary_key: [ticker, model_name, metric_date]
partition_by: [metric_date]

schema:
  - [ticker, string, false, "Stock ticker"]
  - [model_name, string, false, "Model identifier"]
  - [metric_date, string, false, "Metrics calculation date"]
  - [metric_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [training_start, string, true, "Training period start"]
  - [training_end, string, true, "Training period end"]
  - [mae, double, true, "Mean Absolute Error"]
  - [rmse, double, true, "Root Mean Square Error"]
  - [mape, double, true, "Mean Absolute Percentage Error"]
  - [r2_score, double, true, "R-squared score"]
  - [directional_accuracy, double, true, "Direction prediction accuracy %"]

measures:
  - [avg_mape, avg, mape, "Average MAPE", {format: "#,##0.00%"}]
  - [avg_r2, avg, r2_score, "Average R2", {format: "#,##0.00"}]
---

## Forecast Metrics Fact Table

Model accuracy metrics on holdout validation data.

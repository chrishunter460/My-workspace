---
type: domain-model-table
table: fact_forecast_price
table_type: fact
generated: true
primary_key: [forecast_price_id]
partition_by: [forecast_date]

schema:
  - [forecast_price_id, integer, false, "PK"]
  - [ticker, string, false, "Stock ticker"]
  - [forecast_date, string, false, "Date forecast generated"]
  - [prediction_date, string, false, "Date being predicted"]
  - [forecast_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [prediction_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [horizon, integer, false, "Days ahead"]
  - [model_name, string, false, "Model identifier"]
  - [predicted_close, double, false, "Predicted closing price"]
  - [lower_bound, double, true, "Lower confidence bound"]
  - [upper_bound, double, true, "Upper confidence bound"]
  - [confidence, double, true, "Confidence level", {default: 0.95}]

measures:
  - [forecast_count, count_distinct, forecast_price_id, "Forecasts", {format: "#,##0"}]
  - [avg_predicted_close, avg, predicted_close, "Avg predicted close", {format: "$#,##0.00"}]
---

## Price Forecast Fact Table

ML-generated price predictions.

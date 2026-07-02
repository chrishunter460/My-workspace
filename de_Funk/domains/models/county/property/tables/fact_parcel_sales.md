---
type: domain-model-table
table: fact_parcel_sales
extends: _base.property.parcel._fact_parcel_sales
table_type: fact
primary_key: [parcel_id, sale_date]
partition_by: [year]

schema:
  # Bronze columns: pin, year, township_code, class, sale_date, sale_price, sale_document_num, deed_type, seller_name, buyer_name
  - [parcel_id, string, false, "FK to dim_parcel", {fk: dim_parcel.parcel_id, derived: "LPAD(CAST(pin AS VARCHAR), 14, '0')"}]
  - [sale_date, date, false, "Sale date", {format: date}]
  - [sale_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(sale_date, 'yyyyMMdd') AS INT)"}]
  - [sale_price, double, true, "Sale price", {format: $}]
  - [sale_type, string, true, "Sale type (deed type)", {derived: "deed_type"}]
  - [year, integer, false, "Sale year"]

measures:
  - [total_sales_volume, sum, sale_price, "Total sales volume", {format: "$#,##0"}]
  - [avg_sale_price, avg, sale_price, "Average sale price", {format: "$#,##0"}]
  - [sale_count, count, parcel_id, "Number of sales", {format: "#,##0"}]
---

## Parcel Sales Fact Table

Property sales transactions for Cook County parcels.

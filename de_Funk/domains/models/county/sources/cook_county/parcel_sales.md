---
type: domain-model-source
source: parcel_sales
extends: _base.property.parcel
maps_to: fact_parcel_sales
from: bronze.cook_county_parcel_sales
domain_source: "'cook_county'"

aliases:
  # Available in bronze.cook_county_parcel_sales:
  # pin, year, township_code, class, sale_date, sale_price, sale_document_num, deed_type, seller_name, buyer_name
  - [legal_entity_id, "ABS(HASH(CONCAT('COUNTY_', 'Cook County')))"]
  - [parcel_id, "LPAD(CAST(pin AS STRING), 14, '0')"]
  - [sale_date, sale_date]
  - [sale_date_id, "CAST(DATE_FORMAT(sale_date, 'yyyyMMdd') AS INT)"]
  - [year, year]
  - [sale_price, sale_price]
  - [sale_type, deed_type]
  - [sale_document_num, sale_document_num]
  - [seller_name, seller_name]
  - [buyer_name, buyer_name]
  - [property_class, class]
  - [township_code, township_code]
---

## Parcel Sales
Property sales transactions with sale price, date, and type for all Cook County parcels.

---
type: api-endpoint
provider: Cook County Data Portal
endpoint_id: parcel_sales

# API Configuration
endpoint_pattern: /resource/wvhk-k5uv.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
  $order: sale_date DESC
required_params: []

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: finance
legal_entity_type: county
subject_entity_tags: [county, property]
data_tags: [property-tax, parcel, sales, time-series]
status: active
update_cadence: monthly
last_verified:
last_reviewed:
notes: "Parcel sales 1999-present. PIN must be zero-padded to 14 digits."

# Storage Configuration
bronze: cook_county
partitions: [year]
write_strategy: upsert
key_columns: [pin, sale_document_num]
date_column: sale_date

# Schema
schema:
  - [pin, string, pin, false, "14-digit Parcel Index Number", {transform: "zfill(14)"}]
  - [year, int, year, true, "Sale year"]
  - [township_code, string, township_code, true, "Township code"]
  - [class, string, class, true, "Property class code"]
  - [sale_date, date, sale_date, true, "Sale date"]
  - [sale_price, double, sale_price, true, "Sale price", {coerce: double}]
  - [sale_document_num, string, sale_document_num, true, "Clerk document number"]
  - [deed_type, string, deed_type, true, "Deed type"]
  - [seller_name, string, seller_name, true, "Seller name"]
  - [buyer_name, string, buyer_name, true, "Buyer name"]
---

## Description

Parcel sales for real property in Cook County, from 1999 to present. The Assessor's Office uses this data in its modeling to estimate the fair market value of unsold properties.  
  
When working with Parcel Index Numbers (PINs) make sure to zero-pad them to 14 digits. Some datasets may lose leading zeros for PINs when downloaded.  
  
Sale document numbers correspond to those of the Cook County Clerk, and can be used on the [Clerk's website](https://ccrd.cookcountyclerkil.gov/i2/default.aspx) to find more information about each sale.  
  
NOTE: These sales _are_ filtered, but likely include non-arms-length transactions - sales less than $10,000 along with quit claims, executor deeds, beneficial interests are excluded. While the Data Department will upload what it has access to monthly, sales are reported on a lag, with many records not populating until months after their official recording date.  
  
Current property class codes, their levels of assessment, and descriptions can be found [on the Assessor's website](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf). Note that class codes details can change across time.  
  
For more information on the sourcing of attached data and the preparation of this dataset, see the [Assessor's Standard Operating Procedures for Open Data](https://github.com/ccao-data/wiki/blob/master/SOPs/Open-Data.md) on GitHub.  
  
[Read about the Assessor's 2025 Open Data Refresh.](https://datacatalog.cookcountyil.gov/stories/s/gzdr-q7c4)

**Update 10/31/2023:** Sales are no longer filtered out of this data set based on deed type, sale price, or recency of sale for a given PIN with the same price. If users wish to recreate the former filtering schema they should set _sale_filter_same_sale_within_365_, _sale_filter_less_than_10k_, and _sale_filter_deed_type_ to False.

## Request Notes
Query params, limits, filters.

## Homelab Usage
Cron jobs, ingest scripts, storage paths.

## Known Quirks
Downtime patterns, format changes, gotchas.
---
type: domain-model-source
source: business_licenses
extends: _base.regulatory.inspection
maps_to: fact_business_licenses
from: bronze.chicago_business_licenses
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [license_record_id, "ABS(HASH(CAST(license_id AS STRING)))"]
  - [business_name, doing_business_as_name]
  - [issue_date, date_issued]
  - [date_id, "CAST(DATE_FORMAT(date_issued, 'yyyyMMdd') AS INT)"]
  - [expiration_date, license_term_expiration_date]
  - [start_date, license_term_start_date]
  - [year, "YEAR(date_issued)"]
  - [address, address]
  - [city, city]
  - [state, state]
  - [zip_code, zip_code]
  - [legal_name, legal_name]
  - [account_number, account_number]
  - [license_code, license_code]
  - [application_type, application_type]
  - [status, license_status]
  - [license_type, license_description]
  - [ward, "CAST(NULL AS INT)"]
  - [community_area, "CAST(NULL AS INT)"]
  - [latitude, latitude]
  - [license_id, "ABS(HASH(CAST(license_id AS STRING)))"]
  - [longitude, longitude]
---

## Business Licenses
Business license issuance and renewal records with status tracking.

 
```dataview
TABLE
  provider,
  service,
  method,
  endpoint,
  domain,
  data_tags,
  auth,
  rate_limit,
  status
FROM ""
WHERE type = "api-endpoint"
SORT provider, service, endpoint

```
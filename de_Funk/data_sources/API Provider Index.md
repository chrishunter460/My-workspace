```dataview
TABLE
  provider,
  category,
  auth_model,
  env_api_key,
  data_domains,
  data_tags,
  rate_limit,
  status
FROM ""
WHERE type = "api-provider"
SORT provider
```

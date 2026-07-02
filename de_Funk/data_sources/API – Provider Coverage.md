
```dataview
TABLE
  provider,
  length(rows) AS endpoint_count
FROM "de'funk/APIs/Endpoints"
WHERE type = "api-endpoint"
GROUP BY provider
SORT endpoint_count DESC
```

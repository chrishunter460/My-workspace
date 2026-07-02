# Full summary with column details
python -m scripts.maintenance.inspect_silver

# Summary table only (no column details)
python -m scripts.maintenance.inspect_silver --summary-only

# Inspect a specific domain
python -m scripts.maintenance.inspect_silver --domain stocks

# Inspect a specific table with sample rows
python -m scripts.maintenance.inspect_silver --table dim_stock --sample 5

# Combine filters
python -m scripts.maintenance.inspect_silver --domain corporate/entity --sample 3

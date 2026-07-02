# Quickstart

## 1. Conda Environment

```bash
# Create (first time)
conda env create -f environment.yml

# Activate
conda activate de_funk

# Verify
python -c "import de_funk; print('ok')"
```

## 2. Spark Cluster

```bash
# Start master
$SPARK_HOME/sbin/start-master.sh

# Start worker (same machine or remote)
$SPARK_HOME/sbin/start-worker.sh spark://192.168.1.212:7077

# Verify — Spark UI at http://192.168.1.212:8080
```

Stop the cluster when done:
```bash
$SPARK_HOME/sbin/stop-worker.sh
$SPARK_HOME/sbin/stop-master.sh
```

## 3. FastAPI Server

```bash
conda activate de_funk
python -m uvicorn de_funk.api.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs at http://localhost:8000/docs

## 4. Build Silver Models

```bash
# Dry run — see what would build
python -m scripts.build.build_models --dry-run

# Build one model
python -m scripts.build.build_models --models temporal

# Build all
python -m scripts.build.build_models
```

## 5. Example: Generate dim_calendar via Spark

```bash
# Requires cluster running (step 2)
conda activate de_funk
python -c "
from de_funk.orchestration.common.spark_session import get_spark
from pyspark.sql import functions as F

spark = get_spark('CalendarBuild')

df = spark.sql(\"\"\"
    SELECT explode(sequence(
        to_date('2000-01-01'), to_date('2050-12-31'), interval 1 day
    )) as date
\"\"\")

df = df.select(
    F.date_format('date', 'yyyyMMdd').cast('int').alias('date_id'),
    F.col('date'),
    F.year('date').alias('year'),
    F.quarter('date').alias('quarter'),
    F.month('date').alias('month'),
    F.date_format('date', 'MMMM').alias('month_name'),
)

df.write.format('delta').mode('overwrite').save(
    '/shared/storage/silver/temporal/dims/dim_calendar'
)
spark.stop()
"
```

## Environment Variables (.env)

| Variable | Purpose | Example |
|---|---|---|
| `SPARK_MASTER_URL` | Spark cluster master | `spark://192.168.1.212:7077` |
| `SPARK_DRIVER_HOST` | Driver IP for cluster comms | `192.168.1.212` |
| `SPARK_DRIVER_MEMORY` | Driver heap (default 2g cluster, 4g local) | `4g` |
| `SPARK_EXECUTOR_MEMORY` | Worker heap (default 4g) | `8g` |
| `LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING` |

## Storage Layout

```
/shared/storage/
├── bronze/          # Raw API data (partitioned by source)
├── silver/          # Dimensional star schemas (Delta Lake)
│   ├── municipal/
│   ├── corporate/
│   ├── securities/
│   └── temporal/    # dim_calendar
└── spark-events/    # Spark History Server logs
```

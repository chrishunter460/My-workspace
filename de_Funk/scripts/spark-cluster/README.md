# Standalone Spark Cluster Setup

Simple standalone Spark cluster using your existing 4-node infrastructure.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Standalone Spark Cluster                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   bigbark (192.168.1.212)                                       │
│   ├── Spark Master (:7077)                                      │
│   ├── Master Web UI (:8080)                                     │
│   ├── Spark Worker (local)                                      │
│   └── History Server (:18080)                                   │
│                                                                  │
│   bark-1 (192.168.1.207)     ─┐                                 │
│   ├── Spark Worker            │                                 │
│   └── connects to master:7077 │                                 │
│                               │                                 │
│   bark-2 (192.168.1.202)     ─┼── Workers register with Master  │
│   ├── Spark Worker            │                                 │
│   └── connects to master:7077 │                                 │
│                               │                                 │
│   bark-3 (192.168.1.203)     ─┘                                 │
│   ├── Spark Worker                                              │
│   └── connects to master:7077                                   │
│                                                                  │
│   Shared Storage: /shared/storage (NFS)                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start Master (on bigbark)

```bash
ssh bigbark
./scripts/spark-cluster/start-master.sh
```

Master UI available at: http://192.168.1.212:8080

### 2. Start Workers (on each worker node)

```bash
# On bark-1
ssh bark-1
./scripts/spark-cluster/start-worker.sh

# Repeat for bark-2, bark-3
```

Or start all workers from bigbark:
```bash
./scripts/spark-cluster/start-all-workers.sh
```

### 3. Submit Jobs

```bash
# From any node with access to master
spark-submit --master spark://192.168.1.212:7077 \
    --deploy-mode client \
    your_job.py
```

Or use the provided wrapper:
```bash
./scripts/spark-cluster/submit-job.sh scripts/build/build_models.py --models stocks
```

## Web UIs

| UI | URL | Purpose |
|----|-----|---------|
| Master | http://192.168.1.212:8080 | Cluster overview, workers, apps |
| Worker | http://<worker>:8081 | Worker details, executors |
| Application | http://192.168.1.212:4040 | Running job details (when active) |
| History | http://192.168.1.212:18080 | Completed job logs |

## Management Commands

```bash
# Stop everything
./scripts/spark-cluster/stop-all.sh

# Check status
./scripts/spark-cluster/status.sh

# View logs
tail -f /tmp/spark-*.out
```

## Configuration

Edit `scripts/spark-cluster/spark-env.sh` to customize:
- Worker memory
- Worker cores
- Master host/port

## vs Ray Cluster

| Aspect | Standalone Spark | Ray + Spark |
|--------|-----------------|-------------|
| Memory sharing | Native shuffle | None (isolated tasks) |
| Setup | Simpler | More complex |
| API ingestion | Not ideal | Good (async) |
| Silver builds | Excellent | Good (but RAM competition) |
| Web UI | Built-in | Limited |

## Recommended Usage

1. **API Ingestion**: Simple Python script (asyncio) - runs on any node
2. **Silver Builds**: Submit to Spark cluster - true distributed compute
3. **Orchestration**: Cron or Airflow to trigger jobs

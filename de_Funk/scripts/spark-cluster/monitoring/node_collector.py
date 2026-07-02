"""
Node Metrics Collector - Collects CPU, memory, disk stats from cluster nodes.

Collects metrics from all nodes defined in configs/cluster.yaml via SSH
and provides them as a JSON API for the monitoring dashboard.
"""
from __future__ import annotations

import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml


@dataclass
class NodeMetrics:
    """Metrics for a single node."""
    name: str
    ip: str
    status: str  # 'online', 'offline', 'error'
    timestamp: float

    # CPU metrics
    cpu_percent: float = 0.0
    cpu_cores: int = 0
    load_1m: float = 0.0
    load_5m: float = 0.0
    load_15m: float = 0.0

    # Memory metrics (in GB)
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_available_gb: float = 0.0
    memory_percent: float = 0.0

    # Disk metrics (in GB)
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_available_gb: float = 0.0
    disk_percent: float = 0.0

    # Spark worker status
    spark_worker_running: bool = False
    spark_worker_pid: Optional[int] = None

    # Error message if any
    error: Optional[str] = None


class NodeCollector:
    """Collects metrics from cluster nodes."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize collector with cluster config."""
        if config_path is None:
            # Find repo root and config
            script_dir = Path(__file__).parent
            repo_root = script_dir.parent.parent.parent
            config_path = repo_root / "configs" / "cluster.yaml"

        self.config_path = config_path
        self.config = self._load_config()
        self.cache: Dict[str, NodeMetrics] = {}
        self.cache_ttl = 5  # seconds
        self.last_collection = 0

    def _load_config(self) -> dict:
        """Load cluster configuration."""
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def get_nodes(self) -> List[dict]:
        """Get list of all nodes (head + workers)."""
        nodes = []

        # Head node
        head = self.config['cluster']['head']
        nodes.append({
            'name': head['hostname'],
            'ip': head['ip'],
            'user': head['user'],
            'is_head': True,
            'cores': None,  # Will be detected
            'memory_gb': None
        })

        # Workers
        for worker in self.config['cluster']['workers']:
            nodes.append({
                'name': worker['name'],
                'ip': worker['ip'],
                'user': head['user'],  # Same user as head
                'is_head': False,
                'cores': worker['cores'],
                'memory_gb': worker['memory_gb']
            })

        return nodes

    def collect_node_metrics(self, node: dict) -> NodeMetrics:
        """Collect metrics from a single node via SSH."""
        metrics = NodeMetrics(
            name=node['name'],
            ip=node['ip'],
            status='offline',
            timestamp=time.time()
        )

        user = node['user']
        ip = node['ip']

        # Build the metrics collection command
        # This runs on the remote node and outputs JSON
        # Uses two /proc/stat samples for accurate CPU measurement
        collect_cmd = """
python3 -c '
import json
import os
import time

result = {}

# CPU info - sample twice for accurate measurement
try:
    def read_cpu_times():
        with open("/proc/stat") as f:
            cpu_line = f.readline()
            times = list(map(int, cpu_line.split()[1:8]))
            # user, nice, system, idle, iowait, irq, softirq
            idle = times[3] + times[4]  # idle + iowait
            total = sum(times)
            return idle, total

    # First sample
    idle1, total1 = read_cpu_times()
    time.sleep(0.5)  # Wait 500ms
    # Second sample
    idle2, total2 = read_cpu_times()

    # Calculate CPU usage
    idle_delta = idle2 - idle1
    total_delta = total2 - total1
    if total_delta > 0:
        result["cpu_percent"] = round((1.0 - idle_delta / total_delta) * 100, 1)
    else:
        result["cpu_percent"] = 0.0

    # Load average
    with open("/proc/loadavg") as f:
        load = f.read().split()
        result["load_1m"] = float(load[0])
        result["load_5m"] = float(load[1])
        result["load_15m"] = float(load[2])

    result["cpu_cores"] = os.cpu_count()
except Exception as e:
    result["cpu_error"] = str(e)
    result["cpu_percent"] = 0.0

# Memory info
try:
    with open("/proc/meminfo") as f:
        meminfo = {}
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                meminfo[parts[0].rstrip(":")] = int(parts[1])

    total = meminfo.get("MemTotal", 0) / 1024 / 1024  # GB
    available = meminfo.get("MemAvailable", 0) / 1024 / 1024  # GB
    used = total - available

    result["memory_total_gb"] = round(total, 2)
    result["memory_used_gb"] = round(used, 2)
    result["memory_available_gb"] = round(available, 2)
    result["memory_percent"] = round((used / total) * 100, 1) if total > 0 else 0
except Exception as e:
    result["memory_error"] = str(e)

# Disk info (root partition)
try:
    statvfs = os.statvfs("/")
    total = statvfs.f_blocks * statvfs.f_frsize / 1024 / 1024 / 1024  # GB
    available = statvfs.f_bavail * statvfs.f_frsize / 1024 / 1024 / 1024  # GB
    used = total - available

    result["disk_total_gb"] = round(total, 2)
    result["disk_used_gb"] = round(used, 2)
    result["disk_available_gb"] = round(available, 2)
    result["disk_percent"] = round((used / total) * 100, 1) if total > 0 else 0
except Exception as e:
    result["disk_error"] = str(e)

# Spark worker status
try:
    import subprocess
    proc = subprocess.run(["pgrep", "-f", "org.apache.spark.deploy.worker.Worker"],
                         capture_output=True, text=True)
    if proc.returncode == 0:
        result["spark_worker_running"] = True
        result["spark_worker_pid"] = int(proc.stdout.strip().split()[0])
    else:
        result["spark_worker_running"] = False
except Exception as e:
    result["spark_error"] = str(e)

print(json.dumps(result))
'
"""

        # Extract the Python script from the command template
        python_script = collect_cmd.strip()
        if python_script.startswith("python3 -c '"):
            python_script = python_script[12:]  # Remove "python3 -c '"
        if python_script.endswith("'"):
            python_script = python_script[:-1]  # Remove trailing "'"

        try:
            # Check if this is the local node
            local_ips_result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                timeout=5
            )
            local_ips = local_ips_result.stdout.strip()

            if ip in local_ips:
                # Run locally - use the extracted Python script
                result = subprocess.run(
                    ["python3", "-c", python_script],
                    capture_output=True,
                    text=True,
                    timeout=15  # Increased for CPU sampling delay
                )
            else:
                # Run via SSH - use full command with python3 -c wrapper
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                     f"{user}@{ip}", collect_cmd],
                    capture_output=True,
                    text=True,
                    timeout=20  # Increased for SSH + CPU sampling
                )

            if result.returncode == 0:
                data = json.loads(result.stdout.strip())
                metrics.status = 'online'
                metrics.cpu_percent = data.get('cpu_percent', 0)
                metrics.cpu_cores = data.get('cpu_cores', 0)
                metrics.load_1m = data.get('load_1m', 0)
                metrics.load_5m = data.get('load_5m', 0)
                metrics.load_15m = data.get('load_15m', 0)
                metrics.memory_total_gb = data.get('memory_total_gb', 0)
                metrics.memory_used_gb = data.get('memory_used_gb', 0)
                metrics.memory_available_gb = data.get('memory_available_gb', 0)
                metrics.memory_percent = data.get('memory_percent', 0)
                metrics.disk_total_gb = data.get('disk_total_gb', 0)
                metrics.disk_used_gb = data.get('disk_used_gb', 0)
                metrics.disk_available_gb = data.get('disk_available_gb', 0)
                metrics.disk_percent = data.get('disk_percent', 0)
                metrics.spark_worker_running = data.get('spark_worker_running', False)
                metrics.spark_worker_pid = data.get('spark_worker_pid')
            else:
                metrics.status = 'error'
                metrics.error = result.stderr.strip() or 'Unknown error'

        except subprocess.TimeoutExpired:
            metrics.status = 'offline'
            metrics.error = 'Connection timeout'
        except json.JSONDecodeError as e:
            metrics.status = 'error'
            metrics.error = f'Invalid response: {e}'
        except Exception as e:
            metrics.status = 'error'
            metrics.error = str(e)

        return metrics

    def collect_all(self, force: bool = False) -> Dict[str, NodeMetrics]:
        """Collect metrics from all nodes."""
        current_time = time.time()

        # Use cache if still valid
        if not force and self.cache and (current_time - self.last_collection) < self.cache_ttl:
            return self.cache

        nodes = self.get_nodes()
        results = {}

        # Collect in parallel
        with ThreadPoolExecutor(max_workers=len(nodes)) as executor:
            futures = {
                executor.submit(self.collect_node_metrics, node): node['name']
                for node in nodes
            }

            for future in as_completed(futures):
                name = futures[future]
                try:
                    metrics = future.result()
                    results[name] = metrics
                except Exception as e:
                    results[name] = NodeMetrics(
                        name=name,
                        ip='unknown',
                        status='error',
                        timestamp=current_time,
                        error=str(e)
                    )

        self.cache = results
        self.last_collection = current_time
        return results

    def get_cluster_summary(self) -> dict:
        """Get cluster-wide summary statistics."""
        metrics = self.collect_all()

        online_nodes = [m for m in metrics.values() if m.status == 'online']

        if not online_nodes:
            return {
                'total_nodes': len(metrics),
                'online_nodes': 0,
                'total_cores': 0,
                'total_memory_gb': 0,
                'used_memory_gb': 0,
                'avg_cpu_percent': 0,
                'avg_memory_percent': 0,
                'spark_workers_running': 0
            }

        return {
            'total_nodes': len(metrics),
            'online_nodes': len(online_nodes),
            'total_cores': sum(m.cpu_cores for m in online_nodes),
            'total_memory_gb': round(sum(m.memory_total_gb for m in online_nodes), 2),
            'used_memory_gb': round(sum(m.memory_used_gb for m in online_nodes), 2),
            'avg_cpu_percent': round(sum(m.cpu_percent for m in online_nodes) / len(online_nodes), 1),
            'avg_memory_percent': round(sum(m.memory_percent for m in online_nodes) / len(online_nodes), 1),
            'spark_workers_running': sum(1 for m in online_nodes if m.spark_worker_running)
        }

    def to_json(self) -> str:
        """Get all metrics as JSON."""
        metrics = self.collect_all()
        summary = self.get_cluster_summary()

        return json.dumps({
            'timestamp': time.time(),
            'summary': summary,
            'nodes': {name: asdict(m) for name, m in metrics.items()}
        }, indent=2)


if __name__ == "__main__":
    # Test the collector
    collector = NodeCollector()
    print(collector.to_json())

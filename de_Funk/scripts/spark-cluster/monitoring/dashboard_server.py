#!/usr/bin/env python3
"""
Cluster Monitoring Dashboard Server

A lightweight web server that displays real-time cluster metrics.
Uses Flask for simplicity - no external dependencies beyond Flask.

Usage:
    python dashboard_server.py [--port 8082] [--host 0.0.0.0]

Dashboard URL: http://<head-ip>:8082
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import socket

# Import the collector
from node_collector import NodeCollector


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the monitoring dashboard."""

    collector: NodeCollector = None  # Shared collector instance

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/':
            self.serve_dashboard()
        elif path == '/api/metrics':
            self.serve_metrics()
        elif path == '/api/summary':
            self.serve_summary()
        elif path == '/api/spark':
            self.serve_spark_info()
        else:
            self.send_error(404, 'Not Found')

    def serve_dashboard(self):
        """Serve the main dashboard HTML."""
        html = self.get_dashboard_html()
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def serve_metrics(self):
        """Serve node metrics as JSON."""
        try:
            metrics = self.collector.collect_all()
            summary = self.collector.get_cluster_summary()

            data = {
                'timestamp': time.time(),
                'summary': summary,
                'nodes': {
                    name: {
                        'name': m.name,
                        'ip': m.ip,
                        'status': m.status,
                        'cpu_percent': m.cpu_percent,
                        'cpu_cores': m.cpu_cores,
                        'load_1m': m.load_1m,
                        'load_5m': m.load_5m,
                        'load_15m': m.load_15m,
                        'memory_percent': m.memory_percent,
                        'memory_used_gb': m.memory_used_gb,
                        'memory_total_gb': m.memory_total_gb,
                        'disk_percent': m.disk_percent,
                        'disk_used_gb': m.disk_used_gb,
                        'disk_total_gb': m.disk_total_gb,
                        'spark_worker_running': m.spark_worker_running,
                        'error': m.error
                    }
                    for name, m in metrics.items()
                }
            }
            self.send_json(data)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def serve_summary(self):
        """Serve cluster summary as JSON."""
        try:
            summary = self.collector.get_cluster_summary()
            self.send_json(summary)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def serve_spark_info(self):
        """Fetch Spark cluster info from master."""
        try:
            import urllib.request
            config = self.collector.config
            head_ip = config['cluster']['head']['ip']
            spark_port = config['spark']['master']['ui_port']

            url = f"http://{head_ip}:{spark_port}/json/"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                self.send_json(data)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

    def get_dashboard_html(self) -> str:
        """Generate the dashboard HTML."""
        config = self.collector.config
        head_ip = config['cluster']['head']['ip']
        spark_port = config['spark']['master']['ui_port']

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>de_Funk Cluster Monitor</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }}
        .header h1 {{
            font-size: 24px;
            color: #4fc3f7;
        }}
        .header .links a {{
            color: #81d4fa;
            text-decoration: none;
            margin-left: 20px;
            padding: 8px 16px;
            border: 1px solid #4fc3f7;
            border-radius: 4px;
            transition: all 0.2s;
        }}
        .header .links a:hover {{
            background: #4fc3f7;
            color: #1a1a2e;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        .summary-card {{
            background: #16213e;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card .value {{
            font-size: 28px;
            font-weight: bold;
            color: #4fc3f7;
        }}
        .summary-card .label {{
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }}
        .nodes {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .node-card {{
            background: #16213e;
            border-radius: 10px;
            padding: 20px;
            position: relative;
        }}
        .node-card.offline {{
            opacity: 0.6;
            border: 1px solid #e74c3c;
        }}
        .node-card.head {{
            border: 2px solid #f39c12;
        }}
        .node-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .node-name {{
            font-size: 18px;
            font-weight: bold;
        }}
        .node-ip {{
            font-size: 12px;
            color: #888;
        }}
        .status-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .status-badge.online {{ background: #27ae60; color: white; }}
        .status-badge.offline {{ background: #e74c3c; color: white; }}
        .status-badge.error {{ background: #e67e22; color: white; }}
        .metrics {{
            display: grid;
            gap: 12px;
        }}
        .metric {{
            display: flex;
            flex-direction: column;
        }}
        .metric-header {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            margin-bottom: 4px;
        }}
        .metric-label {{ color: #888; }}
        .metric-value {{ color: #eee; font-weight: bold; }}
        .progress-bar {{
            height: 8px;
            background: #2c3e50;
            border-radius: 4px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        .progress-fill.cpu {{ background: linear-gradient(90deg, #3498db, #2980b9); }}
        .progress-fill.memory {{ background: linear-gradient(90deg, #9b59b6, #8e44ad); }}
        .progress-fill.disk {{ background: linear-gradient(90deg, #1abc9c, #16a085); }}
        .progress-fill.warning {{ background: linear-gradient(90deg, #f39c12, #e67e22); }}
        .progress-fill.danger {{ background: linear-gradient(90deg, #e74c3c, #c0392b); }}
        .spark-status {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #333;
            font-size: 12px;
        }}
        .spark-status.running {{ color: #27ae60; }}
        .spark-status.stopped {{ color: #e74c3c; }}
        .load-avg {{
            font-size: 11px;
            color: #666;
            margin-top: 4px;
        }}
        .refresh-info {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 20px;
        }}
        .error-msg {{
            color: #e74c3c;
            font-size: 11px;
            margin-top: 10px;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .updating {{ animation: pulse 1s ease-in-out; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>de_Funk Cluster Monitor</h1>
        <div class="links">
            <a href="http://{head_ip}:{spark_port}" target="_blank">Spark UI</a>
            <a href="http://{head_ip}:18080" target="_blank">History Server</a>
            <a href="http://{head_ip}:8081" target="_blank">Airflow</a>
        </div>
    </div>

    <div class="summary" id="summary">
        <div class="summary-card">
            <div class="value" id="online-nodes">-</div>
            <div class="label">Nodes Online</div>
        </div>
        <div class="summary-card">
            <div class="value" id="total-cores">-</div>
            <div class="label">Total Cores</div>
        </div>
        <div class="summary-card">
            <div class="value" id="total-memory">-</div>
            <div class="label">Total Memory (GB)</div>
        </div>
        <div class="summary-card">
            <div class="value" id="avg-cpu">-</div>
            <div class="label">Avg CPU %</div>
        </div>
        <div class="summary-card">
            <div class="value" id="avg-memory">-</div>
            <div class="label">Avg Memory %</div>
        </div>
        <div class="summary-card">
            <div class="value" id="spark-workers">-</div>
            <div class="label">Spark Workers</div>
        </div>
    </div>

    <div class="nodes" id="nodes"></div>

    <div class="refresh-info">
        Auto-refreshes every 5 seconds | Last update: <span id="last-update">-</span>
    </div>

    <script>
        function getProgressClass(value) {{
            if (value >= 90) return 'danger';
            if (value >= 75) return 'warning';
            return '';
        }}

        function renderNode(name, node, isHead) {{
            const statusClass = node.status;
            const headClass = isHead ? 'head' : '';

            const cpuClass = getProgressClass(node.cpu_percent);
            const memClass = getProgressClass(node.memory_percent);
            const diskClass = getProgressClass(node.disk_percent);

            const sparkStatus = node.spark_worker_running
                ? '<div class="spark-status running">&#9679; Spark Worker Running</div>'
                : '<div class="spark-status stopped">&#9675; Spark Worker Stopped</div>';

            const errorMsg = node.error
                ? `<div class="error-msg">${{node.error}}</div>`
                : '';

            return `
                <div class="node-card ${{statusClass}} ${{headClass}}">
                    <div class="node-header">
                        <div>
                            <div class="node-name">${{name}}${{isHead ? ' (Head)' : ''}}</div>
                            <div class="node-ip">${{node.ip}}</div>
                        </div>
                        <span class="status-badge ${{statusClass}}">${{node.status}}</span>
                    </div>
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-header">
                                <span class="metric-label">CPU</span>
                                <span class="metric-value">${{node.cpu_percent.toFixed(1)}}%</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill cpu ${{cpuClass}}" style="width: ${{node.cpu_percent}}%"></div>
                            </div>
                            <div class="load-avg">Load: ${{node.load_1m.toFixed(2)}} / ${{node.load_5m.toFixed(2)}} / ${{node.load_15m.toFixed(2)}} (${{node.cpu_cores}} cores)</div>
                        </div>
                        <div class="metric">
                            <div class="metric-header">
                                <span class="metric-label">Memory</span>
                                <span class="metric-value">${{node.memory_used_gb.toFixed(1)}} / ${{node.memory_total_gb.toFixed(1)}} GB (${{node.memory_percent.toFixed(1)}}%)</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill memory ${{memClass}}" style="width: ${{node.memory_percent}}%"></div>
                            </div>
                        </div>
                        <div class="metric">
                            <div class="metric-header">
                                <span class="metric-label">Disk</span>
                                <span class="metric-value">${{node.disk_used_gb.toFixed(1)}} / ${{node.disk_total_gb.toFixed(1)}} GB (${{node.disk_percent.toFixed(1)}}%)</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill disk ${{diskClass}}" style="width: ${{node.disk_percent}}%"></div>
                            </div>
                        </div>
                    </div>
                    ${{sparkStatus}}
                    ${{errorMsg}}
                </div>
            `;
        }}

        async function updateDashboard() {{
            try {{
                const response = await fetch('/api/metrics');
                const data = await response.json();

                // Update summary
                document.getElementById('online-nodes').textContent =
                    `${{data.summary.online_nodes}} / ${{data.summary.total_nodes}}`;
                document.getElementById('total-cores').textContent = data.summary.total_cores;
                document.getElementById('total-memory').textContent = data.summary.total_memory_gb.toFixed(0);
                document.getElementById('avg-cpu').textContent = data.summary.avg_cpu_percent.toFixed(1);
                document.getElementById('avg-memory').textContent = data.summary.avg_memory_percent.toFixed(1);
                document.getElementById('spark-workers').textContent = data.summary.spark_workers_running;

                // Update nodes
                const nodesContainer = document.getElementById('nodes');
                let nodesHtml = '';

                // Sort: head first, then workers
                const sortedNodes = Object.entries(data.nodes).sort((a, b) => {{
                    if (a[0] === 'bigbark') return -1;
                    if (b[0] === 'bigbark') return 1;
                    return a[0].localeCompare(b[0]);
                }});

                for (const [name, node] of sortedNodes) {{
                    const isHead = name === 'bigbark';
                    nodesHtml += renderNode(name, node, isHead);
                }}

                nodesContainer.innerHTML = nodesHtml;

                // Update timestamp
                const now = new Date();
                document.getElementById('last-update').textContent = now.toLocaleTimeString();

            }} catch (error) {{
                console.error('Failed to update dashboard:', error);
            }}
        }}

        // Initial load
        updateDashboard();

        // Auto-refresh every 5 seconds
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>'''


def run_server(host: str = '0.0.0.0', port: int = 8082):
    """Run the monitoring dashboard server."""
    # Initialize the collector
    DashboardHandler.collector = NodeCollector()

    server = HTTPServer((host, port), DashboardHandler)

    # Get the actual IP for display
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = host

    print(f"=" * 60)
    print(f"  de_Funk Cluster Monitoring Dashboard")
    print(f"=" * 60)
    print(f"  Dashboard:  http://{local_ip}:{port}")
    print(f"  API:        http://{local_ip}:{port}/api/metrics")
    print(f"=" * 60)
    print(f"  Press Ctrl+C to stop")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cluster Monitoring Dashboard')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8082, help='Port to listen on')
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)

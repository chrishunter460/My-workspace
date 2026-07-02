"""
Pipeline Run Tracker

Tracks all pipeline executions with timestamps, status, and results.
Provides historical logging and analysis of pipeline runs.
"""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class PipelineRunTracker:
    """
    Tracks pipeline executions and maintains a history log.
    """

    def __init__(self, log_dir: str = "logs/pipeline_runs"):
        """
        Initialize the run tracker.

        Args:
            log_dir: Directory to store run logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_run = None
        self.run_id = None

    def start_run(
        self,
        pipeline_type: str,
        config: Dict[str, Any]
    ) -> str:
        """
        Start tracking a new pipeline run.

        Args:
            pipeline_type: Type of pipeline (data_ingestion, forecasting, full)
            config: Configuration for this run

        Returns:
            Run ID
        """
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_run = {
            "run_id": self.run_id,
            "pipeline_type": pipeline_type,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "config": config,
            "results": {},
            "errors": [],
            "warnings": []
        }

        # Write initial run file
        self._save_run()

        print(f"📊 Run Tracker: Started run {self.run_id}")
        return self.run_id

    def log_stage(self, stage: str, status: str, details: Dict[str, Any] = None):
        """
        Log a pipeline stage completion.

        Args:
            stage: Stage name (e.g., "data_ingestion", "forecasting")
            status: Status (success, failed, skipped)
            details: Additional details about the stage
        """
        if not self.current_run:
            return

        if "stages" not in self.current_run:
            self.current_run["stages"] = []

        stage_info = {
            "stage": stage,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }

        self.current_run["stages"].append(stage_info)
        self._save_run()

        status_symbol = "✓" if status == "success" else "✗" if status == "failed" else "⊘"
        print(f"📊 Run Tracker: {status_symbol} Stage '{stage}' - {status}")

    def log_error(self, error: str, stage: str = None):
        """
        Log an error during pipeline execution.

        Args:
            error: Error message
            stage: Optional stage where error occurred
        """
        if not self.current_run:
            return

        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "error": error
        }

        self.current_run["errors"].append(error_entry)
        self._save_run()

        print(f"📊 Run Tracker: ✗ Error logged - {error[:100]}")

    def log_warning(self, warning: str, stage: str = None):
        """
        Log a warning during pipeline execution.

        Args:
            warning: Warning message
            stage: Optional stage where warning occurred
        """
        if not self.current_run:
            return

        warning_entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "warning": warning
        }

        self.current_run["warnings"].append(warning_entry)
        self._save_run()

        print(f"📊 Run Tracker: ⚠ Warning logged - {warning[:100]}")

    def update_results(self, results: Dict[str, Any]):
        """
        Update run results.

        Args:
            results: Results dictionary
        """
        if not self.current_run:
            return

        self.current_run["results"].update(results)
        self._save_run()

    def end_run(self, status: str, summary: Dict[str, Any] = None):
        """
        End the current pipeline run.

        Args:
            status: Final status (success, failed, partial)
            summary: Summary information
        """
        if not self.current_run:
            return

        self.current_run["end_time"] = datetime.now().isoformat()
        self.current_run["status"] = status

        if summary:
            self.current_run["summary"] = summary

        # Calculate duration
        start = datetime.fromisoformat(self.current_run["start_time"])
        end = datetime.fromisoformat(self.current_run["end_time"])
        duration = (end - start).total_seconds()
        self.current_run["duration_seconds"] = duration

        self._save_run()

        status_symbol = "✓" if status == "success" else "✗" if status == "failed" else "⚠"
        print(f"📊 Run Tracker: {status_symbol} Run {self.run_id} ended - {status}")
        print(f"📊 Run Tracker: Duration: {duration:.1f} seconds")

        # Update summary log
        self._update_summary_log()

        # Clear current run
        self.current_run = None
        self.run_id = None

    def _save_run(self):
        """Save current run to file."""
        if not self.current_run:
            return

        run_file = self.log_dir / f"run_{self.run_id}.json"
        with open(run_file, 'w') as f:
            json.dump(self.current_run, f, indent=2)

    def _update_summary_log(self):
        """Update the summary log with all runs."""
        summary_file = self.log_dir / "runs_summary.json"

        # Load existing summary
        if summary_file.exists():
            with open(summary_file, 'r') as f:
                summary = json.load(f)
        else:
            summary = {"runs": []}

        # Add current run summary
        run_summary = {
            "run_id": self.current_run["run_id"],
            "pipeline_type": self.current_run["pipeline_type"],
            "start_time": self.current_run["start_time"],
            "end_time": self.current_run["end_time"],
            "status": self.current_run["status"],
            "duration_seconds": self.current_run.get("duration_seconds"),
            "error_count": len(self.current_run["errors"]),
            "warning_count": len(self.current_run["warnings"])
        }

        summary["runs"].append(run_summary)

        # Keep only last 100 runs in summary
        summary["runs"] = summary["runs"][-100:]

        # Save summary
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

    @staticmethod
    def get_recent_runs(log_dir: str = "logs/pipeline_runs", count: int = 10) -> list:
        """
        Get recent pipeline runs.

        Args:
            log_dir: Directory containing run logs
            count: Number of recent runs to retrieve

        Returns:
            List of recent run summaries
        """
        summary_file = Path(log_dir) / "runs_summary.json"

        if not summary_file.exists():
            return []

        with open(summary_file, 'r') as f:
            summary = json.load(f)

        return summary["runs"][-count:]

    @staticmethod
    def print_recent_runs(log_dir: str = "logs/pipeline_runs", count: int = 5):
        """
        Print recent pipeline runs.

        Args:
            log_dir: Directory containing run logs
            count: Number of recent runs to display
        """
        runs = PipelineRunTracker.get_recent_runs(log_dir, count)

        if not runs:
            print("No pipeline runs found.")
            return

        print(f"\n{'='*80}")
        print(f"RECENT PIPELINE RUNS (Last {len(runs)})")
        print(f"{'='*80}")

        for run in reversed(runs):  # Most recent first
            status_symbol = "✓" if run["status"] == "success" else "✗" if run["status"] == "failed" else "⚠"
            duration = run.get("duration_seconds", 0)

            print(f"\n{status_symbol} Run ID: {run['run_id']}")
            print(f"  Type: {run['pipeline_type']}")
            print(f"  Status: {run['status']}")
            print(f"  Start: {run['start_time']}")
            print(f"  Duration: {duration:.1f}s")

            if run['error_count'] > 0:
                print(f"  Errors: {run['error_count']}")
            if run['warning_count'] > 0:
                print(f"  Warnings: {run['warning_count']}")

        print(f"\n{'='*80}\n")

"""
Checkpoint System - Resume capability for long-running ingestion pipelines.

Enables:
- Checkpoint state before/after processing each ticker
- Resume from last checkpoint on failure
- Track progress and failures
- Clear checkpoints when complete
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import threading

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TickerCheckpoint:
    """Checkpoint state for a single ticker."""
    ticker: str
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0
    data_endpoints: Dict[str, str] = field(default_factory=dict)  # endpoint -> status

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'TickerCheckpoint':
        return cls(**data)


@dataclass
class PipelineCheckpoint:
    """Checkpoint state for an entire pipeline run."""
    pipeline_id: str
    pipeline_name: str
    started_at: str
    last_updated: str
    status: str  # 'running', 'completed', 'failed', 'paused'
    total_tickers: int
    processed_count: int = 0
    failed_count: int = 0
    tickers: Dict[str, TickerCheckpoint] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = asdict(self)
        result['tickers'] = {k: v.to_dict() for k, v in self.tickers.items()}
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'PipelineCheckpoint':
        tickers = {k: TickerCheckpoint.from_dict(v) for k, v in data.get('tickers', {}).items()}
        data['tickers'] = tickers
        return cls(**data)


class CheckpointManager:
    """
    Manages checkpoint state for ingestion pipelines.

    Features:
    - Persistent checkpoints to JSON files
    - Thread-safe operations
    - Resume from failure
    - Progress tracking
    """

    DEFAULT_CHECKPOINT_DIR = "storage/checkpoints"

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        auto_save: bool = True,
        save_interval: int = 10  # Save every N ticker updates
    ):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files
            auto_save: Whether to auto-save after each update
            save_interval: If not auto_save, save every N updates
        """
        self.checkpoint_dir = Path(checkpoint_dir or self.DEFAULT_CHECKPOINT_DIR)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.auto_save = auto_save
        self.save_interval = save_interval
        self._update_count = 0
        self._lock = threading.Lock()
        self._current_checkpoint: Optional[PipelineCheckpoint] = None

    def _get_checkpoint_path(self, pipeline_id: str) -> Path:
        """Get path to checkpoint file."""
        return self.checkpoint_dir / f"{pipeline_id}.checkpoint.json"

    def create_checkpoint(
        self,
        pipeline_name: str,
        tickers: List[str],
        metadata: Dict[str, Any] = None
    ) -> PipelineCheckpoint:
        """
        Create a new checkpoint for a pipeline run.

        Args:
            pipeline_name: Name of the pipeline (e.g., 'alpha_vantage_ingestion')
            tickers: List of tickers to process
            metadata: Additional metadata (e.g., endpoint configs)

        Returns:
            New PipelineCheckpoint
        """
        now = datetime.now().isoformat()
        pipeline_id = f"{pipeline_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        ticker_checkpoints = {
            ticker: TickerCheckpoint(ticker=ticker, status='pending')
            for ticker in tickers
        }

        checkpoint = PipelineCheckpoint(
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            started_at=now,
            last_updated=now,
            status='running',
            total_tickers=len(tickers),
            tickers=ticker_checkpoints,
            metadata=metadata or {}
        )

        self._current_checkpoint = checkpoint
        self._save_checkpoint(checkpoint)

        logger.info(
            f"Created checkpoint '{pipeline_id}' for {len(tickers)} tickers"
        )

        return checkpoint

    def load_checkpoint(self, pipeline_id: str) -> Optional[PipelineCheckpoint]:
        """
        Load an existing checkpoint.

        Args:
            pipeline_id: Pipeline ID to load

        Returns:
            PipelineCheckpoint if found, None otherwise
        """
        path = self._get_checkpoint_path(pipeline_id)

        if not path.exists():
            logger.warning(f"Checkpoint not found: {pipeline_id}")
            return None

        try:
            with open(path, 'r') as f:
                data = json.load(f)
            checkpoint = PipelineCheckpoint.from_dict(data)
            self._current_checkpoint = checkpoint
            logger.info(
                f"Loaded checkpoint '{pipeline_id}': "
                f"{checkpoint.processed_count}/{checkpoint.total_tickers} processed"
            )
            return checkpoint
        except Exception as e:
            logger.error(f"Error loading checkpoint {pipeline_id}: {e}")
            return None

    def find_latest_checkpoint(self, pipeline_name: str) -> Optional[PipelineCheckpoint]:
        """
        Find the most recent checkpoint for a pipeline.

        Args:
            pipeline_name: Pipeline name to search for

        Returns:
            Most recent PipelineCheckpoint or None
        """
        pattern = f"{pipeline_name}_*.checkpoint.json"
        checkpoints = list(self.checkpoint_dir.glob(pattern))

        if not checkpoints:
            return None

        # Sort by modification time (most recent first)
        checkpoints.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Load the most recent
        latest_path = checkpoints[0]
        pipeline_id = latest_path.stem.replace('.checkpoint', '')

        return self.load_checkpoint(pipeline_id)

    def find_resumable_checkpoint(
        self,
        pipeline_name: str
    ) -> Optional[PipelineCheckpoint]:
        """
        Find a checkpoint that can be resumed (not completed).

        Args:
            pipeline_name: Pipeline name to search for

        Returns:
            Resumable checkpoint or None
        """
        checkpoint = self.find_latest_checkpoint(pipeline_name)

        if checkpoint and checkpoint.status in ('running', 'paused', 'failed'):
            pending = sum(
                1 for t in checkpoint.tickers.values()
                if t.status in ('pending', 'failed')
            )
            if pending > 0:
                logger.info(
                    f"Found resumable checkpoint '{checkpoint.pipeline_id}' "
                    f"with {pending} pending tickers"
                )
                return checkpoint

        return None

    def _save_checkpoint(self, checkpoint: PipelineCheckpoint) -> None:
        """Save checkpoint to disk."""
        path = self._get_checkpoint_path(checkpoint.pipeline_id)

        with self._lock:
            try:
                with open(path, 'w') as f:
                    json.dump(checkpoint.to_dict(), f, indent=2, default=str)
            except Exception as e:
                logger.error(f"Error saving checkpoint: {e}")

    def _maybe_save(self) -> None:
        """Save if auto_save or save_interval reached."""
        if self._current_checkpoint is None:
            return

        self._update_count += 1

        if self.auto_save or self._update_count >= self.save_interval:
            self._save_checkpoint(self._current_checkpoint)
            self._update_count = 0

    def mark_ticker_started(self, ticker: str) -> None:
        """Mark a ticker as started processing."""
        if self._current_checkpoint is None:
            return

        with self._lock:
            if ticker in self._current_checkpoint.tickers:
                tc = self._current_checkpoint.tickers[ticker]
                tc.status = 'in_progress'
                tc.started_at = datetime.now().isoformat()
                self._current_checkpoint.last_updated = datetime.now().isoformat()

        self._maybe_save()
        logger.debug(f"Ticker started: {ticker}")

    def mark_ticker_completed(self, ticker: str, endpoints: Dict[str, str] = None) -> None:
        """
        Mark a ticker as completed.

        Args:
            ticker: Ticker symbol
            endpoints: Dict of endpoint -> status for this ticker
        """
        if self._current_checkpoint is None:
            return

        with self._lock:
            if ticker in self._current_checkpoint.tickers:
                tc = self._current_checkpoint.tickers[ticker]
                tc.status = 'completed'
                tc.completed_at = datetime.now().isoformat()
                tc.data_endpoints = endpoints or {}
                self._current_checkpoint.processed_count += 1
                self._current_checkpoint.last_updated = datetime.now().isoformat()

        self._maybe_save()
        logger.debug(
            f"Ticker completed: {ticker} "
            f"({self._current_checkpoint.processed_count}/{self._current_checkpoint.total_tickers})"
        )

    def mark_ticker_failed(self, ticker: str, error: str) -> None:
        """Mark a ticker as failed."""
        if self._current_checkpoint is None:
            return

        with self._lock:
            if ticker in self._current_checkpoint.tickers:
                tc = self._current_checkpoint.tickers[ticker]
                tc.status = 'failed'
                tc.error = error
                tc.retries += 1
                tc.completed_at = datetime.now().isoformat()
                self._current_checkpoint.failed_count += 1
                self._current_checkpoint.last_updated = datetime.now().isoformat()

        self._maybe_save()
        logger.warning(f"Ticker failed: {ticker} - {error}")

    def get_pending_tickers(self) -> List[str]:
        """Get list of tickers that still need processing."""
        if self._current_checkpoint is None:
            return []

        with self._lock:
            return [
                ticker for ticker, tc in self._current_checkpoint.tickers.items()
                if tc.status in ('pending', 'failed')
            ]

    def get_failed_tickers(self) -> List[str]:
        """Get list of failed tickers."""
        if self._current_checkpoint is None:
            return []

        with self._lock:
            return [
                ticker for ticker, tc in self._current_checkpoint.tickers.items()
                if tc.status == 'failed'
            ]

    def mark_pipeline_completed(self) -> None:
        """Mark the entire pipeline as completed."""
        if self._current_checkpoint is None:
            return

        with self._lock:
            self._current_checkpoint.status = 'completed'
            self._current_checkpoint.last_updated = datetime.now().isoformat()

        self._save_checkpoint(self._current_checkpoint)
        logger.info(
            f"Pipeline completed: {self._current_checkpoint.pipeline_id} - "
            f"{self._current_checkpoint.processed_count} processed, "
            f"{self._current_checkpoint.failed_count} failed"
        )

    def mark_pipeline_failed(self, error: str) -> None:
        """Mark the entire pipeline as failed."""
        if self._current_checkpoint is None:
            return

        with self._lock:
            self._current_checkpoint.status = 'failed'
            self._current_checkpoint.metadata['final_error'] = error
            self._current_checkpoint.last_updated = datetime.now().isoformat()

        self._save_checkpoint(self._current_checkpoint)
        logger.error(f"Pipeline failed: {self._current_checkpoint.pipeline_id} - {error}")

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress summary."""
        if self._current_checkpoint is None:
            return {"status": "no_checkpoint"}

        cp = self._current_checkpoint
        return {
            "pipeline_id": cp.pipeline_id,
            "status": cp.status,
            "total": cp.total_tickers,
            "processed": cp.processed_count,
            "failed": cp.failed_count,
            "pending": cp.total_tickers - cp.processed_count - cp.failed_count,
            "percent_complete": round(
                (cp.processed_count / cp.total_tickers * 100)
                if cp.total_tickers > 0 else 0, 1
            ),
            "started_at": cp.started_at,
            "last_updated": cp.last_updated,
        }

    def clear_checkpoint(self, pipeline_id: str = None) -> bool:
        """
        Clear a checkpoint file.

        Args:
            pipeline_id: Specific checkpoint to clear, or current if None

        Returns:
            True if cleared successfully
        """
        if pipeline_id is None and self._current_checkpoint:
            pipeline_id = self._current_checkpoint.pipeline_id

        if pipeline_id is None:
            return False

        path = self._get_checkpoint_path(pipeline_id)

        try:
            if path.exists():
                path.unlink()
                logger.info(f"Cleared checkpoint: {pipeline_id}")

            if self._current_checkpoint and self._current_checkpoint.pipeline_id == pipeline_id:
                self._current_checkpoint = None

            return True
        except Exception as e:
            logger.error(f"Error clearing checkpoint {pipeline_id}: {e}")
            return False

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all available checkpoints."""
        checkpoints = []

        for path in self.checkpoint_dir.glob("*.checkpoint.json"):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                checkpoints.append({
                    "pipeline_id": data.get("pipeline_id"),
                    "pipeline_name": data.get("pipeline_name"),
                    "status": data.get("status"),
                    "total_tickers": data.get("total_tickers"),
                    "processed_count": data.get("processed_count"),
                    "failed_count": data.get("failed_count"),
                    "started_at": data.get("started_at"),
                    "last_updated": data.get("last_updated"),
                })
            except Exception as e:
                logger.warning(f"Error reading checkpoint {path}: {e}")

        # Sort by last_updated descending
        checkpoints.sort(key=lambda x: x.get("last_updated", ""), reverse=True)

        return checkpoints

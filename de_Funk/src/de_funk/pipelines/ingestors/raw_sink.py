"""
RawSink — writes raw API responses to the Raw storage tier.

Raw data is the first landing zone for all external API data.
Files are stored as-is (JSON, CSV, etc.) before Bronze normalization.

Storage layout:
    raw_root/{provider}/{endpoint}/{partition_key}/data.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class RawSink:
    """Writes raw API responses to the raw storage tier."""

    def __init__(self, raw_root: str | Path, session=None):
        self.raw_root = Path(raw_root)
        self.session = session

    def write(self, data: Any, provider: str, endpoint: str,
              partition: str = "") -> Path:
        """Write raw data to storage.

        Args:
            data: Raw API response data (dict, list, str, or bytes)
            provider: Provider name (e.g. "alpha_vantage")
            endpoint: Endpoint name (e.g. "time_series_daily")
            partition: Optional partition key (e.g. "AAPL" or "2024-01-15")

        Returns:
            Path to the written file
        """
        dir_path = self.raw_root / provider / endpoint
        if partition:
            dir_path = dir_path / partition
        dir_path.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            file_path = dir_path / "data.bin"
            with open(file_path, "wb") as f:
                f.write(data)
        elif isinstance(data, str):
            file_path = dir_path / "data.txt"
            with open(file_path, "w") as f:
                f.write(data)
        else:
            file_path = dir_path / "data.json"
            with open(file_path, "w") as f:
                json.dump(data, f, default=str)

        logger.debug(f"RawSink: wrote {file_path}")
        return file_path

    def exists(self, provider: str, endpoint: str,
               partition: str = "") -> bool:
        """Check if raw data exists for a provider/endpoint/partition."""
        dir_path = self.raw_root / provider / endpoint
        if partition:
            dir_path = dir_path / partition
        return dir_path.exists() and any(dir_path.iterdir())

    def read(self, provider: str, endpoint: str,
             partition: str = "") -> Any:
        """Read raw data for a provider/endpoint/partition.

        Returns:
            Parsed data (dict/list for JSON, str for text, bytes for binary)
        """
        dir_path = self.raw_root / provider / endpoint
        if partition:
            dir_path = dir_path / partition

        json_path = dir_path / "data.json"
        if json_path.exists():
            with open(json_path) as f:
                return json.load(f)

        txt_path = dir_path / "data.txt"
        if txt_path.exists():
            with open(txt_path) as f:
                return f.read()

        bin_path = dir_path / "data.bin"
        if bin_path.exists():
            with open(bin_path, "rb") as f:
                return f.read()

        raise FileNotFoundError(f"No raw data at {dir_path}")

"""Tests for Ingest Path Migration — Phase 9."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock


class TestRawSink:
    def test_write_json(self, tmp_path):
        from de_funk.pipelines.ingestors.raw_sink import RawSink
        sink = RawSink(raw_root=tmp_path)
        data = {"key": "value", "count": 42}
        path = sink.write(data, "alpha_vantage", "daily", partition="AAPL")
        assert path.exists()
        assert path.name == "data.json"

    def test_write_text(self, tmp_path):
        from de_funk.pipelines.ingestors.raw_sink import RawSink
        sink = RawSink(raw_root=tmp_path)
        path = sink.write("csv,data,here", "alpha_vantage", "daily")
        assert path.exists()
        assert path.name == "data.txt"

    def test_write_bytes(self, tmp_path):
        from de_funk.pipelines.ingestors.raw_sink import RawSink
        sink = RawSink(raw_root=tmp_path)
        path = sink.write(b"\x00\x01\x02", "provider", "endpoint")
        assert path.exists()
        assert path.name == "data.bin"

    def test_exists(self, tmp_path):
        from de_funk.pipelines.ingestors.raw_sink import RawSink
        sink = RawSink(raw_root=tmp_path)
        assert not sink.exists("alpha_vantage", "daily", "AAPL")
        sink.write({"x": 1}, "alpha_vantage", "daily", "AAPL")
        assert sink.exists("alpha_vantage", "daily", "AAPL")

    def test_read_json(self, tmp_path):
        from de_funk.pipelines.ingestors.raw_sink import RawSink
        sink = RawSink(raw_root=tmp_path)
        sink.write({"key": "value"}, "prov", "ep")
        data = sink.read("prov", "ep")
        assert data["key"] == "value"

    def test_read_not_found(self, tmp_path):
        from de_funk.pipelines.ingestors.raw_sink import RawSink
        sink = RawSink(raw_root=tmp_path)
        with pytest.raises(FileNotFoundError):
            sink.read("nonexistent", "endpoint")

    def test_path_resolution(self, tmp_path):
        from de_funk.pipelines.ingestors.raw_sink import RawSink
        sink = RawSink(raw_root=tmp_path)
        sink.write({"x": 1}, "alpha_vantage", "daily", "AAPL")
        expected = tmp_path / "alpha_vantage" / "daily" / "AAPL" / "data.json"
        assert expected.exists()


class TestProviderAcceptsSession:
    def test_provider_session_param(self):
        import inspect
        from de_funk.pipelines.base.provider import BaseProvider
        sig = inspect.signature(BaseProvider.__init__)
        assert "session" in sig.parameters

    def test_provider_backward_compat(self):
        """Provider works without session (backward compat)."""
        from de_funk.pipelines.base.provider import BaseProvider
        # Can't instantiate ABC directly, but we can check the init signature
        import inspect
        params = inspect.signature(BaseProvider.__init__).parameters
        assert params["session"].default is None


class TestIngestorEngineAcceptsSession:
    def test_ingestor_session_param(self):
        import inspect
        from de_funk.pipelines.base.ingestor_engine import IngestorEngine
        sig = inspect.signature(IngestorEngine.__init__)
        assert "session" in sig.parameters


class TestBronzeSinkAcceptsSession:
    def test_bronze_sink_session_param(self):
        import inspect
        from de_funk.pipelines.ingestors.bronze_sink import BronzeSink
        sig = inspect.signature(BronzeSink.__init__)
        assert "session" in sig.parameters

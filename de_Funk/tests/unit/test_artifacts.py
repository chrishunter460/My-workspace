"""Tests for ModelArtifact and ArtifactStore."""
import pytest
import tempfile
from pathlib import Path

from de_funk.core.artifacts import ModelArtifact, ArtifactStore


@pytest.fixture
def tmp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ArtifactStore(models_root=tmpdir)


class TestModelArtifact:
    def test_defaults(self):
        artifact = ModelArtifact(model_name="arima_aapl", version="v1")
        assert artifact.model_name == "arima_aapl"
        assert artifact.version == "v1"
        assert artifact.status == "active"
        assert artifact.trained_at != ""

    def test_to_dict(self):
        artifact = ModelArtifact(model_name="test", version="v1")
        d = artifact.to_dict()
        assert d["model_name"] == "test"
        assert "trained_at" in d

    def test_from_dict(self):
        data = {"model_name": "test", "version": "v2", "status": "retired"}
        artifact = ModelArtifact.from_dict(data)
        assert artifact.model_name == "test"
        assert artifact.version == "v2"
        assert artifact.status == "retired"


class TestArtifactStore:
    def test_save_and_load(self, tmp_store):
        artifact = ModelArtifact(model_name="test_model", version="v1", metrics={"rmse": 0.05})
        model_object = {"weights": [1, 2, 3]}

        path = tmp_store.save(artifact, model_object)
        assert path.exists()

        loaded_artifact, loaded_model = tmp_store.load("test_model", "v1")
        assert loaded_artifact.model_name == "test_model"
        assert loaded_artifact.metrics["rmse"] == 0.05
        assert loaded_model["weights"] == [1, 2, 3]

    def test_list_versions(self, tmp_store):
        for v in ["v1", "v2", "v3"]:
            artifact = ModelArtifact(model_name="multi_ver", version=v)
            tmp_store.save(artifact, {"v": v})

        versions = tmp_store.list_versions("multi_ver")
        assert len(versions) == 3
        assert versions[0].version == "v1"

    def test_latest(self, tmp_store):
        for v in ["v1", "v2"]:
            artifact = ModelArtifact(model_name="latest_test", version=v)
            tmp_store.save(artifact, {"v": v})

        result = tmp_store.latest("latest_test")
        assert result is not None
        artifact, model = result
        assert artifact.version == "v2"

    def test_load_not_found(self, tmp_store):
        with pytest.raises(FileNotFoundError):
            tmp_store.load("nonexistent", "v1")

    def test_list_empty(self, tmp_store):
        versions = tmp_store.list_versions("nonexistent")
        assert versions == []

    def test_latest_empty(self, tmp_store):
        result = tmp_store.latest("nonexistent")
        assert result is None

    def test_register_metadata_only(self, tmp_store):
        artifact = ModelArtifact(model_name="registered", version="v1")
        tmp_store.register(artifact)

        versions = tmp_store.list_versions("registered")
        assert len(versions) == 1
        assert versions[0].model_name == "registered"

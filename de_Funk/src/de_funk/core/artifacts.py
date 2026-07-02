"""
Model Artifacts — trained ML model lifecycle management.

Stores trained model artifacts (pickle/joblib) separately from
prediction results (Silver Delta tables). Supports versioning,
recall, and staleness detection for retraining.

Storage layout:
    /storage/models/{model_name}/{version}/
        model.pkl          ← trained model artifact
        metadata.json      ← ModelArtifact fields
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field as dc_field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ModelArtifact:
    """Metadata for a trained ML model artifact."""
    model_name: str
    version: str
    trained_at: str = ""  # ISO format datetime
    artifact_path: str = ""
    metrics: dict = dc_field(default_factory=dict)
    config: dict = dc_field(default_factory=dict)
    status: str = "active"

    def __post_init__(self):
        if not self.trained_at:
            self.trained_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> ModelArtifact:
        return ModelArtifact(**{k: v for k, v in data.items() if k in ModelArtifact.__dataclass_fields__})


class ArtifactStore:
    """Manages trained model artifacts on disk.

    Artifacts are stored separately from Silver data:
        /storage/models/{model_name}/{version}/model.pkl
        /storage/models/{model_name}/{version}/metadata.json
    """

    def __init__(self, models_root: str | Path):
        self.models_root = Path(models_root)

    def save(self, artifact: ModelArtifact, model_object: Any) -> Path:
        """Save a trained model artifact + metadata."""
        artifact_dir = self.models_root / artifact.model_name / artifact.version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Save model object
        model_path = artifact_dir / "model.pkl"
        try:
            import pickle
            with open(model_path, 'wb') as f:
                pickle.dump(model_object, f)
            artifact.artifact_path = str(model_path)
            logger.info(f"Saved model artifact: {model_path}")
        except Exception as e:
            logger.error(f"Failed to save model artifact: {e}")
            raise

        # Save metadata
        meta_path = artifact_dir / "metadata.json"
        with open(meta_path, 'w') as f:
            json.dump(artifact.to_dict(), f, indent=2)

        return model_path

    def load(self, model_name: str, version: str) -> tuple[ModelArtifact, Any]:
        """Load a trained model artifact by name and version."""
        artifact_dir = self.models_root / model_name / version
        if not artifact_dir.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact_dir}")

        # Load metadata
        meta_path = artifact_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path) as f:
                artifact = ModelArtifact.from_dict(json.load(f))
        else:
            artifact = ModelArtifact(model_name=model_name, version=version)

        # Load model object
        model_path = artifact_dir / "model.pkl"
        if model_path.exists():
            import pickle
            with open(model_path, 'rb') as f:
                model_object = pickle.load(f)
        else:
            model_object = None

        return artifact, model_object

    def latest(self, model_name: str) -> tuple[ModelArtifact, Any] | None:
        """Load the most recent version of a model."""
        versions = self.list_versions(model_name)
        if not versions:
            return None
        latest_version = versions[-1]
        return self.load(model_name, latest_version.version)

    def list_versions(self, model_name: str) -> list[ModelArtifact]:
        """List all versions of a model, sorted by trained_at."""
        model_dir = self.models_root / model_name
        if not model_dir.exists():
            return []

        artifacts = []
        for version_dir in sorted(model_dir.iterdir()):
            if version_dir.is_dir():
                meta_path = version_dir / "metadata.json"
                if meta_path.exists():
                    with open(meta_path) as f:
                        artifacts.append(ModelArtifact.from_dict(json.load(f)))
                else:
                    artifacts.append(ModelArtifact(
                        model_name=model_name,
                        version=version_dir.name,
                    ))

        return sorted(artifacts, key=lambda a: a.trained_at)

    def register(self, artifact: ModelArtifact) -> None:
        """Register an artifact (save metadata only, no model object)."""
        artifact_dir = self.models_root / artifact.model_name / artifact.version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        meta_path = artifact_dir / "metadata.json"
        with open(meta_path, 'w') as f:
            json.dump(artifact.to_dict(), f, indent=2)
        logger.info(f"Registered artifact: {artifact.model_name} v{artifact.version}")

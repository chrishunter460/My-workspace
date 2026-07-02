"""
BaseModelBuilder — builds Silver tables from domain configs.

Takes a BuildSession directly — no BuildContext intermediary.
Each builder declares model_name, depends_on, and get_model_class().

BuildResult captures the outcome of a build.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Type
from pathlib import Path
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of a model build operation."""
    model_name: str
    success: bool
    dimensions: int = 0
    facts: int = 0
    rows_written: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.success:
            return (f"✓ {self.model_name}: {self.dimensions} dims, "
                    f"{self.facts} facts ({self.duration_seconds:.1f}s)")
        return f"✗ {self.model_name}: {self.error}"


class BaseModelBuilder(ABC):
    """Abstract builder for domain models. Takes BuildSession directly."""

    model_name: str = ""
    depends_on: List[str] = []

    def __init__(self, session):
        """
        Args:
            session: BuildSession with engine, storage_router, models, graph
        """
        self.session = session
        self._model_config = None

    @abstractmethod
    def get_model_class(self) -> Type:
        """Return the model class to instantiate."""
        pass

    def get_model_config(self) -> Dict[str, Any]:
        """Load model config from domain markdown and produce build plan.

        Uses BuildPlanner to interpret config → executable plan.
        Returns the translated dict for backward compat with DomainModel.
        """
        if self._model_config is None:
            from de_funk.config.domain import get_domain_loader
            from de_funk.models.base.build_planner import BuildPlanner
            repo_root = Path(self.session._kwargs.get('repo_root', '.'))
            domains_dir = repo_root / "domains"
            loader = get_domain_loader(domains_dir)
            raw_config = loader.load_model_config(self.model_name)
            planner = BuildPlanner()
            plan = planner.plan(raw_config)
            # Store both typed plan and compat dict
            self._build_plan = plan
            self._model_config = {**raw_config, **plan.to_translated_dict()}
        return self._model_config

    def build(self) -> BuildResult:
        """Build the model: instantiate → build → write."""
        from de_funk.core.error_handling import ErrorContext
        from de_funk.core.exceptions import ModelError, StorageError, ConfigurationError

        start = time.time()
        try:
            with ErrorContext("Load config", model=self.model_name):
                model_config = self.get_model_config()
                model_class = self.get_model_class()

            params = {
                "repo_root": str(Path(self.session._kwargs.get('repo_root', '.'))),
                "DATE_FROM": self.session._kwargs.get('date_from', '2020-01-01'),
                "DATE_TO": self.session._kwargs.get('date_to', '2026-12-31'),
            }
            if self.session._kwargs.get('max_tickers'):
                params["UNIVERSE_SIZE"] = self.session._kwargs['max_tickers']

            with ErrorContext("Build tables", model=self.model_name):
                model = model_class(
                    session=self.session,
                    model_cfg=model_config,
                    params=params,
                )
                dims, facts = model.build()

            with ErrorContext("Write Silver", model=self.model_name):
                model.write_tables()

            return BuildResult(
                model_name=self.model_name,
                success=True,
                dimensions=len(dims),
                facts=len(facts),
                duration_seconds=time.time() - start,
            )

        except ConfigurationError as e:
            logger.error(f"Config error building {self.model_name}: {e}")
            return BuildResult(
                model_name=self.model_name, success=False,
                error=f"[CONFIG] {e}", duration_seconds=time.time() - start,
            )
        except StorageError as e:
            logger.error(f"Storage error building {self.model_name}: {e}")
            return BuildResult(
                model_name=self.model_name, success=False,
                error=f"[STORAGE] {e}", duration_seconds=time.time() - start,
            )
        except ModelError as e:
            logger.error(f"Model error building {self.model_name}: {e}")
            return BuildResult(
                model_name=self.model_name, success=False,
                error=f"[MODEL] {e}", duration_seconds=time.time() - start,
            )
        except Exception as e:
            logger.error(f"Build failed for {self.model_name}: {e}", exc_info=True)
            return BuildResult(
                model_name=self.model_name, success=False,
                error=str(e), duration_seconds=time.time() - start,
            )

    @classmethod
    def get_dependencies(cls) -> List[str]:
        return cls.depends_on if cls.depends_on else []


class BuilderRegistry:
    """Registry of discovered model builders."""
    _builders: Dict[str, Type[BaseModelBuilder]] = {}

    @classmethod
    def register(cls, builder_class: Type[BaseModelBuilder]) -> Type[BaseModelBuilder]:
        cls._builders[builder_class.model_name] = builder_class
        return builder_class

    @classmethod
    def all(cls) -> Dict[str, Type[BaseModelBuilder]]:
        return dict(cls._builders)

    @classmethod
    def discover(cls, models_path: Path) -> None:
        """Discover builders from Python modules."""
        import importlib
        if not models_path.exists():
            return
        for builder_file in models_path.rglob("builder.py"):
            rel = builder_file.relative_to(models_path.parent.parent)
            module_name = "de_funk." + str(rel).replace("/", ".").replace(".py", "")
            try:
                mod = importlib.import_module(module_name)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type) and issubclass(attr, BaseModelBuilder)
                            and attr is not BaseModelBuilder and hasattr(attr, 'model_name')
                            and attr.model_name):
                        cls.register(attr)
            except Exception as e:
                logger.debug(f"Could not load {module_name}: {e}")

    @classmethod
    def clear(cls):
        cls._builders.clear()

"""
Domain Builder Factory - Dynamic builder registration for domain models.

Creates builder classes on-the-fly for each domain model config,
registering them with BuilderRegistry so build_models.py can
discover and build them. This is the SOLE builder discovery path
(v3 builders are sunset).
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Type

logger = logging.getLogger(__name__)

# Custom model classes for models with specialized build logic.
# Maps model_name -> (module_path, class_name).
# Models not listed here use the generic DomainModel.
# All models use generic DomainModel. Custom logic lives in hooks/:
#   temporal: hooks/temporal/calendar.py (custom_node_loading → @pipeline_hook)
#   corporate.entity: hooks/corporate/cik_enrichment.py (after_build → YAML hook)
#   securities.forecast: hooks/securities/forecast.py (post_build → YAML hook)
CUSTOM_MODEL_CLASSES = {}


def _import_model_class(module_path: str, class_name: str) -> type:
    """Import and return a model class by module path and class name."""
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class DomainBuilderFactory:
    """
    Factory that scans domain configs and creates builder classes.

    Each generated builder:
    - Has model_name and depends_on from the domain config
    - Uses DomainConfigLoader + translate_domain_config() for config loading
    - Returns the appropriate model class (custom or DomainModel)
    - Registers with BuilderRegistry
    """

    @classmethod
    def create_builders(
        cls,
        domains_dir: Path,
    ) -> Dict[str, Any]:
        """
        Scan domain configs and create/register builder classes.

        Args:
            domains_dir: Path to domains/ directory

        Returns:
            Dict of model_name -> builder_class for all created builders
        """
        from de_funk.config.domain import DomainConfigLoader, get_domain_loader
        from de_funk.models.base.builder import BuilderRegistry

        # Check if this is actually a domain config directory
        loader = get_domain_loader(domains_dir)
        if not isinstance(loader, DomainConfigLoader):
            logger.debug(f"{domains_dir} is not a domain config directory")
            return {}

        created = {}

        for model_name in loader.list_models():
            try:
                # Load minimal config to get depends_on
                config = loader.load_model_config(model_name)
                depends = config.get("depends_on", [])
                if isinstance(depends, str):
                    depends = [depends]

                # Create a dynamic builder class
                builder_class = cls._create_builder_class(
                    model_name, depends, domains_dir
                )

                # Register with the registry
                BuilderRegistry.register(builder_class)
                created[model_name] = builder_class

                logger.debug(f"Registered domain builder: {model_name}")

            except Exception as e:
                logger.warning(
                    f"Failed to create domain builder for '{model_name}': {e}"
                )

        if created:
            logger.info(
                f"Registered {len(created)} domain builders: "
                f"{', '.join(sorted(created.keys()))}"
            )

        return created

    @classmethod
    def _create_builder_class(
        cls,
        model_name: str,
        depends_on: List[str],
        domains_dir: Path,
    ) -> type:
        """
        Create a dynamic builder class for a domain model.

        Uses type() to create a new class with the correct model_name
        and depends_on attributes. If the model has a custom model class
        registered in CUSTOM_MODEL_CLASSES, uses that instead of DomainModel.
        """
        from de_funk.models.base.builder import BaseModelBuilder

        class_name = f"DomainBuilder_{model_name.replace('-', '_').replace('.', '_')}"

        # Determine the model class to use
        custom_spec = CUSTOM_MODEL_CLASSES.get(model_name)

        def get_model_class(self) -> type:
            spec = CUSTOM_MODEL_CLASSES.get(self.model_name)
            if spec:
                try:
                    return _import_model_class(spec[0], spec[1])
                except (ImportError, AttributeError) as e:
                    logger.warning(
                        f"Custom model class for '{self.model_name}' "
                        f"not found ({e}), falling back to DomainModel"
                    )
            from de_funk.models.base.domain_model import DomainModel
            return DomainModel

        def get_model_config(self) -> Dict[str, Any]:
            if self._model_config is None:
                from de_funk.config.domain import DomainConfigLoader
                from de_funk.models.base.build_planner import BuildPlanner

                loader = DomainConfigLoader(self._domains_dir)
                raw_config = loader.load_model_config(self.model_name)
                planner = BuildPlanner()
                plan = planner.plan(raw_config)
                self._build_plan = plan
                self._model_config = {**raw_config, **plan.to_translated_dict()}

            return self._model_config

        def pre_build(self) -> None:
            """Skip bronze validation — domain sources are more complex."""
            logger.info(f"Pre-build for domain model: {self.model_name}")

        def post_build(self, result) -> None:
            """Run post_build hooks declared in model YAML."""
            cfg = self.get_model_config()
            build_cfg = cfg.get("build", {}) if isinstance(cfg, dict) else {}
            steps = build_cfg.get("post_build", [])
            if not steps:
                return
            logger.info(f"Running {len(steps)} post_build step(s) for {self.model_name}...")
            # Post-build steps are now handled by _run_hooks("post_build")
            # on the model instance, which reads hooks from YAML config
            # and dispatches to plugin registry functions

        # Build the class with type()
        attrs = {
            "model_name": model_name,
            "depends_on": depends_on,
            "_domains_dir": domains_dir,
            "get_model_class": get_model_class,
            "get_model_config": get_model_config,
            "pre_build": pre_build,
            "post_build": post_build,
        }

        builder_class = type(class_name, (BaseModelBuilder,), attrs)
        return builder_class


def discover_domain_builders(repo_root: Path) -> Dict[str, Any]:
    """
    Discover and register domain builders from the domains/ directory.

    This is the sole builder discovery entry point (v3 builders are sunset).

    Args:
        repo_root: Repository root path

    Returns:
        Dict of created builder classes
    """
    domains_dir = repo_root / "domains"
    if not domains_dir.exists():
        return {}

    return DomainBuilderFactory.create_builders(domains_dir)


# Backward-compatible aliases
V4BuilderFactory = DomainBuilderFactory
discover_v4_builders = discover_domain_builders

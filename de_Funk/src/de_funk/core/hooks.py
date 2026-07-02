"""
HookRunner — config-first hook dispatch.

Reads hooks from YAML config (model.md hooks: section), imports and
calls the declared Python functions. Falls back to @pipeline_hook
decorated functions for hooks that can't be expressed in YAML
(e.g. custom_node_loading which returns a DataFrame).

Config is king — YAML hooks are checked first. Python decorators
are the escape hatch for complex logic.

Usage:
    runner = HookRunner(model_cfg, model_name="securities.stocks")
    runner.run("post_build", engine=engine, model=model)

    # Or with the decorator fallback:
    @pipeline_hook("custom_node_loading", model="temporal")
    def generate_calendar(engine, config, **params):
        return calendar_df  # Can't do this in YAML
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, List

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


# ── Decorator registry (fallback for non-YAML hooks) ──────

_decorator_registry: Dict[str, Dict[str, List[Callable]]] = {}


def pipeline_hook(hook_type: str, model: str = "*"):
    """Decorator to register a hook function.

    Use for hooks that CAN'T be declared in YAML — typically because
    they return a value (like custom_node_loading returning a DataFrame).

    For hooks that are side effects (pre/post build, training, etc.),
    prefer declaring them in model.md hooks: section instead.

    Args:
        hook_type: Hook point (pre_build, before_build, after_build,
                   post_build, custom_node_loading)
        model: Model name or "*" for all models
    """
    def decorator(fn: Callable) -> Callable:
        _decorator_registry.setdefault(hook_type, {}).setdefault(model, []).append(fn)
        logger.debug(f"Registered @pipeline_hook: {hook_type}/{model} → {fn.__name__}")
        return fn
    return decorator


def discover_hooks(hooks_dir: str = "de_funk.hooks"):
    """Auto-discover hook modules from the hooks/ directory tree.

    Recursively imports all .py files under hooks/, which triggers
    @pipeline_hook registration for decorated functions.
    """
    import pkgutil
    try:
        package = importlib.import_module(hooks_dir)
        for importer, name, is_pkg in pkgutil.walk_packages(
            package.__path__, prefix=f"{hooks_dir}."
        ):
            if name.endswith("__init__"):
                continue
            try:
                importlib.import_module(name)
                logger.debug(f"Discovered hook module: {name}")
            except Exception as e:
                logger.debug(f"Could not load {name}: {e}")
    except (ModuleNotFoundError, AttributeError) as e:
        logger.debug(f"No hooks at {hooks_dir}: {e}")


def discover_plugins(hooks_dir: str = "de_funk.hooks"):
    """Backward compat — redirects to discover_hooks for old plugins/ dir."""
    discover_hooks(hooks_dir)


def catalog(hooks_dir: str = "de_funk.hooks") -> dict:
    """Build a catalog of all available hooks by scanning docstrings.

    Returns dict of {dotted_path: {trigger, domain, description, params}}.
    """
    import pkgutil
    import inspect

    discover_hooks(hooks_dir)
    result = {}

    try:
        package = importlib.import_module(hooks_dir)
        for importer, mod_name, is_pkg in pkgutil.walk_packages(
            package.__path__, prefix=f"{hooks_dir}."
        ):
            if mod_name.endswith("__init__"):
                continue
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue

            for name, obj in inspect.getmembers(mod, inspect.isfunction):
                if name.startswith("_"):
                    continue
                # Skip imported utility functions (get_logger, pipeline_hook, etc.)
                if obj.__module__ != mod.__name__:
                    continue
                doc = inspect.getdoc(obj) or ""
                entry = {"description": doc.split("\n")[0] if doc else ""}

                # Parse structured docstring fields
                for line in doc.split("\n"):
                    line = line.strip()
                    if line.startswith("Trigger:"):
                        entry["trigger"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Domain:"):
                        entry["domain"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Params:"):
                        entry["params"] = [p.strip() for p in line.split(":", 1)[1].split(",")]

                path = f"{mod_name}.{name}"
                result[path] = entry

    except (ModuleNotFoundError, AttributeError):
        pass

    return result


# ── HookRunner — config-first dispatch ─────────────────────

class HookRunner:
    """Dispatches hooks from YAML config, with decorator fallback.

    Resolution order:
    1. Read model_cfg["hooks"][hook_name] → list of {fn, params}
    2. Import each fn by dotted path, call it
    3. If no YAML hooks, check @pipeline_hook decorator registry
    4. If neither, no-op
    """

    def __init__(self, model_cfg: dict, model_name: str = ""):
        self.model_cfg = model_cfg
        self.model_name = model_name

    def run(self, hook_name: str, **context) -> Any:
        """Run all hooks for a lifecycle event.

        Args:
            hook_name: Hook point (pre_build, before_build, after_build, post_build)
            **context: Passed to each hook fn (engine, model, dims, facts, etc.)

        Returns:
            Result from last hook, or None
        """
        result = None

        # 1. YAML config hooks (primary — config is king)
        hooks_cfg = self.model_cfg.get("hooks", {})
        hook_defs = hooks_cfg.get(hook_name, [])

        if hook_defs:
            for hook_def in hook_defs:
                fn_path = hook_def.get("fn", "") if isinstance(hook_def, dict) else getattr(hook_def, 'fn', '')
                params = hook_def.get("params", {}) if isinstance(hook_def, dict) else getattr(hook_def, 'params', {})

                if not fn_path:
                    continue

                try:
                    from de_funk.core.error_handling import ErrorContext
                    with ErrorContext(f"Hook {hook_name}", fn=fn_path, model=self.model_name):
                        fn = _import_fn(fn_path)
                        result = fn(config=self.model_cfg, **context, **params)
                except Exception as e:
                    logger.error(f"Hook {hook_name}/{fn_path} failed: {e}", exc_info=True)
            return result

        # 2. Decorator registry (fallback — Python escape hatch)
        decorator_hooks = _get_decorator_hooks(hook_name, self.model_name)
        if decorator_hooks:
            for fn in decorator_hooks:
                try:
                    result = fn(config=self.model_cfg, **context)
                    logger.info(f"Hook {hook_name}: @pipeline_hook {fn.__name__}")
                except Exception as e:
                    logger.warning(f"Hook {hook_name}/{fn.__name__} failed: {e}")
            return result

        # 3. No hooks — no-op
        return None

    def has_hooks(self, hook_name: str) -> bool:
        """Check if any hooks exist for a lifecycle event."""
        hooks_cfg = self.model_cfg.get("hooks", {})
        if hooks_cfg.get(hook_name):
            return True
        return bool(_get_decorator_hooks(hook_name, self.model_name))

    def list_hooks(self) -> dict:
        """List all available hooks for this model."""
        result = {}
        hooks_cfg = self.model_cfg.get("hooks", {})
        for hook_name, defs in hooks_cfg.items():
            result[hook_name] = [d.get("fn", "") if isinstance(d, dict) else "" for d in defs]

        # Add decorator hooks
        for hook_type, models in _decorator_registry.items():
            fns = models.get(self.model_name, []) + models.get("*", [])
            if fns:
                existing = result.get(hook_type, [])
                result[hook_type] = existing + [f"@{fn.__name__}" for fn in fns]

        return result


# ── Helpers ────────────────────────────────────────────────

def _import_fn(dotted_path: str) -> Callable:
    """Import a function by dotted path."""
    module_path, fn_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, fn_name)


def _get_decorator_hooks(hook_type: str, model_name: str) -> List[Callable]:
    """Get hooks from the decorator registry for a hook type + model."""
    hooks = _decorator_registry.get(hook_type, {})
    return hooks.get(model_name, []) + hooks.get("*", [])



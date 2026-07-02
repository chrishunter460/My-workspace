"""Backward compat — imports from core.hooks."""
from de_funk.core.hooks import (
    pipeline_hook,
    discover_hooks as discover_plugins,
    HookRunner,
    _decorator_registry,
    _get_decorator_hooks,
)

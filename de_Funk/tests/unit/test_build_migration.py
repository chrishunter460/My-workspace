"""Tests for Build Path — session-first model building."""
import pytest
from unittest.mock import MagicMock, patch


class TestBaseModelRunHooks:
    def test_run_hooks_noop(self):
        """No hooks configured, no crash."""
        from de_funk.models.base.model import BaseModel
        model = MagicMock(spec=BaseModel)
        model.model_cfg = {"hooks": {}}
        model.model_name = "test"
        model.engine = MagicMock()
        BaseModel._run_hooks(model, "before_build")

    def test_run_hooks_yaml_config(self):
        """YAML hooks are called when configured."""
        from de_funk.models.base.model import BaseModel
        model = MagicMock(spec=BaseModel)
        model.model_cfg = {
            "hooks": {
                "after_build": [
                    {"fn": "tests.unit.test_build_migration._test_hook", "params": {"x": 1}}
                ]
            }
        }
        model.model_name = "test"
        model.engine = MagicMock()
        BaseModel._run_hooks(model, "after_build")

    def test_run_hooks_decorator_registry(self):
        """Decorator-registered hooks are discovered by HookRunner."""
        from de_funk.core.hooks import _decorator_registry

        called = []
        def my_hook(engine=None, config=None, **kwargs):
            called.append("plugin_called")

        _decorator_registry.setdefault("test_hook", {}).setdefault("test_model", []).append(my_hook)

        from de_funk.models.base.model import BaseModel
        model = MagicMock(spec=BaseModel)
        model.model_cfg = {"hooks": {}}
        model.model_name = "test_model"
        model.engine = MagicMock()
        BaseModel._run_hooks(model, "test_hook")
        assert "plugin_called" in called

        _decorator_registry["test_hook"]["test_model"].remove(my_hook)


class TestBaseModelSession:
    def test_model_takes_session(self):
        """BaseModel.__init__ takes session as first arg."""
        import inspect
        from de_funk.models.base.model import BaseModel
        sig = inspect.signature(BaseModel.__init__)
        params = list(sig.parameters.keys())
        assert params[1] == "session"  # self, session, model_cfg, params

    def test_builder_takes_session(self):
        """BaseModelBuilder.__init__ takes session."""
        import inspect
        from de_funk.models.base.builder import BaseModelBuilder
        sig = inspect.signature(BaseModelBuilder.__init__)
        params = list(sig.parameters.keys())
        assert params[1] == "session"

    def test_no_build_context(self):
        """BuildContext has been removed."""
        import de_funk.models.base.builder as builder_mod
        assert not hasattr(builder_mod, 'BuildContext')

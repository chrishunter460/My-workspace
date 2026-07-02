"""Tests for API Wiring — Phase 10."""
import pytest


class TestApiCreation:
    def test_create_app_returns_fastapi(self):
        from de_funk.api.main import create_app
        app = create_app()
        assert app is not None
        assert app.title == "de_funk API"
        assert app.version == "2.0.0"

    def test_app_has_routers(self):
        from de_funk.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        # Check key routes are mounted
        assert any("/api/health" in str(p) for p in paths)

    def test_startup_uses_defunk(self):
        """Verify startup handler imports and uses DeFunk."""
        import inspect
        from de_funk.api.main import create_app
        app = create_app()
        # Find startup event handler
        startup_handlers = [h for h in app.router.on_startup]
        assert len(startup_handlers) >= 1
        # Check it references DeFunk
        source = inspect.getsource(startup_handlers[0])
        assert "DeFunk" in source

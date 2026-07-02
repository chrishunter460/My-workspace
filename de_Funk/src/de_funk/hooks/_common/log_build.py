"""
Generic build logging hook — usable by any domain.

Logs build start/end with timing. Attach via YAML:
    hooks:
      before_build:
        - {fn: de_funk.hooks._common.log_build.log_start}
      post_build:
        - {fn: de_funk.hooks._common.log_build.log_complete}

Trigger: before_build, post_build
Domain: any (generic)
Params: none
"""
import time
from de_funk.config.logging import get_logger

logger = get_logger(__name__)

_build_times = {}


def log_start(engine=None, config=None, model=None, **params):
    """Log build start with model name and timestamp.

    Trigger: before_build
    Domain: any
    """
    model_name = config.get("model", "unknown") if config else "unknown"
    _build_times[model_name] = time.time()
    logger.info(f"Build started: {model_name}")


def log_complete(engine=None, config=None, model=None, **params):
    """Log build completion with duration.

    Trigger: post_build
    Domain: any
    """
    model_name = config.get("model", "unknown") if config else "unknown"
    start = _build_times.pop(model_name, None)
    if start:
        elapsed = time.time() - start
        logger.info(f"Build complete: {model_name} ({elapsed:.1f}s)")
    else:
        logger.info(f"Build complete: {model_name}")

"""
Run the de_funk FastAPI backend.

Usage:
    python -m scripts.serve.run_api
    python -m scripts.serve.run_api --port 8765 --host 0.0.0.0
    python -m scripts.serve.run_api --reload          # dev mode with auto-reload

The server binds to 0.0.0.0 by default so it is reachable from other LAN devices.
Find your LAN IP with: ip addr show | grep "inet " | grep -v 127.0.0.1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src/ to path for package imports
_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root / "src"))

from de_funk.config.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev mode)")
    parser.add_argument("--workers", type=int, default=1, help="Number of uvicorn workers")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn not installed. Run: pip install de_funk[api]")
        sys.exit(1)

    logger.info(f"Starting de_funk API on {args.host}:{args.port}")
    logger.info(f"API docs: http://localhost:{args.port}/api/docs")

    uvicorn.run(
        "de_funk.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level="info",
    )


if __name__ == "__main__":
    main()

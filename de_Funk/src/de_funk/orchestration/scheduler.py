"""
Scheduled Jobs using APScheduler.

Provides scheduled execution of pipeline jobs including:
- Daily market cap refresh (6:00 AM)
- Daily price ingestion (4:30 PM - after market close)
- Weekly full forecast run (Sunday 2:00 AM)
- Daily silver layer rebuild (5:00 AM)

Usage:
    # Run scheduler daemon
    python -m orchestration.scheduler

    # Or import and configure programmatically
    from de_funk.orchestration.scheduler import PipelineScheduler
    scheduler = PipelineScheduler()
    scheduler.start()

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from pathlib import Path

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def _get_apscheduler():
    """Lazy import APScheduler."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
        return BlockingScheduler, BackgroundScheduler, CronTrigger, IntervalTrigger
    except ImportError:
        raise ImportError(
            "APScheduler is not installed. Install with: pip install apscheduler"
        )


class PipelineScheduler:
    """
    Scheduler for de_Funk pipeline jobs.

    Manages scheduled execution of:
    - Data ingestion (daily)
    - Market cap refresh (daily)
    - Forecasting (weekly)
    - Silver layer rebuilds (daily)

    Uses APScheduler with cron-style triggers.
    """

    def __init__(self, blocking: bool = True):
        """
        Initialize scheduler.

        Args:
            blocking: Use blocking scheduler (True for daemon mode)
        """
        BlockingScheduler, BackgroundScheduler, _, _ = _get_apscheduler()

        if blocking:
            self.scheduler = BlockingScheduler()
        else:
            self.scheduler = BackgroundScheduler()

        self._jobs_registered = False

    def add_job(
        self,
        func: Callable,
        trigger: str,
        job_id: str,
        name: str = None,
        **trigger_kwargs
    ):
        """
        Add a job to the scheduler.

        Args:
            func: Function to execute
            trigger: Trigger type ('cron', 'interval')
            job_id: Unique job identifier
            name: Human-readable job name
            **trigger_kwargs: Arguments for trigger (hour, minute, day_of_week, etc.)
        """
        _, _, CronTrigger, IntervalTrigger = _get_apscheduler()

        if trigger == 'cron':
            trigger_obj = CronTrigger(**trigger_kwargs)
        elif trigger == 'interval':
            trigger_obj = IntervalTrigger(**trigger_kwargs)
        else:
            raise ValueError(f"Unknown trigger type: {trigger}")

        self.scheduler.add_job(
            func,
            trigger=trigger_obj,
            id=job_id,
            name=name or job_id,
            replace_existing=True
        )
        logger.info(f"Scheduled job: {name or job_id}")

    def register_default_jobs(self):
        """Register the default pipeline jobs."""
        if self._jobs_registered:
            return

        # Daily market cap refresh at 6:00 AM
        self.add_job(
            job_daily_market_cap_refresh,
            trigger='cron',
            job_id='daily_market_cap_refresh',
            name='Daily Market Cap Refresh',
            hour=6, minute=0
        )

        # Daily price ingestion at 4:30 PM (after market close)
        self.add_job(
            job_daily_price_ingestion,
            trigger='cron',
            job_id='daily_price_ingestion',
            name='Daily Price Ingestion',
            hour=16, minute=30
        )

        # Daily silver layer rebuild at 5:00 AM
        self.add_job(
            job_daily_silver_rebuild,
            trigger='cron',
            job_id='daily_silver_rebuild',
            name='Daily Silver Rebuild',
            hour=5, minute=0
        )

        # Weekly full forecast at 2:00 AM Sunday
        self.add_job(
            job_weekly_forecasts,
            trigger='cron',
            job_id='weekly_forecasts',
            name='Weekly Forecasts',
            day_of_week='sun', hour=2, minute=0
        )

        self._jobs_registered = True

    def start(self, register_defaults: bool = True):
        """
        Start the scheduler.

        Args:
            register_defaults: Register default jobs before starting
        """
        if register_defaults:
            self.register_default_jobs()

        print("=" * 60)
        print("de_Funk Pipeline Scheduler")
        print("=" * 60)
        print(f"\nStarted at: {datetime.now().isoformat()}")
        print("\nScheduled jobs:")

        for job in self.scheduler.get_jobs():
            print(f"  - {job.name}: {job.trigger}")

        print("\nPress Ctrl+C to stop")
        print("=" * 60)
        print()

        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            print("\nShutdown requested...")
            self.scheduler.shutdown()
            print("Scheduler stopped")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()

    def run_job_now(self, job_id: str):
        """
        Manually trigger a job immediately.

        Args:
            job_id: ID of job to run
        """
        job = self.scheduler.get_job(job_id)
        if job:
            logger.info(f"Manually triggering job: {job_id}")
            job.func()
        else:
            logger.warning(f"Job not found: {job_id}")


# ============================================================================
# SCHEDULED JOB FUNCTIONS
# ============================================================================

def job_daily_market_cap_refresh():
    """
    Daily market cap refresh job.

    Runs at 6:00 AM to update market cap rankings before market open.
    """
    logger.info(f"[{datetime.now()}] Starting daily market cap refresh...")

    try:
        from de_funk.utils.repo import setup_repo_imports
        repo_root = setup_repo_imports()

from de_funk.core.context import RepoContext
        from de_funk.pipelines.providers.alpha_vantage.alpha_vantage_ingestor import AlphaVantageIngestor

        ctx = RepoContext.from_repo_root(connection_type="spark")

        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )

        # Refresh market cap rankings
        ingestor.refresh_market_cap_rankings(max_tickers=1000)

        logger.info(f"[{datetime.now()}] Market cap refresh complete")

    except Exception as e:
        logger.error(f"Market cap refresh failed: {e}", exc_info=True)


def job_daily_price_ingestion():
    """
    Daily price ingestion job.

    Runs at 4:30 PM (after market close) to ingest latest prices.
    """
    logger.info(f"[{datetime.now()}] Starting daily price ingestion...")

    try:
        from de_funk.utils.repo import setup_repo_imports
        repo_root = setup_repo_imports()

from de_funk.core.context import RepoContext
        from de_funk.pipelines.base.ingestor_engine import create_engine
        from de_funk.pipelines.base.provider import DataType

        ctx = RepoContext.from_repo_root(connection_type="spark")

        engine = create_engine(
            provider_name="alpha_vantage",
            api_cfg=ctx.get_api_config('alpha_vantage'),
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )

        # Run ingestion for top 500 tickers by market cap
        results = engine.run_with_discovery(
            max_tickers=500,
            use_market_cap=True,
            data_types=[DataType.PRICES],
            batch_size=20
        )

        logger.info(
            f"[{datetime.now()}] Price ingestion complete: "
            f"{results.completed_tickers} tickers"
        )

    except Exception as e:
        logger.error(f"Price ingestion failed: {e}", exc_info=True)


def job_daily_silver_rebuild():
    """
    Daily silver layer rebuild job.

    Runs at 5:00 AM to rebuild silver layer models.
    """
    logger.info(f"[{datetime.now()}] Starting silver layer rebuild...")

    try:
        from de_funk.utils.repo import setup_repo_imports
        repo_root = setup_repo_imports()

from de_funk.core.context import RepoContext
        from scripts.orchestrate import build_model, load_storage_config

        ctx = RepoContext.from_repo_root(connection_type="spark")
        storage_cfg = load_storage_config()

        # Build models in dependency order
        models = ['temporal', 'corporate.entity', 'securities.stocks', 'macro']

        for model_name in models:
            try:
                result = build_model(
                    model_name=model_name,
                    spark_session=ctx.spark,
                    storage_cfg=storage_cfg,
                    repo_root_path=Path(repo_root)
                )
                logger.info(f"  Built {model_name}: {result.get('status')}")
            except Exception as e:
                logger.warning(f"  Failed to build {model_name}: {e}")

        logger.info(f"[{datetime.now()}] Silver rebuild complete")

    except Exception as e:
        logger.error(f"Silver rebuild failed: {e}", exc_info=True)


def job_weekly_forecasts():
    """
    Weekly forecast job.

    Runs at 2:00 AM Sunday for full forecast run.
    Uses Spark for distributed processing.
    """
    logger.info(f"[{datetime.now()}] Starting weekly forecast run...")

    try:
        from de_funk.utils.repo import setup_repo_imports
        repo_root = setup_repo_imports()

        from de_funk.core.context import RepoContext

        ctx = RepoContext.from_repo_root(connection_type="spark")

        from de_funk.models.domains.securities.forecast.builder import ForecastBuilder
        # BuildContext removed — use BuildSession

        # Use DeFunk.build_session() instead
            repo_root=Path(repo_root),
            storage_config=ctx.storage,
            spark=ctx.spark,
            max_tickers=500,
        )

        builder = ForecastBuilder(build_ctx)
        result = builder.build()

        if result.success:
            logger.info(f"Forecasts complete: {result.rows_written} forecasts generated")
        else:
            logger.error(f"Forecast build failed: {result.error}")

        logger.info(f"[{datetime.now()}] Weekly forecasts complete")

    except Exception as e:
        logger.error(f"Weekly forecasts failed: {e}", exc_info=True)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    """Main entry point for scheduler daemon."""
    setup_logging()

    import argparse
    parser = argparse.ArgumentParser(description="de_Funk Pipeline Scheduler")
    parser.add_argument(
        '--run-job',
        help='Run a specific job immediately instead of starting scheduler'
    )
    parser.add_argument(
        '--list-jobs',
        action='store_true',
        help='List available jobs and exit'
    )

    args = parser.parse_args()

    scheduler = PipelineScheduler(blocking=True)
    scheduler.register_default_jobs()

    if args.list_jobs:
        print("\nAvailable jobs:")
        for job in scheduler.scheduler.get_jobs():
            print(f"  {job.id}: {job.name}")
        return

    if args.run_job:
        scheduler.run_job_now(args.run_job)
        return

    scheduler.start()


if __name__ == "__main__":
    main()

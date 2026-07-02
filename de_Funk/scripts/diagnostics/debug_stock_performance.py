#!/usr/bin/env python
"""
Stock Price Performance Debugger.

Comprehensive diagnostics for stock price query performance issues.

This script checks:
1. Required packages installed
2. Bronze/Silver data layer state
3. DuckDB connection and query performance
4. Filter application overhead
5. Data size and partitioning
6. Common bottlenecks

Usage:
    python -m scripts.diagnostics.debug_stock_performance
    python -m scripts.diagnostics.debug_stock_performance --verbose
    python -m scripts.diagnostics.debug_stock_performance --profile-query
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Setup repo imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def print_header(text: str, char: str = "=") -> None:
    """Print a formatted header line."""
    line = char * 80
    print(f"\n{line}")
    print(f"  {text}")
    print(line)


def print_section(text: str) -> None:
    """Print a section header."""
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def check_mark(condition: bool) -> str:
    """Return check mark or X based on condition."""
    return "✅" if condition else "❌"


def warn_mark() -> str:
    """Return warning mark."""
    return "⚠️"


class PackageChecker:
    """Check for required packages."""

    REQUIRED_PACKAGES = {
        'duckdb': 'Fast analytics engine (required for UI queries)',
        'pandas': 'Data manipulation',
        'pyarrow': 'Parquet file support',
    }

    OPTIONAL_PACKAGES = {
        'pyspark': 'ETL and batch processing (optional)',
        'delta': 'Delta Lake support (optional)',
    }

    @classmethod
    def check_all(cls) -> Dict[str, Tuple[bool, str]]:
        """Check all packages and return status."""
        results = {}

        for pkg, desc in cls.REQUIRED_PACKAGES.items():
            try:
                __import__(pkg)
                results[pkg] = (True, desc)
            except ImportError:
                results[pkg] = (False, desc)

        for pkg, desc in cls.OPTIONAL_PACKAGES.items():
            try:
                __import__(pkg)
                results[pkg] = (True, desc)
            except ImportError:
                results[pkg] = (None, desc)  # None = optional missing

        return results

    @classmethod
    def print_report(cls) -> bool:
        """Print package status report. Returns True if all required packages present."""
        print_section("Package Status")

        results = cls.check_all()
        all_required_present = True

        print("\n  Required packages:")
        for pkg, (status, desc) in results.items():
            if pkg in cls.REQUIRED_PACKAGES:
                mark = check_mark(status) if status else "❌"
                if not status:
                    all_required_present = False
                print(f"    {mark} {pkg}: {desc}")

        print("\n  Optional packages:")
        for pkg, (status, desc) in results.items():
            if pkg in cls.OPTIONAL_PACKAGES:
                if status is True:
                    mark = "✅"
                elif status is None:
                    mark = "⚪"  # Optional missing
                else:
                    mark = "⚪"
                print(f"    {mark} {pkg}: {desc}")

        if not all_required_present:
            print(f"\n  {warn_mark()} Missing required packages!")
            print("  Install with: pip install -r requirements.txt")

        return all_required_present


class DataLayerChecker:
    """Check bronze and silver data layers."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.bronze_root = repo_root / "storage" / "bronze"
        self.silver_root = repo_root / "storage" / "silver"

    def check_bronze(self) -> Dict[str, Any]:
        """Check bronze layer status."""
        results = {
            'exists': self.bronze_root.exists(),
            'tables': {},
            'total_files': 0,
            'total_size_mb': 0,
        }

        if not results['exists']:
            return results

        # Find all tables
        for table_dir in self.bronze_root.iterdir():
            if table_dir.is_dir() and not table_dir.name.startswith('.'):
                parquet_files = list(table_dir.rglob('*.parquet'))
                delta_log = (table_dir / '_delta_log').exists()

                total_size = sum(f.stat().st_size for f in parquet_files if f.exists())

                results['tables'][table_dir.name] = {
                    'files': len(parquet_files),
                    'size_mb': total_size / (1024 * 1024),
                    'is_delta': delta_log,
                    'path': str(table_dir),
                }
                results['total_files'] += len(parquet_files)
                results['total_size_mb'] += total_size / (1024 * 1024)

        return results

    def check_silver(self) -> Dict[str, Any]:
        """Check silver layer status."""
        results = {
            'exists': self.silver_root.exists(),
            'models': {},
            'total_files': 0,
            'total_size_mb': 0,
        }

        if not results['exists']:
            return results

        # Find all models
        for model_dir in self.silver_root.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                parquet_files = list(model_dir.rglob('*.parquet'))

                total_size = sum(f.stat().st_size for f in parquet_files if f.exists())

                # Find tables within model
                tables = {}
                for subdir in ['dims', 'facts']:
                    table_dir = model_dir / subdir
                    if table_dir.exists():
                        for table in table_dir.iterdir():
                            if table.is_dir():
                                tfiles = list(table.rglob('*.parquet'))
                                tsize = sum(f.stat().st_size for f in tfiles if f.exists())
                                tables[f"{subdir}/{table.name}"] = {
                                    'files': len(tfiles),
                                    'size_mb': tsize / (1024 * 1024),
                                }

                results['models'][model_dir.name] = {
                    'tables': tables,
                    'total_files': len(parquet_files),
                    'size_mb': total_size / (1024 * 1024),
                }
                results['total_files'] += len(parquet_files)
                results['total_size_mb'] += total_size / (1024 * 1024)

        return results

    def print_report(self) -> Tuple[bool, bool]:
        """Print data layer report. Returns (bronze_ok, silver_ok)."""
        print_section("Data Layer Status")

        # Bronze
        bronze = self.check_bronze()
        print(f"\n  Bronze Layer: {self.bronze_root}")
        print(f"    {check_mark(bronze['exists'])} Directory exists")

        if bronze['exists'] and bronze['tables']:
            print(f"    Tables: {len(bronze['tables'])}")
            print(f"    Total files: {bronze['total_files']}")
            print(f"    Total size: {bronze['total_size_mb']:.2f} MB")

            print("\n    Table details:")
            for name, info in bronze['tables'].items():
                delta_mark = "Δ" if info['is_delta'] else "P"
                print(f"      [{delta_mark}] {name}: {info['files']} files, {info['size_mb']:.2f} MB")

            # Check for required tables
            required_bronze = ['securities_reference', 'securities_prices_daily']
            missing = [t for t in required_bronze if t not in bronze['tables']]
            if missing:
                print(f"\n    {warn_mark()} Missing required bronze tables: {missing}")
                print("      Run: python -m scripts.ingest.run_full_pipeline --max-tickers 100")
        else:
            print(f"    {warn_mark()} No bronze tables found!")
            print("      Run: python -m scripts.ingest.run_full_pipeline --max-tickers 100")

        # Silver
        silver = self.check_silver()
        print(f"\n  Silver Layer: {self.silver_root}")
        print(f"    {check_mark(silver['exists'])} Directory exists")

        if silver['exists'] and silver['models']:
            print(f"    Models: {len(silver['models'])}")
            print(f"    Total files: {silver['total_files']}")
            print(f"    Total size: {silver['total_size_mb']:.2f} MB")

            print("\n    Model details:")
            for name, info in silver['models'].items():
                print(f"      {name}: {info['total_files']} files, {info['size_mb']:.2f} MB")
                for table, tinfo in info['tables'].items():
                    print(f"        └─ {table}: {tinfo['files']} files, {tinfo['size_mb']:.2f} MB")

            # Check for stocks model
            if 'stocks' not in silver['models']:
                print(f"\n    {warn_mark()} Stocks model not found!")
                print("      Run: python -m scripts.build.build_all_models")
        else:
            print(f"    {warn_mark()} No silver models found!")
            print("      Run: python -m scripts.build.build_all_models")

        bronze_ok = bronze['exists'] and bool(bronze['tables'])
        silver_ok = silver['exists'] and bool(silver['models'])

        return bronze_ok, silver_ok


class QueryProfiler:
    """Profile DuckDB query performance."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.conn = None

    def connect(self) -> bool:
        """Try to connect to DuckDB."""
        try:
            import duckdb
            db_path = self.repo_root / "storage" / "duckdb" / "analytics.db"

            # Create directory if needed
            db_path.parent.mkdir(parents=True, exist_ok=True)

            self.conn = duckdb.connect(str(db_path))
            return True
        except ImportError:
            print(f"  {warn_mark()} DuckDB not installed")
            return False
        except Exception as e:
            print(f"  {warn_mark()} Failed to connect: {e}")
            return False

    def profile_parquet_read(self, path: Path, label: str) -> Optional[Dict[str, Any]]:
        """Profile reading a parquet table."""
        if not self.conn:
            return None

        if not path.exists():
            return {'error': 'Path does not exist'}

        pattern = str(path) + "/**/*.parquet"

        try:
            # Time metadata read
            start = time.perf_counter()
            df = self.conn.execute(f"""
                SELECT COUNT(*) as cnt
                FROM read_parquet('{pattern}', hive_partitioning=true, union_by_name=true)
            """).fetchone()
            count_time = time.perf_counter() - start
            row_count = df[0] if df else 0

            # Time full scan (limit 1000)
            start = time.perf_counter()
            self.conn.execute(f"""
                SELECT *
                FROM read_parquet('{pattern}', hive_partitioning=true, union_by_name=true)
                LIMIT 1000
            """).fetchdf()
            scan_time = time.perf_counter() - start

            # Get columns
            start = time.perf_counter()
            schema_df = self.conn.execute(f"""
                SELECT *
                FROM read_parquet('{pattern}', hive_partitioning=true, union_by_name=true)
                LIMIT 0
            """)
            columns = schema_df.columns
            schema_time = time.perf_counter() - start

            return {
                'label': label,
                'row_count': row_count,
                'column_count': len(columns),
                'count_time_ms': count_time * 1000,
                'scan_1k_time_ms': scan_time * 1000,
                'schema_time_ms': schema_time * 1000,
            }
        except Exception as e:
            return {'error': str(e), 'label': label}

    def profile_filtered_query(
        self,
        path: Path,
        filters: Dict[str, Any],
        label: str
    ) -> Optional[Dict[str, Any]]:
        """Profile a filtered query."""
        if not self.conn:
            return None

        if not path.exists():
            return {'error': 'Path does not exist', 'label': label}

        pattern = str(path) + "/**/*.parquet"

        # Build WHERE clause
        conditions = []
        for col, val in filters.items():
            if isinstance(val, dict):
                if 'start' in val:
                    conditions.append(f"{col} >= '{val['start']}'")
                if 'end' in val:
                    conditions.append(f"{col} <= '{val['end']}'")
            elif isinstance(val, list):
                vals = "', '".join(str(v) for v in val)
                conditions.append(f"{col} IN ('{vals}')")
            else:
                conditions.append(f"{col} = '{val}'")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        try:
            # Time filtered count
            start = time.perf_counter()
            result = self.conn.execute(f"""
                SELECT COUNT(*) as cnt
                FROM read_parquet('{pattern}', hive_partitioning=true, union_by_name=true)
                WHERE {where_clause}
            """).fetchone()
            filter_count_time = time.perf_counter() - start
            filtered_count = result[0] if result else 0

            # Time filtered scan
            start = time.perf_counter()
            self.conn.execute(f"""
                SELECT *
                FROM read_parquet('{pattern}', hive_partitioning=true, union_by_name=true)
                WHERE {where_clause}
                LIMIT 1000
            """).fetchdf()
            filter_scan_time = time.perf_counter() - start

            return {
                'label': label,
                'filters': filters,
                'filtered_count': filtered_count,
                'filter_count_time_ms': filter_count_time * 1000,
                'filter_scan_time_ms': filter_scan_time * 1000,
            }
        except Exception as e:
            return {'error': str(e), 'label': label}

    def print_report(self) -> None:
        """Print query performance report."""
        print_section("Query Performance Profile")

        if not self.connect():
            return

        print(f"\n  {check_mark(True)} DuckDB connected")

        # Profile bronze tables
        bronze_path = self.repo_root / "storage" / "bronze"
        silver_path = self.repo_root / "storage" / "silver"

        # Check for securities_prices_daily
        prices_bronze = bronze_path / "securities_prices_daily"
        if prices_bronze.exists():
            result = self.profile_parquet_read(prices_bronze, "bronze.securities_prices_daily")
            if result and 'error' not in result:
                print(f"\n  Bronze prices table:")
                print(f"    Rows: {result['row_count']:,}")
                print(f"    Columns: {result['column_count']}")
                print(f"    Count query: {result['count_time_ms']:.1f}ms")
                print(f"    Scan 1k rows: {result['scan_1k_time_ms']:.1f}ms")

                # Profile with filters
                filter_result = self.profile_filtered_query(
                    prices_bronze,
                    {'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}},
                    "bronze prices filtered"
                )
                if filter_result and 'error' not in filter_result:
                    print(f"\n  Filtered query (2024 dates):")
                    print(f"    Filtered rows: {filter_result['filtered_count']:,}")
                    print(f"    Filter count: {filter_result['filter_count_time_ms']:.1f}ms")
                    print(f"    Filter scan: {filter_result['filter_scan_time_ms']:.1f}ms")
        else:
            print(f"\n  {warn_mark()} Bronze prices table not found at {prices_bronze}")

        # Check for silver stocks
        stocks_prices = silver_path / "stocks" / "facts" / "fact_stock_prices"
        if stocks_prices.exists():
            result = self.profile_parquet_read(stocks_prices, "silver.stocks.fact_stock_prices")
            if result and 'error' not in result:
                print(f"\n  Silver stock prices table:")
                print(f"    Rows: {result['row_count']:,}")
                print(f"    Columns: {result['column_count']}")
                print(f"    Count query: {result['count_time_ms']:.1f}ms")
                print(f"    Scan 1k rows: {result['scan_1k_time_ms']:.1f}ms")
        else:
            print(f"\n  {warn_mark()} Silver stock prices not found at {stocks_prices}")

        # Performance recommendations
        print_section("Performance Recommendations")

        recommendations = []

        # Check if data exists
        if not prices_bronze.exists() and not stocks_prices.exists():
            recommendations.append(
                "1. CRITICAL: No stock price data found!\n"
                "   Run: python -m scripts.ingest.run_full_pipeline --max-tickers 100\n"
                "   Then: python -m scripts.build.build_all_models"
            )

        # Check silver layer
        if not stocks_prices.exists() and prices_bronze.exists():
            recommendations.append(
                "2. Bronze data exists but Silver is not built.\n"
                "   Run: python -m scripts.build.build_all_models"
            )

        if recommendations:
            for rec in recommendations:
                print(f"\n  {rec}")
        else:
            print("\n  ✅ Data layers appear healthy")
            print("\n  General performance tips:")
            print("    1. Use date filters to limit data scanned")
            print("    2. Filter by ticker to reduce result set")
            print("    3. Use DuckDB (not Spark) for UI queries")
            print("    4. Cache frequently accessed tables")

        if self.conn:
            self.conn.close()


class BottleneckAnalyzer:
    """Analyze common performance bottlenecks."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def check_partitioning(self) -> List[str]:
        """Check if data is properly partitioned."""
        issues = []

        bronze_prices = self.repo_root / "storage" / "bronze" / "securities_prices_daily"
        if bronze_prices.exists():
            # Check for partition directories
            partition_dirs = [d for d in bronze_prices.iterdir() if d.is_dir() and '=' in d.name]
            if not partition_dirs:
                issues.append("Bronze prices not partitioned - full table scans required")
            else:
                # Check partition scheme
                sample_partition = partition_dirs[0].name
                if 'asset_type=' in sample_partition:
                    pass  # Good partitioning
                elif 'trade_date=' in sample_partition:
                    issues.append("Partitioned by trade_date only - consider asset_type partitioning")

        return issues

    def check_file_count(self) -> Tuple[List[str], Dict[str, Any]]:
        """Check for too many small files (small file problem)."""
        issues = []
        stats = {}

        for layer in ['bronze', 'silver']:
            layer_path = self.repo_root / "storage" / layer
            if not layer_path.exists():
                continue

            parquet_files = list(layer_path.rglob('*.parquet'))
            total_size = sum(f.stat().st_size for f in parquet_files if f.exists())
            avg_size = total_size / len(parquet_files) / (1024 * 1024) if parquet_files else 0

            stats[layer] = {
                'file_count': len(parquet_files),
                'total_size_mb': total_size / (1024 * 1024),
                'avg_size_mb': avg_size,
            }

            if len(parquet_files) > 1000:
                issues.append(f"{layer.title()}: {len(parquet_files)} parquet files - consider compaction")

            # Check average file size
            if parquet_files and avg_size < 1:  # Less than 1MB average
                issues.append(f"{layer.title()}: Average file size {avg_size:.2f}MB - too small, consider compaction")

        return issues, stats

    def print_report(self) -> Dict[str, Any]:
        """Print bottleneck analysis. Returns stats for use in recommendations."""
        print_section("Bottleneck Analysis")

        all_issues = []

        partition_issues = self.check_partitioning()
        all_issues.extend(partition_issues)

        file_issues, file_stats = self.check_file_count()
        all_issues.extend(file_issues)

        if all_issues:
            print("\n  Potential issues found:")
            for i, issue in enumerate(all_issues, 1):
                print(f"    {i}. {issue}")

            # Add specific compaction recommendation
            if any('compaction' in issue for issue in all_issues):
                print("\n  🔧 RECOMMENDED FIX: Run Delta OPTIMIZE")
                print("    This will compact small files into larger ones for better performance.")
                print()
                print("    Commands:")
                print("      # Dry run (see what would be done):")
                print("      python -m scripts.maintenance.delta_maintenance --all --dry-run")
                print()
                print("      # Run compaction (optimize all bronze tables):")
                print("      python -m scripts.maintenance.delta_maintenance --optimize")
                print()
                print("      # Full maintenance (optimize + vacuum old files):")
                print("      python -m scripts.maintenance.delta_maintenance --all")
        else:
            print("\n  ✅ No obvious bottlenecks detected")

        return file_stats


def main():
    parser = argparse.ArgumentParser(
        description="Debug stock price performance issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.diagnostics.debug_stock_performance
    python -m scripts.diagnostics.debug_stock_performance --verbose
    python -m scripts.diagnostics.debug_stock_performance --profile-query
        """
    )
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--profile-query', action='store_true', help='Profile query performance (requires duckdb)')
    args = parser.parse_args()

    print_header("STOCK PRICE PERFORMANCE DEBUGGER")
    print(f"  Repository: {repo_root}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Check packages
    packages_ok = PackageChecker.print_report()

    # 2. Check data layers
    data_checker = DataLayerChecker(repo_root)
    bronze_ok, silver_ok = data_checker.print_report()

    # 3. Profile queries (if packages available and requested)
    if packages_ok or args.profile_query:
        profiler = QueryProfiler(repo_root)
        profiler.print_report()

    # 4. Analyze bottlenecks
    analyzer = BottleneckAnalyzer(repo_root)
    file_stats = analyzer.print_report()

    # Summary
    print_header("SUMMARY")

    issues = []
    if not packages_ok:
        issues.append("Missing required packages - install with: pip install -r requirements.txt")
    if not bronze_ok:
        issues.append("Bronze layer empty - run ingestion pipeline")
    if not silver_ok:
        issues.append("Silver layer empty - run model build")

    # Check for small file problem
    has_small_file_problem = False
    if file_stats:
        bronze_stats = file_stats.get('bronze', {})
        if bronze_stats.get('file_count', 0) > 1000 or bronze_stats.get('avg_size_mb', 999) < 1:
            has_small_file_problem = True
            issues.append("Small file problem in Bronze - run Delta OPTIMIZE")

    if issues:
        print("\n  Issues to resolve:")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")

        print("\n  Quick fix commands:")
        if not packages_ok:
            print("    pip install -r requirements.txt")
        if not bronze_ok:
            print("    python -m scripts.ingest.run_full_pipeline --max-tickers 100")
        if not silver_ok:
            print("    python -m scripts.build.build_all_models")
        if has_small_file_problem:
            print("    python -m scripts.maintenance.delta_maintenance --optimize")
    else:
        print("\n  ✅ All checks passed!")
        print("\n  If queries are still slow, consider:")
        print("    1. Adding date range filters to reduce data scanned")
        print("    2. Limiting ticker selection")
        print("    3. Enabling DuckDB caching in storage service")
        print("    4. Running Delta OPTIMIZE if using Delta Lake")

    print_header("DEBUG COMPLETE")


if __name__ == "__main__":
    main()

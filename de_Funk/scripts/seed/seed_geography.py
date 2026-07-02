#!/usr/bin/env python3
"""
Seed Geography Dimension (States + Counties) from Census Bureau.

Fetches US state and county FIPS codes from the Census Bureau API and writes
a geospatial.dim_geography Delta Lake table to the Silver layer.

Data source:
    Census Bureau Decennial Census 2020 (PL 94-171)
    https://api.census.gov/data/2020/dec/pl
    No API key required.

Usage:
    python -m scripts.seed.seed_geography
    python -m scripts.seed.seed_geography --storage-path /shared/storage
    python -m scripts.seed.seed_geography --dry-run
"""

import argparse
import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)

# Census Bureau API base URL (no key required for decennial data)
CENSUS_API_BASE = "https://api.census.gov/data/2020/dec/pl"

# State abbreviation lookup (FIPS -> abbreviation)
STATE_FIPS_TO_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}


def _make_geography_id(geography_type: str, geography_code: str) -> int:
    """Generate a deterministic geography_id from type and code."""
    key = f"{geography_type}_{geography_code}"
    return abs(hash(key))


def fetch_states() -> list[dict]:
    """
    Fetch state-level geography from Census Bureau API.

    Returns:
        List of state dicts with FIPS code, name, population.
    """
    import urllib.request
    import json

    url = f"{CENSUS_API_BASE}?get=NAME,P1_001N&for=state:*"
    logger.info(f"Fetching states from: {url}")

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "de_Funk/3.0 (geography seed script)")

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # First row is header: ['NAME', 'P1_001N', 'state']
    header = data[0]
    rows = data[1:]

    name_idx = header.index("NAME")
    pop_idx = header.index("P1_001N")
    fips_idx = header.index("state")

    states = []
    for row in rows:
        state_fips = row[fips_idx].zfill(2)
        abbr = STATE_FIPS_TO_ABBR.get(state_fips)
        if abbr is None:
            # Skip territories (PR, GU, VI, AS, MP) - not in our lookup
            logger.debug(f"Skipping non-state FIPS {state_fips}: {row[name_idx]}")
            continue

        population = None
        try:
            population = int(row[pop_idx])
        except (ValueError, TypeError):
            pass

        states.append({
            "geography_type": "STATE",
            "geography_code": state_fips,
            "geography_name": row[name_idx],
            "state_fips": state_fips,
            "state_name": row[name_idx],
            "state_abbr": abbr,
            "county_fips": None,
            "county_name": None,
            "population": population,
        })

    logger.info(f"Fetched {len(states)} states (including DC)")
    return states


def fetch_counties() -> list[dict]:
    """
    Fetch county-level geography from Census Bureau API.

    Returns:
        List of county dicts with FIPS codes, names, population.
    """
    import urllib.request
    import json

    url = f"{CENSUS_API_BASE}?get=NAME,P1_001N&for=county:*&in=state:*"
    logger.info(f"Fetching counties from: {url}")

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "de_Funk/3.0 (geography seed script)")

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    header = data[0]
    rows = data[1:]

    name_idx = header.index("NAME")
    pop_idx = header.index("P1_001N")
    state_idx = header.index("state")
    county_idx = header.index("county")

    counties = []
    for row in rows:
        state_fips = row[state_idx].zfill(2)
        abbr = STATE_FIPS_TO_ABBR.get(state_fips)
        if abbr is None:
            # Skip territories
            continue

        county_fips_3 = row[county_idx].zfill(3)
        county_fips_5 = state_fips + county_fips_3
        county_name = row[name_idx]

        population = None
        try:
            population = int(row[pop_idx])
        except (ValueError, TypeError):
            pass

        # Look up state name from our state data (will be joined later)
        # For now, extract state name from the county NAME field
        # Census returns "County Name, State Name"
        parts = county_name.split(", ")
        state_name_from_census = parts[-1] if len(parts) > 1 else ""
        display_county_name = parts[0] if len(parts) > 1 else county_name

        counties.append({
            "geography_type": "COUNTY",
            "geography_code": county_fips_5,
            "geography_name": county_name,
            "state_fips": state_fips,
            "state_name": state_name_from_census,
            "state_abbr": abbr,
            "county_fips": county_fips_5,
            "county_name": display_county_name,
            "population": population,
        })

    logger.info(f"Fetched {len(counties)} counties")
    return counties


def build_geography_rows(states: list[dict], counties: list[dict]) -> list[dict]:
    """
    Combine states and counties into final dim_geography rows.

    Computes geography_id and parent_geography_id fields.
    """
    # Build state lookup for parent references
    state_id_lookup = {}
    for s in states:
        geo_id = _make_geography_id(s["geography_type"], s["geography_code"])
        state_id_lookup[s["state_fips"]] = geo_id

    rows = []

    # States: no parent
    for s in states:
        geo_id = _make_geography_id(s["geography_type"], s["geography_code"])
        rows.append({
            "geography_id": geo_id,
            "geography_type": s["geography_type"],
            "geography_code": s["geography_code"],
            "geography_name": s["geography_name"],
            "parent_geography_id": None,
            "state_fips": s["state_fips"],
            "state_name": s["state_name"],
            "state_abbr": s["state_abbr"],
            "county_fips": None,
            "county_name": None,
            "region": None,
            "division": None,
            "latitude": None,
            "longitude": None,
            "population": s.get("population"),
            "land_area_sqmi": None,
        })

    # Counties: parent is their state
    for c in counties:
        geo_id = _make_geography_id(c["geography_type"], c["geography_code"])
        parent_id = state_id_lookup.get(c["state_fips"])
        rows.append({
            "geography_id": geo_id,
            "geography_type": c["geography_type"],
            "geography_code": c["geography_code"],
            "geography_name": c["geography_name"],
            "parent_geography_id": parent_id,
            "state_fips": c["state_fips"],
            "state_name": c["state_name"],
            "state_abbr": c["state_abbr"],
            "county_fips": c["county_fips"],
            "county_name": c["county_name"],
            "region": None,
            "division": None,
            "latitude": None,
            "longitude": None,
            "population": c.get("population"),
            "land_area_sqmi": None,
        })

    return rows


def seed_geography(
    storage_path: Path = None,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    """
    Seed geography dimension from Census Bureau data.

    Args:
        storage_path: Storage root (default: /shared/storage or repo_root/storage).
        dry_run: If True, fetch and display data without writing.
        force: Force re-seed even if data exists.

    Returns:
        Number of rows written (or that would be written in dry-run).
    """
    setup_logging()

    # Determine storage path
    if storage_path is None:
        shared = Path("/shared/storage")
        if shared.exists():
            storage_path = shared
        else:
            storage_path = repo_root / "storage"
    storage_path = Path(storage_path)

    output_path = storage_path / "bronze" / "census" / "us_geography"

    # Check if already exists
    if not force and not dry_run and output_path.exists() and (output_path / "_delta_log").exists():
        from de_funk.orchestration.common.spark_session import get_spark

        spark = get_spark("GeographySeedCheck")
        try:
            existing_df = spark.read.format("delta").load(str(output_path))
            existing_count = existing_df.count()
            if existing_count > 50:
                logger.info(f"Geography already seeded: {existing_count:,} rows at {output_path}")
                print(f"Geography already seeded: {existing_count:,} rows at {output_path}")
                print("  Use --force to re-seed")
                spark.stop()
                return existing_count
        except Exception:
            pass
        finally:
            spark.stop()

    print("=" * 70)
    print("Seeding Geography Dimension from Census Bureau")
    print("=" * 70)
    print()

    # Fetch data from Census Bureau API
    print("1. Fetching states from Census Bureau API...")
    try:
        states = fetch_states()
    except Exception as e:
        logger.error(f"Failed to fetch states: {e}", exc_info=True)
        print(f"   ERROR: Failed to fetch states: {e}")
        sys.exit(1)
    print(f"   Fetched {len(states)} states (including DC)")
    print()

    print("2. Fetching counties from Census Bureau API...")
    try:
        counties = fetch_counties()
    except Exception as e:
        logger.error(f"Failed to fetch counties: {e}", exc_info=True)
        print(f"   ERROR: Failed to fetch counties: {e}")
        sys.exit(1)
    print(f"   Fetched {len(counties)} counties")
    print()

    # Build final rows
    print("3. Building dim_geography rows...")
    rows = build_geography_rows(states, counties)
    total = len(rows)
    print(f"   Total rows: {total:,} ({len(states)} states + {len(counties)} counties)")
    print()

    # Show sample
    print("4. Sample data:")
    print(f"   {'Type':<8} {'Code':<6} {'Name':<40} {'Abbr':<5} {'Population':>12}")
    print(f"   {'-'*8} {'-'*6} {'-'*40} {'-'*5} {'-'*12}")
    for row in rows[:5]:
        pop = f"{row['population']:>12,}" if row["population"] else "           -"
        print(f"   {row['geography_type']:<8} {row['geography_code']:<6} "
              f"{row['geography_name'][:40]:<40} {row['state_abbr']:<5} {pop}")
    print("   ...")
    # Show a few counties
    county_rows = [r for r in rows if r["geography_type"] == "COUNTY"]
    for row in county_rows[:5]:
        pop = f"{row['population']:>12,}" if row["population"] else "           -"
        print(f"   {row['geography_type']:<8} {row['geography_code']:<6} "
              f"{row['geography_name'][:40]:<40} {row['state_abbr']:<5} {pop}")
    print()

    if dry_run:
        print("=" * 70)
        print(f"DRY RUN: Would write {total:,} rows to {output_path}")
        print("=" * 70)
        return total

    # Write with Spark + Delta Lake
    print("5. Initializing Spark...")
    from de_funk.orchestration.common.spark_session import get_spark
    from pyspark.sql.types import (
        StructType, StructField, LongType, StringType, DoubleType,
    )

    spark = get_spark("GeographySeed")
    print()

    schema = StructType([
        StructField("geography_id", LongType(), nullable=False),
        StructField("geography_type", StringType(), nullable=False),
        StructField("geography_code", StringType(), nullable=False),
        StructField("geography_name", StringType(), nullable=False),
        StructField("parent_geography_id", LongType(), nullable=True),
        StructField("state_fips", StringType(), nullable=False),
        StructField("state_name", StringType(), nullable=False),
        StructField("state_abbr", StringType(), nullable=False),
        StructField("county_fips", StringType(), nullable=True),
        StructField("county_name", StringType(), nullable=True),
        StructField("region", StringType(), nullable=True),
        StructField("division", StringType(), nullable=True),
        StructField("latitude", DoubleType(), nullable=True),
        StructField("longitude", DoubleType(), nullable=True),
        StructField("population", LongType(), nullable=True),
        StructField("land_area_sqmi", DoubleType(), nullable=True),
    ])

    # Convert rows to tuples in schema order
    spark_rows = []
    for r in rows:
        spark_rows.append((
            r["geography_id"],
            r["geography_type"],
            r["geography_code"],
            r["geography_name"],
            r["parent_geography_id"],
            r["state_fips"],
            r["state_name"],
            r["state_abbr"],
            r["county_fips"],
            r["county_name"],
            r["region"],
            r["division"],
            r["latitude"],
            r["longitude"],
            r["population"],
            r["land_area_sqmi"],
        ))

    df = spark.createDataFrame(spark_rows, schema=schema)

    print(f"6. Writing to Delta Lake...")
    print(f"   Path: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.write.format("delta").mode("overwrite").save(str(output_path))
    print(f"   Written successfully!")
    print()

    # Verify
    print("7. Verifying...")
    verify_df = spark.read.format("delta").load(str(output_path))
    verify_count = verify_df.count()
    print(f"   Verified: {verify_count:,} rows")
    print()

    print("   Breakdown by type:")
    verify_df.groupBy("geography_type").count().orderBy("geography_type").show()

    print("=" * 70)
    print("Geography seed complete!")
    print("=" * 70)
    print()
    print(f"Total rows: {verify_count:,}")
    print(f"Output: {output_path}")
    print()

    spark.stop()
    return verify_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed geography dimension (states + counties) from Census Bureau"
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Storage root path (default: /shared/storage or repo_root/storage)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and preview data without writing to Delta Lake",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-seed even if data exists",
    )
    args = parser.parse_args()

    storage_path = Path(args.storage_path) if args.storage_path else None

    try:
        seed_geography(
            storage_path=storage_path,
            dry_run=args.dry_run,
            force=args.force,
        )
    except Exception as e:
        logger.error(f"Geography seed failed: {e}", exc_info=True)
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

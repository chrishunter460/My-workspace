#!/usr/bin/env python3
"""
Debug script to investigate why exchange_name is NULL in auto-join results.

ROOT CAUSE IDENTIFIED:
- dim_company.exchange_code contains MIC codes (XNAS, XNYS, ARCX) from Polygon API
- dim_exchange.exchange_code contained numeric IDs (1, 10, 11)
- Zero matching records between the two tables

FIX APPLIED:
- Updated ExchangesFacet to use 'mic' field from Polygon API
- This will populate dim_exchange.exchange_code with MIC codes

NEXT STEPS TO COMPLETE FIX:
1. Re-ingest bronze exchanges data to get MIC codes from Polygon API
2. Run this script again to verify exchange codes now match
3. Test dimensional selector exchange tab

To re-ingest exchanges:
  # Run the exchange ingestion pipeline
  # This will fetch fresh data from Polygon API with MIC codes
"""

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.core.duckdb_connection import DuckDBConnection

# Initialize DuckDB connection
conn = DuckDBConnection()

print("=" * 70)
print("INVESTIGATING NULL EXCHANGE_NAME IN AUTO-JOIN RESULTS")
print("=" * 70)

# Query 1: Check dim_company exchange_code data quality
print("\n1. dim_company exchange_code data quality:")
print("-" * 70)
result1 = conn.execute("""
    SELECT
        COUNT(*) as total_rows,
        COUNT(exchange_code) as non_null_exchange_codes,
        COUNT(DISTINCT exchange_code) as distinct_exchange_codes,
        COUNT(CASE WHEN exchange_code IS NULL THEN 1 END) as null_count,
        COUNT(CASE WHEN exchange_code = '' THEN 1 END) as empty_string_count
    FROM read_parquet('storage/silver/company/dims/dim_company/**/*.parquet')
""").fetchdf()
print(result1.to_string(index=False))

# Query 2: Show top exchange_code values in dim_company
print("\n2. Top exchange_code values in dim_company:")
print("-" * 70)
result2 = conn.execute("""
    SELECT
        exchange_code,
        COUNT(*) as company_count
    FROM read_parquet('storage/silver/company/dims/dim_company/**/*.parquet')
    WHERE exchange_code IS NOT NULL AND exchange_code != ''
    GROUP BY exchange_code
    ORDER BY company_count DESC
    LIMIT 10
""").fetchdf()
print(result2.to_string(index=False))

# Query 3: Show all exchange_code values in dim_exchange
print("\n3. All exchange_code values in dim_exchange:")
print("-" * 70)
result3 = conn.execute("""
    SELECT
        exchange_code,
        exchange_name
    FROM read_parquet('storage/silver/company/dims/dim_exchange/**/*.parquet')
    ORDER BY exchange_code
""").fetchdf()
print(result3.to_string(index=False))
print(f"Total exchanges: {len(result3)}")

# Query 4: Check for matching exchange_codes between tables
print("\n4. Matching exchange_codes between dim_company and dim_exchange:")
print("-" * 70)
result4 = conn.execute("""
    SELECT
        c.exchange_code as company_exchange_code,
        e.exchange_code as exchange_exchange_code,
        COUNT(DISTINCT c.ticker) as matching_companies
    FROM read_parquet('storage/silver/company/dims/dim_company/**/*.parquet') c
    INNER JOIN read_parquet('storage/silver/company/dims/dim_exchange/**/*.parquet') e
        ON c.exchange_code = e.exchange_code
    GROUP BY c.exchange_code, e.exchange_code
    ORDER BY matching_companies DESC
    LIMIT 10
""").fetchdf()
print(result4.to_string(index=False))
print(f"Total matching exchange codes: {len(result4)}")

# Query 5: Check sample companies with their exchange_code
print("\n5. Sample companies with exchange_code:")
print("-" * 70)
result5 = conn.execute("""
    SELECT
        ticker,
        company_name,
        exchange_code,
        LENGTH(exchange_code) as code_length
    FROM read_parquet('storage/silver/company/dims/dim_company/**/*.parquet')
    WHERE exchange_code IS NOT NULL
    LIMIT 20
""").fetchdf()
print(result5.to_string(index=False))

# Query 6: Test the actual join that's failing
print("\n6. Testing the actual LEFT JOIN (sample 20 rows):")
print("-" * 70)
result6 = conn.execute("""
    SELECT
        c.ticker,
        c.company_name,
        c.exchange_code as company_exchange_code,
        e.exchange_code as exchange_exchange_code,
        e.exchange_name,
        CASE
            WHEN e.exchange_name IS NULL THEN 'NO MATCH'
            ELSE 'MATCH'
        END as join_status
    FROM read_parquet('storage/silver/company/dims/dim_company/**/*.parquet') c
    LEFT JOIN read_parquet('storage/silver/company/dims/dim_exchange/**/*.parquet') e
        ON c.exchange_code = e.exchange_code
    LIMIT 20
""").fetchdf()
print(result6.to_string(index=False))

# Query 7: Count join success rate
print("\n7. Join success rate:")
print("-" * 70)
result7 = conn.execute("""
    SELECT
        CASE
            WHEN e.exchange_name IS NULL THEN 'No Match'
            ELSE 'Match'
        END as join_result,
        COUNT(*) as company_count
    FROM read_parquet('storage/silver/company/dims/dim_company/**/*.parquet') c
    LEFT JOIN read_parquet('storage/silver/company/dims/dim_exchange/**/*.parquet') e
        ON c.exchange_code = e.exchange_code
    GROUP BY join_result
""").fetchdf()
print(result7.to_string(index=False))

print("\n" + "=" * 70)
print("INVESTIGATION COMPLETE")
print("=" * 70)

conn.stop()

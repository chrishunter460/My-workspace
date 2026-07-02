#!/usr/bin/env python3
"""
Test Alpha Vantage API - Diagnostic Script

This script directly tests Alpha Vantage API endpoints to diagnose issues.
Helps identify problems with API keys, quotas, rate limits, or specific tickers.

Usage:
    # Test with default ticker (AAPL)
    python -m scripts.test.test_alpha_vantage_api

    # Test specific ticker
    python -m scripts.test.test_alpha_vantage_api --ticker ABI

    # Test multiple tickers
    python -m scripts.test.test_alpha_vantage_api --tickers ABI AAPL MSFT GOOGL

    # Test all endpoints
    python -m scripts.test.test_alpha_vantage_api --ticker ABI --all-endpoints

    # Show raw API responses
    python -m scripts.test.test_alpha_vantage_api --ticker ABI --show-raw

Tests Performed:
1. API key validation
2. OVERVIEW endpoint (company fundamentals)
3. TIME_SERIES_DAILY_ADJUSTED endpoint (price data)
4. LISTING_STATUS endpoint (bulk ticker discovery)
5. Raw response inspection
6. Rate limit detection
7. Quota exhaustion detection
"""

import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
import time
import logging

# Add repo root to path
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

try:
    import requests
except ImportError:
    print("❌ ERROR: Missing dependency: requests")
    print("Install with: pip install requests")
    sys.exit(1)

from de_funk.config import ConfigLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlphaVantageDiagnostic:
    """Diagnostic tool for Alpha Vantage API testing."""

    def __init__(self, api_keys: List[str], show_raw: bool = False):
        """
        Initialize diagnostic tool.

        Args:
            api_keys: List of API keys to test
            show_raw: If True, show raw API responses
        """
        self.api_keys = api_keys
        self.show_raw = show_raw
        self.base_url = "https://www.alphavantage.co/query"
        self.test_results = {
            'api_keys_tested': 0,
            'api_keys_valid': 0,
            'api_keys_exhausted': 0,
            'api_keys_invalid': 0,
            'endpoints_tested': 0,
            'endpoints_successful': 0,
            'endpoints_failed': 0,
            'tickers_tested': 0,
            'tickers_successful': 0,
            'tickers_failed': 0,
            'errors': []
        }

    def _make_request(self, params: Dict[str, str], description: str) -> Dict[str, Any]:
        """
        Make API request and return response.

        Args:
            params: Query parameters
            description: Description of the request for logging

        Returns:
            Response dictionary
        """
        try:
            logger.info(f"Testing: {description}")
            logger.info(f"URL: {self.base_url}?{self._format_params(params)}")

            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            # Try to parse as JSON
            try:
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'raw_text': response.text,
                    'status_code': response.status_code
                }
            except json.JSONDecodeError:
                # Might be CSV (LISTING_STATUS)
                return {
                    'success': True,
                    'data': None,
                    'raw_text': response.text,
                    'status_code': response.status_code,
                    'content_type': 'csv'
                }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            }

    def _format_params(self, params: Dict[str, str]) -> str:
        """Format params for display (mask API key)."""
        display_params = params.copy()
        if 'apikey' in display_params:
            key = display_params['apikey']
            display_params['apikey'] = f"{key[:4]}...{key[-4:]}"
        return "&".join([f"{k}={v}" for k, v in display_params.items()])

    def _check_api_error(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Check if API response contains an error.

        Returns:
            Error message if error detected, None otherwise
        """
        if not isinstance(data, dict):
            return None

        # Check for explicit errors
        if "Error Message" in data:
            return f"API Error: {data['Error Message']}"

        # Check for rate limit / quota messages
        if "Information" in data and len(data) == 1:
            info_msg = data["Information"]
            if "rate limit" in info_msg.lower():
                return f"Rate Limit: {info_msg}"
            elif "call frequency" in info_msg.lower():
                return f"Call Frequency: {info_msg}"
            else:
                return f"API Info: {info_msg}"

        # Check for Note (sometimes indicates issues)
        if "Note" in data and len(data) == 1:
            return f"API Note: {data['Note']}"

        return None

    def test_api_key(self, api_key: str) -> bool:
        """
        Test if API key is valid using a simple query.

        Args:
            api_key: API key to test

        Returns:
            True if valid, False otherwise
        """
        self.test_results['api_keys_tested'] += 1

        print(f"\n{'='*80}")
        print(f"TESTING API KEY: {api_key[:4]}...{api_key[-4:]}")
        print(f"{'='*80}")

        # Test with AAPL OVERVIEW (simple, reliable test)
        params = {
            'function': 'OVERVIEW',
            'symbol': 'AAPL',
            'apikey': api_key
        }

        result = self._make_request(params, "API Key Validation (AAPL OVERVIEW)")

        if not result['success']:
            print(f"❌ API Key INVALID: Network error - {result['error']}")
            self.test_results['api_keys_invalid'] += 1
            self.test_results['errors'].append({
                'type': 'api_key_network_error',
                'key': f"{api_key[:4]}...{api_key[-4:]}",
                'error': result['error']
            })
            return False

        if self.show_raw:
            print(f"\nRaw Response (first 500 chars):")
            print(result['raw_text'][:500])
            print("...")

        # Check for errors
        if result['data']:
            error_msg = self._check_api_error(result['data'])
            if error_msg:
                print(f"❌ API Key ISSUE: {error_msg}")
                if "rate limit" in error_msg.lower() or "frequency" in error_msg.lower():
                    self.test_results['api_keys_exhausted'] += 1
                else:
                    self.test_results['api_keys_invalid'] += 1
                self.test_results['errors'].append({
                    'type': 'api_key_error',
                    'key': f"{api_key[:4]}...{api_key[-4:]}",
                    'error': error_msg
                })
                return False

            # Check if we got valid data
            if 'Symbol' in result['data'] and result['data']['Symbol'] == 'AAPL':
                print(f"✅ API Key VALID")
                print(f"   Company: {result['data'].get('Name', 'N/A')}")
                print(f"   Exchange: {result['data'].get('Exchange', 'N/A')}")
                print(f"   Sector: {result['data'].get('Sector', 'N/A')}")
                self.test_results['api_keys_valid'] += 1
                return True
            else:
                print(f"⚠ API Key UNKNOWN: Got response but unexpected format")
                print(f"   Keys in response: {list(result['data'].keys())[:10]}")
                self.test_results['api_keys_invalid'] += 1
                return False

        print(f"⚠ API Key UNKNOWN: No JSON data returned")
        return False

    def test_overview_endpoint(self, api_key: str, ticker: str) -> bool:
        """
        Test OVERVIEW endpoint with specific ticker.

        Args:
            api_key: API key to use
            ticker: Ticker symbol to test

        Returns:
            True if successful, False otherwise
        """
        self.test_results['endpoints_tested'] += 1
        self.test_results['tickers_tested'] += 1

        print(f"\n{'='*80}")
        print(f"TESTING OVERVIEW ENDPOINT: {ticker}")
        print(f"{'='*80}")

        params = {
            'function': 'OVERVIEW',
            'symbol': ticker,
            'apikey': api_key
        }

        result = self._make_request(params, f"OVERVIEW for {ticker}")

        if not result['success']:
            print(f"❌ Network Error: {result['error']}")
            self.test_results['endpoints_failed'] += 1
            self.test_results['tickers_failed'] += 1
            self.test_results['errors'].append({
                'type': 'overview_network_error',
                'ticker': ticker,
                'error': result['error']
            })
            return False

        if self.show_raw:
            print(f"\nRaw Response (first 1000 chars):")
            print(result['raw_text'][:1000])
            print("...")

        # Check for errors
        if result['data']:
            error_msg = self._check_api_error(result['data'])
            if error_msg:
                print(f"❌ API Error: {error_msg}")
                self.test_results['endpoints_failed'] += 1
                self.test_results['tickers_failed'] += 1
                self.test_results['errors'].append({
                    'type': 'overview_api_error',
                    'ticker': ticker,
                    'error': error_msg
                })
                return False

            # Check if we got valid data
            if 'Symbol' in result['data']:
                print(f"✅ SUCCESS")
                print(f"   Symbol: {result['data'].get('Symbol', 'N/A')}")
                print(f"   Name: {result['data'].get('Name', 'N/A')}")
                print(f"   Exchange: {result['data'].get('Exchange', 'N/A')}")
                print(f"   Asset Type: {result['data'].get('AssetType', 'N/A')}")
                print(f"   Sector: {result['data'].get('Sector', 'N/A')}")
                print(f"   Market Cap: {result['data'].get('MarketCapitalization', 'N/A')}")
                print(f"   CIK: {result['data'].get('CIK', 'N/A')}")
                self.test_results['endpoints_successful'] += 1
                self.test_results['tickers_successful'] += 1
                return True
            else:
                print(f"⚠ Unexpected response format")
                print(f"   Keys in response: {list(result['data'].keys())[:15]}")
                if len(result['data']) == 0:
                    print(f"   ⚠ Empty response - ticker may not exist")
                self.test_results['endpoints_failed'] += 1
                self.test_results['tickers_failed'] += 1
                return False

        print(f"⚠ No JSON data returned")
        self.test_results['endpoints_failed'] += 1
        self.test_results['tickers_failed'] += 1
        return False

    def test_prices_endpoint(self, api_key: str, ticker: str, outputsize: str = "compact") -> bool:
        """
        Test TIME_SERIES_DAILY_ADJUSTED endpoint.

        Args:
            api_key: API key to use
            ticker: Ticker symbol to test
            outputsize: "compact" (100 days) or "full" (20+ years)

        Returns:
            True if successful, False otherwise
        """
        self.test_results['endpoints_tested'] += 1

        print(f"\n{'='*80}")
        print(f"TESTING PRICES ENDPOINT: {ticker} (outputsize={outputsize})")
        print(f"{'='*80}")

        params = {
            'function': 'TIME_SERIES_DAILY_ADJUSTED',
            'symbol': ticker,
            'outputsize': outputsize,
            'apikey': api_key
        }

        result = self._make_request(params, f"TIME_SERIES_DAILY_ADJUSTED for {ticker}")

        if not result['success']:
            print(f"❌ Network Error: {result['error']}")
            self.test_results['endpoints_failed'] += 1
            self.test_results['errors'].append({
                'type': 'prices_network_error',
                'ticker': ticker,
                'error': result['error']
            })
            return False

        if self.show_raw:
            print(f"\nRaw Response (first 1000 chars):")
            print(result['raw_text'][:1000])
            print("...")

        # Check for errors
        if result['data']:
            error_msg = self._check_api_error(result['data'])
            if error_msg:
                print(f"❌ API Error: {error_msg}")
                self.test_results['endpoints_failed'] += 1
                self.test_results['errors'].append({
                    'type': 'prices_api_error',
                    'ticker': ticker,
                    'error': error_msg
                })
                return False

            # Check if we got valid time series data
            if 'Time Series (Daily)' in result['data']:
                time_series = result['data']['Time Series (Daily)']
                dates = sorted(list(time_series.keys()), reverse=True)
                print(f"✅ SUCCESS")
                print(f"   Dates returned: {len(dates)}")
                if dates:
                    print(f"   Latest date: {dates[0]}")
                    print(f"   Oldest date: {dates[-1]}")
                    # Show sample data
                    latest_data = time_series[dates[0]]
                    print(f"   Latest close: {latest_data.get('4. close', 'N/A')}")
                    print(f"   Latest volume: {latest_data.get('6. volume', 'N/A')}")
                self.test_results['endpoints_successful'] += 1
                return True
            else:
                print(f"⚠ Unexpected response format")
                print(f"   Keys in response: {list(result['data'].keys())[:15]}")
                self.test_results['endpoints_failed'] += 1
                return False

        print(f"⚠ No JSON data returned")
        self.test_results['endpoints_failed'] += 1
        return False

    def test_listing_status(self, api_key: str) -> bool:
        """
        Test LISTING_STATUS endpoint (bulk ticker discovery).

        Args:
            api_key: API key to use

        Returns:
            True if successful, False otherwise
        """
        self.test_results['endpoints_tested'] += 1

        print(f"\n{'='*80}")
        print(f"TESTING LISTING_STATUS ENDPOINT")
        print(f"{'='*80}")

        params = {
            'function': 'LISTING_STATUS',
            'apikey': api_key
        }

        result = self._make_request(params, "LISTING_STATUS (bulk ticker discovery)")

        if not result['success']:
            print(f"❌ Network Error: {result['error']}")
            self.test_results['endpoints_failed'] += 1
            self.test_results['errors'].append({
                'type': 'listing_network_error',
                'error': result['error']
            })
            return False

        if self.show_raw:
            print(f"\nRaw Response (first 1000 chars):")
            print(result['raw_text'][:1000])
            print("...")

        # LISTING_STATUS returns CSV, not JSON
        if result.get('content_type') == 'csv' or 'symbol,name,exchange' in result['raw_text'].lower():
            lines = result['raw_text'].strip().split('\n')
            print(f"✅ SUCCESS")
            print(f"   Format: CSV")
            print(f"   Lines returned: {len(lines)}")
            if len(lines) > 1:
                print(f"   Header: {lines[0][:80]}")
                print(f"   Sample row: {lines[1][:80]}")
            self.test_results['endpoints_successful'] += 1
            return True
        else:
            # Check if it's an error message in JSON
            if result['data']:
                error_msg = self._check_api_error(result['data'])
                if error_msg:
                    print(f"❌ API Error: {error_msg}")
                    self.test_results['endpoints_failed'] += 1
                    self.test_results['errors'].append({
                        'type': 'listing_api_error',
                        'error': error_msg
                    })
                    return False

            print(f"⚠ Unexpected response format (not CSV)")
            self.test_results['endpoints_failed'] += 1
            return False

    def show_summary(self):
        """Show test summary."""
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")

        print(f"\nAPI Keys:")
        print(f"  Tested: {self.test_results['api_keys_tested']}")
        print(f"  Valid: {self.test_results['api_keys_valid']}")
        print(f"  Exhausted/Rate Limited: {self.test_results['api_keys_exhausted']}")
        print(f"  Invalid: {self.test_results['api_keys_invalid']}")

        print(f"\nEndpoints:")
        print(f"  Tested: {self.test_results['endpoints_tested']}")
        print(f"  Successful: {self.test_results['endpoints_successful']}")
        print(f"  Failed: {self.test_results['endpoints_failed']}")

        print(f"\nTickers:")
        print(f"  Tested: {self.test_results['tickers_tested']}")
        print(f"  Successful: {self.test_results['tickers_successful']}")
        print(f"  Failed: {self.test_results['tickers_failed']}")

        if self.test_results['errors']:
            print(f"\nErrors ({len(self.test_results['errors'])}):")
            for i, error in enumerate(self.test_results['errors'][:10], 1):
                print(f"  {i}. [{error['type']}] {error.get('ticker', error.get('key', 'N/A'))}: {error['error'][:80]}")
            if len(self.test_results['errors']) > 10:
                print(f"  ... and {len(self.test_results['errors']) - 10} more errors")

        # Overall status
        print(f"\n{'='*80}")
        if self.test_results['api_keys_valid'] > 0 and self.test_results['endpoints_failed'] == 0:
            print("✅ ALL TESTS PASSED")
        elif self.test_results['api_keys_exhausted'] > 0:
            print("⚠ API KEY QUOTA EXHAUSTED - Try again later")
        elif self.test_results['api_keys_invalid'] > 0:
            print("❌ API KEY ISSUES DETECTED - Check .env file")
        else:
            print("⚠ SOME TESTS FAILED - Review errors above")
        print(f"{'='*80}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Alpha Vantage API Diagnostic Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--ticker',
        type=str,
        default='AAPL',
        help='Ticker symbol to test (default: AAPL)'
    )

    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Multiple ticker symbols to test'
    )

    parser.add_argument(
        '--all-endpoints',
        action='store_true',
        help='Test all endpoints (OVERVIEW, PRICES, LISTING_STATUS)'
    )

    parser.add_argument(
        '--show-raw',
        action='store_true',
        help='Show raw API responses'
    )

    parser.add_argument(
        '--outputsize',
        choices=['compact', 'full'],
        default='compact',
        help='Output size for price data (compact=100 days, full=20+ years)'
    )

    args = parser.parse_args()

    # Load configuration
    config = ConfigLoader().load()

    # Get API keys from configuration
    alpha_vantage_cfg = config.apis.get("alpha_vantage", {})
    if not alpha_vantage_cfg:
        logger.error("❌ ERROR: alpha_vantage_endpoints.json not found in configs/")
        sys.exit(1)

    # API keys are nested under credentials.api_keys
    credentials = alpha_vantage_cfg.get("credentials", {})
    api_keys = credentials.get("api_keys", [])

    if not api_keys:
        logger.error("❌ ERROR: No API keys found")
        logger.error("Expected structure in alpha_vantage_endpoints.json:")
        logger.error('  "credentials": { "api_keys": ["your_key_here"] }')
        logger.error("")
        logger.error("Or set environment variable: ALPHA_VANTAGE_API_KEYS=your_key_here")
        logger.error("(in .env file)")
        sys.exit(1)

    if isinstance(api_keys, str):
        # If it's a string, split by comma
        api_keys = [k.strip() for k in api_keys.split(",") if k.strip()]

    if not api_keys:
        logger.error("❌ ERROR: API keys list is empty")
        sys.exit(1)

    print(f"{'='*80}")
    print("ALPHA VANTAGE API DIAGNOSTIC TOOL")
    print(f"{'='*80}")
    print(f"API Keys found: {len(api_keys)}")
    print(f"Tickers to test: {args.tickers if args.tickers else [args.ticker]}")
    print(f"Show raw responses: {args.show_raw}")
    print(f"Test all endpoints: {args.all_endpoints}")

    # Create diagnostic tool
    diagnostic = AlphaVantageDiagnostic(api_keys=api_keys, show_raw=args.show_raw)

    # Use first API key for tests
    api_key = api_keys[0]

    # Step 1: Test API key validity
    api_key_valid = diagnostic.test_api_key(api_key)

    if not api_key_valid:
        print(f"\n⚠ API key validation failed - stopping tests")
        diagnostic.show_summary()
        sys.exit(1)

    # Step 2: Test tickers
    tickers_to_test = args.tickers if args.tickers else [args.ticker]

    for ticker in tickers_to_test:
        # Test OVERVIEW
        diagnostic.test_overview_endpoint(api_key, ticker)

        # Test PRICES if requested
        if args.all_endpoints:
            time.sleep(1)  # Rate limit buffer
            diagnostic.test_prices_endpoint(api_key, ticker, outputsize=args.outputsize)

    # Step 3: Test LISTING_STATUS if requested
    if args.all_endpoints:
        time.sleep(1)  # Rate limit buffer
        diagnostic.test_listing_status(api_key)

    # Show summary
    diagnostic.show_summary()


if __name__ == "__main__":
    main()

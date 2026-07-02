"""
API Validation Utility

Validates API access and date ranges before running pipelines.
Helps prevent failures due to API limitations.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Tuple, Optional
import urllib.request
import urllib.error
import json


class APIValidator:
    """
    Validates Polygon API access and capabilities.
    """

    def __init__(self, polygon_cfg: dict):
        """
        Initialize validator with Polygon configuration.

        Args:
            polygon_cfg: Polygon API configuration
        """
        self.polygon_cfg = polygon_cfg

        # Get API key from credentials (supports both formats for backward compatibility)
        credentials = polygon_cfg.get("credentials", {})
        api_keys = credentials.get("api_keys", [])

        # Use first key if available, otherwise fall back to deprecated 'api_key' field
        if api_keys:
            self.api_key = api_keys[0]
        else:
            self.api_key = credentials.get("api_key", "")

    def validate_date_range(
        self,
        date_from: str,
        date_to: str,
        auto_adjust: bool = True
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validate if date range is accessible with current API plan.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            auto_adjust: If True, suggest adjusted date range on failure

        Returns:
            Tuple of (is_valid, message, adjusted_from_date)
        """
        print("\n" + "=" * 80)
        print("API DATE RANGE VALIDATION")
        print("=" * 80)
        print(f"Requested range: {date_from} to {date_to}")
        print("Testing API access...")

        # Test a sample date from the requested range
        test_date = date_from

        try:
            # Try to fetch data for the first date
            url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{test_date}"
            params = {
                'adjusted': 'true',
                'apiKey': self.api_key
            }

            # Build URL with parameters
            param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"

            req = urllib.request.Request(full_url)
            req.add_header('User-Agent', 'de_Funk/1.0')

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

                # Check if we got valid data
                if data.get('status') == 'OK' and data.get('resultsCount', 0) > 0:
                    print(f"✓ API validation successful!")
                    print(f"  Sample date {test_date}: {data.get('resultsCount')} results")
                    print("=" * 80 + "\n")
                    return True, "Date range is accessible", None
                else:
                    message = f"No data available for {test_date}"
                    print(f"⚠ {message}")
                    print("=" * 80 + "\n")

                    if auto_adjust:
                        adjusted_date = self._suggest_adjusted_range()
                        return False, message, adjusted_date
                    return False, message, None

        except urllib.error.HTTPError as e:
            if e.code == 403:
                # Read error response
                error_body = e.read().decode('utf-8')
                try:
                    error_data = json.loads(error_body)
                    error_msg = error_data.get('message', 'Access denied')
                except:
                    error_msg = 'Access denied (403 Forbidden)'

                print(f"✗ API validation failed!")
                print(f"  Error: {error_msg}")

                # Check if it's a historical data limitation
                if 'historical entitlements' in error_msg.lower() or 'upgrade' in error_msg.lower():
                    print(f"\n  Your API plan has limited historical data access.")

                    if auto_adjust:
                        # Suggest a range that typically works
                        adjusted_date = self._suggest_adjusted_range()
                        print(f"  Suggested start date: {adjusted_date}")
                        print("=" * 80 + "\n")
                        return False, error_msg, adjusted_date
                    else:
                        print("=" * 80 + "\n")
                        return False, error_msg, None
                else:
                    print("=" * 80 + "\n")
                    return False, error_msg, None

            else:
                error_msg = f"HTTP {e.code}: {str(e)}"
                print(f"✗ API validation failed: {error_msg}")
                print("=" * 80 + "\n")
                return False, error_msg, None

        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            print(f"✗ {error_msg}")
            print("=" * 80 + "\n")
            return False, error_msg, None

    def _suggest_adjusted_range(self) -> str:
        """
        Suggest an adjusted date range based on typical API limitations.

        Returns:
            Suggested start date (YYYY-MM-DD)
        """
        # Most free/starter plans allow last 2 years
        # Conservative: suggest last 1.5 years to be safe
        suggested_date = datetime.now() - timedelta(days=547)  # ~1.5 years
        return suggested_date.strftime('%Y-%m-%d')

    def test_api_connection(self) -> Tuple[bool, str]:
        """
        Test basic API connection and authentication.

        Returns:
            Tuple of (is_connected, message)
        """
        print("\nTesting API connection...")

        try:
            # Use a recent date that should always work
            test_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{test_date}"
            params = {
                'adjusted': 'true',
                'apiKey': self.api_key
            }

            param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{param_str}"

            req = urllib.request.Request(full_url)
            req.add_header('User-Agent', 'de_Funk/1.0')

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

                if data.get('status') == 'OK':
                    print(f"✓ API connection successful")
                    return True, "Connected"
                else:
                    print(f"⚠ API connected but returned: {data.get('status')}")
                    return False, f"API returned status: {data.get('status')}"

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"✗ Authentication failed - check your API key")
                return False, "Invalid API key"
            elif e.code == 403:
                print(f"✗ Access forbidden - check API plan")
                return False, "Access forbidden"
            else:
                print(f"✗ HTTP {e.code}: {str(e)}")
                return False, f"HTTP {e.code}"

        except Exception as e:
            print(f"✗ Connection failed: {str(e)}")
            return False, str(e)

    def get_recommended_date_range(self, days: int = 90) -> Tuple[str, str]:
        """
        Get a recommended date range that should work with most API plans.

        Args:
            days: Number of days to go back (default: 90)

        Returns:
            Tuple of (date_from, date_to) in YYYY-MM-DD format
        """
        date_to = datetime.now().date()
        date_from = date_to - timedelta(days=days)

        # Ensure we don't go beyond typical 2-year limit
        max_historical = datetime.now() - timedelta(days=730)  # 2 years
        if datetime.fromisoformat(str(date_from)) < max_historical:
            date_from = max_historical.date()
            print(f"⚠ Adjusted start date to {date_from} (2-year limit)")

        return str(date_from), str(date_to)

    @staticmethod
    def prompt_user_for_adjusted_range(
        original_from: str,
        original_to: str,
        suggested_from: str
    ) -> Tuple[str, str, bool]:
        """
        Prompt user to accept adjusted date range or abort.

        Args:
            original_from: Original start date
            original_to: Original end date
            suggested_from: Suggested start date

        Returns:
            Tuple of (date_from, date_to, continue_flag)
        """
        print("\n" + "=" * 80)
        print("DATE RANGE ADJUSTMENT REQUIRED")
        print("=" * 80)
        print(f"Original range: {original_from} to {original_to}")
        print(f"Suggested range: {suggested_from} to {original_to}")
        print("\nOptions:")
        print("  1. Use suggested range (recommended)")
        print("  2. Enter custom start date")
        print("  3. Abort pipeline")
        print("=" * 80)

        while True:
            choice = input("\nSelect option (1/2/3): ").strip()

            if choice == '1':
                print(f"✓ Using suggested range: {suggested_from} to {original_to}")
                return suggested_from, original_to, True

            elif choice == '2':
                custom_date = input("Enter start date (YYYY-MM-DD): ").strip()
                try:
                    # Validate date format
                    datetime.strptime(custom_date, '%Y-%m-%d')
                    print(f"✓ Using custom range: {custom_date} to {original_to}")
                    return custom_date, original_to, True
                except ValueError:
                    print("✗ Invalid date format. Please use YYYY-MM-DD")
                    continue

            elif choice == '3':
                print("✗ Pipeline aborted by user")
                return original_from, original_to, False

            else:
                print("Invalid option. Please select 1, 2, or 3.")

"""
HTTP client for API requests with rate limiting and retry logic.

Provides:
- Rate limiting per API key
- Exponential backoff retry
- Structured logging for debugging
- Support for JSON and text responses
"""

import json
import time
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class HttpClient:
    """
    HTTP client with rate limiting and retry logic for API requests.

    Features:
    - Automatic rate limiting based on configured RPS
    - Exponential backoff on 429 and 5xx errors
    - API key rotation via key pool
    - Detailed logging for debugging
    """

    def __init__(self, base_urls, headers, rate_limit_per_sec, api_key_pool, safety_factor=0.9, max_retries=6):
        """
        Initialize HTTP client.

        Args:
            base_urls: Dict of base URL configurations
            headers: Default headers for requests
            rate_limit_per_sec: Maximum requests per second
            api_key_pool: API key pool for rotation
            safety_factor: Safety margin for rate limiting (default: 0.9)
            max_retries: Maximum retry attempts (default: 6)
        """
        self.base_urls = base_urls
        self.headers = headers
        self.configured_rps = float(rate_limit_per_sec or 0.0834)
        self.api_key_pool = api_key_pool
        self.safety = float(safety_factor)
        self.max_retries = int(max_retries)
        self._last_ts = 0.0
        logger.debug(f"HttpClient initialized: rps={self.configured_rps}, max_retries={max_retries}")

    def _effective_min_interval(self):
        """
        Calculate minimum interval between requests.

        Returns:
            Minimum seconds between requests based on configured RPS.
        """
        return 1.0 / self.configured_rps

    def _throttle(self):
        """Apply rate limiting by sleeping if needed."""
        min_interval = self._effective_min_interval()
        dt = time.time() - self._last_ts
        if dt < min_interval:
            sleep_time = min_interval - dt
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_ts = time.time()

    def _build_request(self, base_key, path, query, method):
        """
        Build urllib request with API key substitution.

        Args:
            base_key: Key for base URL lookup
            path: API endpoint path
            query: Query parameters dict
            method: HTTP method

        Returns:
            Tuple of (Request object, full URL string)
        """
        base = self.base_urls[base_key].rstrip("/")
        url = f"{base}{path}"

        # Get API key for this request
        key = self.api_key_pool.next_key()

        # Replace ${API_KEY} placeholders in query parameters (for Alpha Vantage)
        if query:
            query_with_key = {}
            for k, v in query.items():
                if isinstance(v, str) and "${API_KEY}" in v:
                    query_with_key[k] = v.replace("${API_KEY}", key or "")
                else:
                    query_with_key[k] = v
            url += "?" + urllib.parse.urlencode(query_with_key, doseq=True)

        # Replace ${API_KEY} placeholders in headers (for Polygon)
        hdrs = {k: v.replace("${API_KEY}", key or "") for k, v in self.headers.items()}

        return urllib.request.Request(url, headers=hdrs, method=method), url

    def request_text(self, base_key, path, query, method="GET"):
        """
        Make HTTP request and return raw text response.

        Use this for non-JSON endpoints (e.g., CSV, XML).

        Args:
            base_key: Key for base URL lookup
            path: API endpoint path
            query: Query parameters dict
            method: HTTP method (default: GET)

        Returns:
            Response body as string

        Raises:
            RuntimeError: If request fails after all retries
        """
        backoff_base = 2.0
        last_error = None

        for attempt in range(self.max_retries):
            self._throttle()
            req, url = self._build_request(base_key, path, query, method)

            try:
                logger.debug(f"Request attempt {attempt + 1}/{self.max_retries}: {method} {path}")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = resp.read().decode("utf-8")
                    logger.debug(f"Request successful: {len(result)} bytes")
                    return result

            except HTTPError as e:
                body = None
                try:
                    body = e.read().decode("utf-8")
                except (IOError, UnicodeDecodeError):
                    # Can't read error body - continue without it
                    pass

                last_error = e

                # 429 → backoff + retry
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else min(120.0, (backoff_base ** attempt)) + (0.1 * attempt)
                    logger.warning(f"Rate limited (429): waiting {wait:.1f}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait)
                    continue

                # 5xx → retry
                if 500 <= e.code < 600:
                    wait = min(60.0, (backoff_base ** attempt))
                    logger.warning(f"Server error ({e.code}): waiting {wait:.1f}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait)
                    continue

                # 4xx → raise with details
                logger.error(f"Client error ({e.code}) for {url}: {body}")
                raise RuntimeError(f"HTTP {e.code} for {url} :: query={query} :: body={body}") from e

            except URLError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = min(30.0, (backoff_base ** attempt))
                    logger.warning(f"URL error: {e}. Waiting {wait:.1f}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait)
                    continue
                logger.error(f"URLError after {self.max_retries} attempts for {url}: {e}")
                raise RuntimeError(f"URLError after {self.max_retries} attempts for {url}: {e}") from e

        logger.error(f"Request failed after {self.max_retries} attempts: {method} {path}")
        raise RuntimeError(f"Request failed after {self.max_retries} attempts for {url}")

    def request(self, base_key, path, query, method="GET"):
        """
        Make HTTP request and return JSON response.

        Args:
            base_key: Key for base URL lookup
            path: API endpoint path
            query: Query parameters dict
            method: HTTP method (default: GET)

        Returns:
            Parsed JSON response

        Raises:
            RuntimeError: If request fails after all retries
        """
        backoff_base = 2.0
        last_error = None

        for attempt in range(self.max_retries):
            self._throttle()
            req, url = self._build_request(base_key, path, query, method)

            try:
                logger.debug(f"Request attempt {attempt + 1}/{self.max_retries}: {method} {path}")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    logger.debug(f"Request successful: {method} {path}")
                    return result

            except HTTPError as e:
                body = None
                try:
                    body = e.read().decode("utf-8")
                except (IOError, UnicodeDecodeError):
                    # Can't read error body - continue without it
                    pass

                last_error = e

                # 429 → backoff + retry
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else min(120.0, (backoff_base ** attempt)) + (0.1 * attempt)
                    logger.warning(f"Rate limited (429): waiting {wait:.1f}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait)
                    continue

                # 5xx → retry
                if 500 <= e.code < 600:
                    wait = min(60.0, (backoff_base ** attempt))
                    logger.warning(f"Server error ({e.code}): waiting {wait:.1f}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait)
                    continue

                # 4xx → raise with details
                logger.error(f"Client error ({e.code}) for {url}: {body}")
                raise RuntimeError(f"HTTP {e.code} for {url} :: query={query} :: body={body}") from e

            except URLError as e:
                last_error = e
                wait = min(30.0, (backoff_base ** attempt))
                logger.warning(f"URL error: {e}. Waiting {wait:.1f}s before retry {attempt + 1}/{self.max_retries}")
                time.sleep(wait)
                continue

        logger.error(f"Request failed after {self.max_retries} retries: {method} {path}")
        raise RuntimeError(f"HTTP request failed after {self.max_retries} retries: {method} {path} {query}")

    def get(self, path: str, params: dict = None) -> dict:
        """Convenience GET request returning JSON."""
        return self.request("core", path, params or {})

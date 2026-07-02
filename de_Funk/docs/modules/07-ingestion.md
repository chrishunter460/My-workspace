---
title: "Ingestion Pipeline"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/pipelines/base/ingestor_engine.py
  - src/de_funk/pipelines/base/provider.py
  - src/de_funk/pipelines/base/socrata_client.py
  - src/de_funk/pipelines/base/socrata_provider.py
  - src/de_funk/pipelines/base/http_client.py
  - src/de_funk/pipelines/base/facet.py
  - src/de_funk/pipelines/base/key_pool.py
  - src/de_funk/pipelines/base/normalizer.py
  - src/de_funk/pipelines/base/registry.py
  - src/de_funk/pipelines/base/circuit_breaker.py
  - src/de_funk/pipelines/base/rate_limiter.py
  - src/de_funk/pipelines/base/progress_tracker.py
  - src/de_funk/pipelines/base/metrics.py
  - src/de_funk/pipelines/ingestors/bronze_sink.py
  - src/de_funk/pipelines/ingestors/raw_sink.py
  - src/de_funk/pipelines/providers/alpha_vantage/alpha_vantage_provider.py
  - src/de_funk/pipelines/providers/alpha_vantage/alpha_vantage_registry.py
  - src/de_funk/pipelines/providers/registry.py
---

# Ingestion Pipeline

> Download raw data, normalize to Bronze Delta tables — IngestorEngine, providers, HTTP client, rate limiting, circuit breakers.

## Purpose & Design Decisions

### What Problem This Solves

de_Funk ingests data from multiple external APIs (Alpha Vantage for financial data, Socrata/SODA for open government data) into a Bronze layer of Delta Lake tables. Each API has different authentication, rate limits, pagination patterns, response formats, and schema conventions. The ingestion pipeline provides a provider-agnostic framework that standardizes this process: fetch raw data in batches, normalize to Spark DataFrames, and write to Bronze Delta tables with configurable write strategies (append, upsert, overwrite).

Key challenges addressed:
- **Rate limiting**: Alpha Vantage free tier allows 5 calls/min; premium allows 75/min. Socrata APIs have different limits. The token bucket rate limiter handles this per-provider.
- **Failure isolation**: A single API outage should not block ingestion of other data types. Circuit breakers prevent cascading failures.
- **Throughput**: API fetches and Delta writes can overlap using async writes with a bounded in-memory queue, yielding 2-3x throughput improvement.
- **Resumability**: Long-running ingestion of 500+ tickers needs checkpointing to resume from failure.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| Provider abstraction with "work_item" concept | Different providers have different granularity: Alpha Vantage work items are data types (prices, reference), Socrata work items are endpoint IDs (crimes, budget). The abstract `BaseProvider` unifies both patterns with `list_work_items()`, `fetch()`, `normalize()`, `get_table_name()`. | Separate ingestion code per provider |
| Configuration from markdown documentation files | Provider and endpoint configs live in markdown files with YAML frontmatter under `data_sources/`. This keeps documentation and configuration in sync (single source of truth). `MarkdownConfigLoader` parses these files. | Separate YAML config files |
| Token bucket rate limiting (not simple sleep) | Token bucket allows burst capacity while maintaining average rate. A provider that sleeps 1s between calls wastes capacity when the API allows bursts. The bucket accumulates tokens during idle periods. | Fixed `time.sleep()` between requests |
| Async writes via ThreadPoolExecutor | Decouples API fetching from Delta Lake writes. While the writer thread commits one batch, the fetch thread can start the next API call. Bounded queue (max 3 pending) prevents OOM. | Sequential fetch-then-write per batch |
| BronzeSink with multiple write strategies (append_immutable, upsert, overwrite) | Time-series data (prices) is append-only and idempotent. Reference data needs upsert. Financial statements may need full overwrite. Endpoint config in markdown specifies the strategy. | Single overwrite-all strategy |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| API base URL, rate limit, API key env var | Provider markdown frontmatter (`base_url`, `rate_limit`, `env_api_key`) | `data_sources/{provider}/provider.md` |
| Endpoint resource IDs, schemas, write strategies | Endpoint markdown frontmatter | `data_sources/{provider}/endpoints/{endpoint}.md` |
| Field mappings (source -> target column names) | Endpoint `schema:` section with `source:` fields | `data_sources/{provider}/endpoints/{endpoint}.md` |
| Type coercions (string -> double, etc.) | Endpoint `schema:` section with `{coerce: type}` | `data_sources/{provider}/endpoints/{endpoint}.md` |
| Per-provider rate limits | `PROVIDER_RATE_LIMITS` dict + `RateLimiterManager.configure_provider()` | `src/de_funk/pipelines/base/rate_limiter.py` |
| Circuit breaker thresholds | `CircuitBreakerConfig` (default: 5 failures, 60s timeout) | `src/de_funk/pipelines/base/circuit_breaker.py` |
| Bronze storage paths | `storage.json` > `roots.bronze` | `configs/storage.json` |

## Architecture

### Where This Fits

```
[External APIs]                    [Raw Storage]
  Alpha Vantage  ──┐                    │
  Socrata/SODA   ──┤                    │
  BLS            ──┘                    │
        │                               │
   [HttpClient / SocrataClient]         │
   [Rate Limiter + Circuit Breaker]     │
        │                               │
   [BaseProvider.fetch()]  ──────> [RawSink]
        │
   [BaseProvider.normalize() / Facet / SparkNormalizer]
        │
   [IngestorEngine.run()]
        │
   [BronzeSink.write() / upsert() / append_immutable()]
        │
   [Bronze Delta Lake Tables]
        │
   [Build Pipeline reads Bronze for Silver transforms]
```

The ingestion pipeline sits between external APIs and the Bronze layer. It produces Delta Lake tables that the build pipeline (Module 06) reads as source data for Silver dimensional models.

### Dependencies

| Depends On | What For |
|------------|----------|
| `de_funk.config.markdown_loader.MarkdownConfigLoader` | Reading provider and endpoint configs from markdown |
| `de_funk.config.logging` | Structured logging |
| `pyspark` (Spark) | DataFrame creation and normalization (via `SparkNormalizer`, `Facet`) |
| `delta-spark` | Delta Lake write operations in `BronzeSink` |
| `urllib` | HTTP requests in `HttpClient` |
| `requests` / `urllib3` | HTTP requests in `SocrataClient` |

| Depended On By | What For |
|----------------|----------|
| `de_funk.models.base.graph_builder.GraphBuilder` | Reading Bronze tables as build sources |
| `de_funk.orchestration.scheduler` | Scheduled daily price ingestion and market cap refresh |
| `de_funk.orchestration.checkpoint.CheckpointManager` | Tracking ingestion progress per ticker |
| `scripts/ingest/` | CLI scripts for manual ingestion runs |

## Key Classes

### IngestionResults

**File**: `src/de_funk/pipelines/base/ingestor_engine.py:55`

**Purpose**: Results from an ingestion run.

| Attribute | Type |
|-----------|------|
| `work_items` | `List[str]` |
| `total_work_items` | `int` |
| `completed_work_items` | `int` |
| `total_records` | `int` |
| `total_errors` | `int` |
| `results` | `Dict[str, WorkItemResult]` |
| `elapsed_seconds` | `float` |

| Method | Description |
|--------|-------------|
| `add_result(result: WorkItemResult) -> None` | Add a work item result. |
| `summary() -> Dict[str, Any]` | Get summary statistics. |
| `print_summary() -> None` | Print human-readable summary. |

### WriteTask

**File**: `src/de_funk/pipelines/base/ingestor_engine.py:109`

**Purpose**: A queued write task.

| Attribute | Type |
|-----------|------|
| `df` | `Any` |
| `table_name` | `str` |
| `partitions` | `Optional[List[str]]` |
| `record_count` | `int` |
| `work_item` | `str` |

### IngestorEngine

**File**: `src/de_funk/pipelines/base/ingestor_engine.py:118`

**Purpose**: Unified ingestion engine with async writes.

| Attribute | Type |
|-----------|------|
| `_executor` | `Optional[ThreadPoolExecutor]` |
| `_executor_lock` | `—` |

| Method | Description |
|--------|-------------|
| `from_session(session, provider: BaseProvider, max_pending_writes: int, writer_threads: int)` | Create IngestorEngine from an IngestSession. |
| `get_executor(max_workers: int) -> ThreadPoolExecutor` | Get or create shared ThreadPoolExecutor. |
| `shutdown_executor(wait: bool) -> None` | Shutdown the shared executor. |
| `run(work_items: List[str], write_batch_size: int, max_records: Optional[int], silent: bool, async_writes: bool) -> IngestionResults` | Run ingestion for work items. |
| `run_with_discovery(write_batch_size: int, max_records: Optional[int], silent: bool) -> IngestionResults` | Run ingestion with automatic work item discovery. |

### DataType (Enum)

**File**: `src/de_funk/pipelines/base/provider.py:45`

**Purpose**: Standard data types supported by providers.

| Attribute | Type |
|-----------|------|
| `REFERENCE` | `—` |
| `PRICES` | `—` |
| `INCOME_STATEMENT` | `—` |
| `BALANCE_SHEET` | `—` |
| `CASH_FLOW` | `—` |
| `EARNINGS` | `—` |
| `OPTIONS` | `—` |
| `ETF_PROFILE` | `—` |
| `DIVIDENDS` | `—` |
| `SPLITS` | `—` |

### FetchResult

**File**: `src/de_funk/pipelines/base/provider.py:60`

**Purpose**: Result from a single data fetch operation.

| Attribute | Type |
|-----------|------|
| `ticker` | `str` |
| `data_type` | `DataType` |
| `success` | `bool` |
| `data` | `Optional[Any]` |
| `error` | `Optional[str]` |
| `api_calls` | `int` |

### WorkItemResult

**File**: `src/de_funk/pipelines/base/provider.py:74`

**Purpose**: Result from ingesting a single work item.

| Attribute | Type |
|-----------|------|
| `work_item` | `str` |
| `success` | `bool` |
| `record_count` | `int` |
| `error` | `Optional[str]` |
| `table_path` | `Optional[str]` |

### BaseProvider

**File**: `src/de_funk/pipelines/base/provider.py:83`

**Purpose**: Abstract base class for data providers.

| Attribute | Type |
|-----------|------|
| `PROVIDER_NAME` | `str` |

| Method | Description |
|--------|-------------|
| `base_url() -> str` | Get base URL from markdown config. |
| `rate_limit() -> float` | Get rate limit from markdown config. |
| `env_api_key() -> str` | Get environment variable name for API key. |
| `get_provider_setting(key: str, default: Any) -> Any` | Get provider-specific setting from markdown config. |
| `get_endpoint_config(endpoint_id: str) -> Optional[EndpointConfig]` | Get endpoint configuration by ID. |
| `list_work_items() -> List[str]` | List available work items for ingestion. |
| `fetch(work_item: str, max_records: Optional[int]) -> Generator[List[Dict], None, None]` | Fetch data for a single work item, yielding batches of raw records. |
| `normalize(records: List[Dict], work_item: str) -> Any` | Normalize raw records to a Spark DataFrame. |
| `get_table_name(work_item: str) -> str` | Get the Bronze table name for a work item. |
| `get_partitions(work_item: str) -> Optional[List[str]]` | Get partition columns for a work item from endpoint config. |
| `get_key_columns(work_item: str) -> List[str]` | Get key columns for upsert operations from endpoint config. |
| `get_write_strategy(work_item: str) -> str` | Get write strategy from endpoint config. |
| `get_date_column(work_item: str) -> Optional[str]` | Get date column for append_immutable strategy. |
| `get_response_key(work_item: str) -> Optional[str]` | Get response key for extracting data from API response. |
| `get_field_mappings(work_item: str) -> Dict[str, str]` | Get source to target field name mappings from endpoint schema. |
| `get_type_coercions(work_item: str) -> Dict[str, str]` | Get type coercion rules from endpoint schema. |

### SocrataClient

**File**: `src/de_funk/pipelines/base/socrata_client.py:55`

**Purpose**: HTTP client for Socrata Open Data APIs (SODA).

| Attribute | Type |
|-----------|------|
| `DEFAULT_LIMIT` | `—` |
| `MAX_RETRIES` | `—` |
| `DEFAULT_TIMEOUT` | `—` |

| Method | Description |
|--------|-------------|
| `request(resource_id: str, query_params: Optional[Dict[str, Any]]) -> List[Dict]` | Make a single request to a Socrata resource. |
| `fetch_all(resource_id: str, query_params: Optional[Dict[str, Any]], limit: int, max_records: Optional[int], label: Optional[str]) -> Generator[List[Dict], None, None]` | Fetch all records from a resource using pagination. |
| `fetch_all_flat(resource_id: str, query_params: Optional[Dict[str, Any]], limit: int, max_records: Optional[int]) -> List[Dict]` | Fetch all records from a resource, returning a flat list. |
| `get_row_count(resource_id: str, where_clause: Optional[str]) -> int` | Get the total row count for a resource. |
| `get_metadata(resource_id: str) -> Dict` | Get metadata for a resource. |
| `fetch_csv(resource_id: str, batch_size: int, max_records: Optional[int], label: Optional[str]) -> Generator[List[Dict], None, None]` | Fetch all records via CSV bulk download (streaming). |
| `download_csv_to_file(resource_id: str, output_path: str, label: Optional[str], resume: bool, use_gzip: bool) -> int` | Download CSV to a file on disk with optional gzip compression. |
| `fetch_csv_from_file(file_path: str, batch_size: int, max_records: Optional[int], label: Optional[str]) -> Generator[List[Dict], None, None]` | Read CSV from a file on disk and yield batches. |

### SocrataBaseProvider (BaseProvider)

**File**: `src/de_funk/pipelines/base/socrata_provider.py:34`

**Purpose**: Base class for Socrata API providers.

| Method | Description |
|--------|-------------|
| `enable_raw_save(storage_path: Path, enabled: bool) -> None` | Enable/disable saving raw API responses (CSV files) before transformation. |
| `list_work_items(status: str) -> List[str]` | List available endpoint IDs for ingestion. |
| `fetch(work_item: str, max_records: Optional[int]) -> Generator[List[Dict], None, None]` | Fetch data for an endpoint, yielding batches of records. |
| `normalize(records: List[Dict], work_item: str) -> DataFrame` | Normalize raw records to a Spark DataFrame. |
| `get_table_name(work_item: str) -> str` | Get Bronze table name for an endpoint. |
| `get_resource_id(endpoint_id: str) -> Optional[str]` | Get Socrata resource ID for an endpoint (public method). |
| `list_endpoints() -> List[str]` | List all available endpoint IDs (alias for list_work_items). |
| `read_csv_with_spark(csv_path: Path, endpoint: EndpointConfig) -> DataFrame` | Read CSV file directly with Spark (distributed across executors). |
| `get_raw_path(work_item: str) -> Optional[str]` | Get path to raw CSV file for bulk reading. |
| `read_raw_as_df(work_item: str, raw_path: str) -> Optional[DataFrame]` | Read raw CSV file(s) with Spark and return normalized DataFrame. |
| `download_all_csv(work_items: Optional[List[str]], force: bool) -> dict` | Download raw CSV files for all endpoints. No Spark, no Bronze — just HTTP. |

### HttpClient

**File**: `src/de_funk/pipelines/base/http_client.py:22`

**Purpose**: HTTP client with rate limiting and retry logic for API requests.

| Method | Description |
|--------|-------------|
| `request_text(base_key, path, query, method)` | Make HTTP request and return raw text response. |
| `request(base_key, path, query, method)` | Make HTTP request and return JSON response. |
| `get(path: str, params: dict) -> dict` | Convenience GET request returning JSON. |

### Facet

**File**: `src/de_funk/pipelines/base/facet.py:77`

**Purpose**: Markdown-driven base class for data transformation facets.

| Attribute | Type |
|-----------|------|
| `NUMERIC_COERCE` | `Dict[str, str]` |
| `SPARK_CASTS` | `Dict[str, str]` |
| `FINAL_COLUMNS` | `Optional[List[Tuple[str, str]]]` |
| `PROVIDER_ID` | `Optional[str]` |
| `ENDPOINT_ID` | `Optional[str]` |

| Method | Description |
|--------|-------------|
| `get_coerce_rules() -> Dict[str, str]` | Get source field -> type coercion rules from markdown schema. |
| `get_spark_casts() -> Dict[str, str]` | Get output_name -> type casts from markdown schema. |
| `get_final_columns() -> List[Tuple[str, str]]` | Get final columns list from markdown schema. |
| `get_field_mappings() -> Dict[str, str]` | Get source -> output field name mappings from markdown schema. |
| `get_computed_fields() -> List[Dict[str, Any]]` | Get computed field definitions from markdown schema. |
| `get_facet_config() -> Dict[str, Any]` | Get facet configuration (response_arrays, fixed_fields, etc.). |
| `normalize(raw_batches: List[List[dict]]) -> DataFrame` | Main normalization pipeline. |
| `postprocess(df: DataFrame) -> DataFrame` | Override in child class to apply custom transformations. |
| `validate(df: DataFrame) -> DataFrame` | Override in child class to validate output DataFrame. |
| `calls()` | Override in child class to generate API call specifications. |

### ApiKeyPool

**File**: `src/de_funk/pipelines/base/key_pool.py:4`

**Purpose**: Manages a rotating pool of API keys for providers that support multiple keys. Uses a deque to cycle through keys, with cooldown tracking to avoid re-using an exhausted key too soon.

| Method | Description |
|--------|-------------|
| `size()` | Return the number of keys in the pool. |
| `next_key()` | Return the next available key, rotating the pool. Skips keys within cooldown. |
| `mark_exhausted(key)` | Mark a key as exhausted (rate-limited). Moves it to the back. |

### SparkNormalizer

**File**: `src/de_funk/pipelines/base/normalizer.py:44`

**Purpose**: Standard Spark-based data normalizer for all providers.

| Method | Description |
|--------|-------------|
| `normalize(records: List[Dict], field_mappings: Optional[Dict[str, str]], type_coercions: Optional[Dict[str, str]], date_columns: Optional[List[str]], timestamp_columns: Optional[List[str]], computed_columns: Optional[Dict[str, str]], add_metadata: bool, final_columns: Optional[List[str]], metadata_columns: Optional[Dict[str, Any]]) -> DataFrame` | Normalize raw records to a Spark DataFrame. |
| `normalize_with_schema(records: List[Dict], schema_fields: List[Dict[str, Any]], add_metadata: bool) -> DataFrame` | Normalize using endpoint schema field definitions. |

### Endpoint

**File**: `src/de_funk/pipelines/base/registry.py:5`

**Purpose**: Data class representing a single API endpoint definition, with URL template, HTTP method, required parameters, default query parameters, and response key for data extraction.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `base` | `str` |
| `method` | `str` |
| `path_template` | `str` |
| `required_params` | `list` |
| `default_query` | `dict` |
| `response_key` | `str` |

### BaseRegistry

**File**: `src/de_funk/pipelines/base/registry.py:14`

**Purpose**: Registry of API endpoint definitions. Subclasses populate endpoint metadata (URL templates, query defaults). The `render()` method substitutes parameters into the endpoint template to produce a callable URL.

| Method | Description |
|--------|-------------|
| `render(ep_name)` | - Accepts required params either at the top-level or inside params['query']. |

### CircuitState (Enum)

**File**: `src/de_funk/pipelines/base/circuit_breaker.py:29`

**Purpose**: Circuit breaker states.

| Attribute | Type |
|-----------|------|
| `CLOSED` | `—` |
| `OPEN` | `—` |
| `HALF_OPEN` | `—` |

### CircuitBreakerConfig

**File**: `src/de_funk/pipelines/base/circuit_breaker.py:37`

**Purpose**: Configuration for a circuit breaker.

| Attribute | Type |
|-----------|------|
| `failure_threshold` | `int` |
| `success_threshold` | `int` |
| `timeout_seconds` | `float` |
| `half_open_max_calls` | `int` |
| `name` | `str` |

### CircuitStats

**File**: `src/de_funk/pipelines/base/circuit_breaker.py:47`

**Purpose**: Statistics for a circuit breaker.

| Attribute | Type |
|-----------|------|
| `total_calls` | `int` |
| `successful_calls` | `int` |
| `failed_calls` | `int` |
| `rejected_calls` | `int` |
| `state_changes` | `int` |
| `last_failure_time` | `Optional[float]` |
| `last_success_time` | `Optional[float]` |
| `consecutive_failures` | `int` |
| `consecutive_successes` | `int` |

### CircuitBreaker

**File**: `src/de_funk/pipelines/base/circuit_breaker.py:60`

**Purpose**: Circuit breaker implementation.

| Method | Description |
|--------|-------------|
| `state() -> CircuitState` | Get current circuit state. |
| `stats() -> CircuitStats` | Get circuit statistics. |
| `allow_request() -> bool` | Check if a request should be allowed. |
| `record_success() -> None` | Record a successful request. |
| `record_failure(error: Exception) -> None` | Record a failed request. |
| `reset() -> None` | Reset circuit to closed state. |
| `protect(func: Callable) -> Callable` | Decorator to protect a function with circuit breaker. |
| `call(fn: Callable) -> Any` | Execute function with circuit breaker protection. |
| `get_status() -> Dict[str, Any]` | Get detailed status of the circuit breaker. |

### CircuitOpenError (Exception)

**File**: `src/de_funk/pipelines/base/circuit_breaker.py:270`

**Purpose**: Raised when circuit is open and request is rejected.

### CircuitBreakerManager

**File**: `src/de_funk/pipelines/base/circuit_breaker.py:275`

**Purpose**: Manages circuit breakers for multiple endpoints/providers.

| Attribute | Type |
|-----------|------|
| `_instance` | `Optional['CircuitBreakerManager']` |
| `_lock` | `threading.Lock` |
| `DEFAULT_CONFIGS` | `Dict[str, CircuitBreakerConfig]` |

| Method | Description |
|--------|-------------|
| `get_breaker(name: str) -> CircuitBreaker` | Get or create a circuit breaker. |
| `configure(name: str, failure_threshold: int, success_threshold: int, timeout_seconds: float) -> CircuitBreaker` | Configure a circuit breaker. |
| `get_all_status() -> Dict[str, Dict]` | Get status of all circuit breakers. |
| `reset_all() -> None` | Reset all circuit breakers. |

### RateLimitConfig

**File**: `src/de_funk/pipelines/base/rate_limiter.py:21`

**Purpose**: Configuration for a rate limiter.

| Attribute | Type |
|-----------|------|
| `calls_per_minute` | `float` |
| `burst_size` | `int` |
| `name` | `str` |

| Method | Description |
|--------|-------------|
| `calls_per_second() -> float` | Computed property: `calls_per_minute / 60.0`. |
| `refill_rate() -> float` | Tokens added per second. |

### TokenBucket

**File**: `src/de_funk/pipelines/base/rate_limiter.py:78`

**Purpose**: Token bucket implementation for rate limiting.

| Attribute | Type |
|-----------|------|
| `config` | `RateLimitConfig` |
| `tokens` | `float` |
| `last_refill` | `float` |
| `lock` | `threading.Lock` |
| `total_requests` | `int` |
| `total_waits` | `int` |
| `total_wait_time` | `float` |

| Method | Description |
|--------|-------------|
| `acquire(tokens: int, blocking: bool, timeout: float) -> bool` | Acquire tokens from the bucket. |
| `wait() -> None` | Convenience method: wait and acquire 1 token. |
| `try_acquire(tokens: int) -> bool` | Try to acquire tokens without waiting. |
| `available_tokens() -> float` | Get current available tokens (for monitoring). |
| `get_stats() -> Dict` | Get statistics about this rate limiter. |

### RateLimiterManager

**File**: `src/de_funk/pipelines/base/rate_limiter.py:190`

**Purpose**: Manages rate limiters for multiple providers.

| Attribute | Type |
|-----------|------|
| `_instance` | `Optional['RateLimiterManager']` |
| `_lock` | `threading.Lock` |

| Method | Description |
|--------|-------------|
| `get_limiter(provider: str) -> TokenBucket` | Get or create a rate limiter for a provider. |
| `configure_provider(provider: str, calls_per_minute: float, burst_size: int) -> TokenBucket` | Configure or reconfigure a provider's rate limiter. |
| `wait(provider: str) -> None` | Wait for rate limit on a provider. |
| `try_acquire(provider: str) -> bool` | Try to acquire without waiting. |
| `get_all_stats() -> Dict[str, Dict]` | Get statistics for all rate limiters. |
| `reset() -> None` | Reset all rate limiters (useful for testing). |

### PhaseProgress

**File**: `src/de_funk/pipelines/base/progress_tracker.py:50`

**Purpose**: Progress tracking for a single phase (e.g., 'prices', 'earnings').

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `total` | `int` |
| `completed` | `int` |
| `errors` | `int` |
| `start_time` | `Optional[float]` |
| `end_time` | `Optional[float]` |
| `current_ticker` | `str` |

| Method | Description |
|--------|-------------|
| `percent() -> float` | Percentage complete (0-100). |
| `elapsed_seconds() -> float` | Seconds elapsed since phase started. |
| `eta_seconds() -> Optional[float]` | Estimated seconds remaining for this phase. |
| `is_complete() -> bool` | Whether this phase is complete. |

### PipelineStats

**File**: `src/de_funk/pipelines/base/progress_tracker.py:89`

**Purpose**: Overall pipeline statistics.

| Attribute | Type |
|-----------|------|
| `total_tickers` | `int` |
| `completed_tickers` | `int` |
| `total_api_calls` | `int` |
| `successful_calls` | `int` |
| `failed_calls` | `int` |
| `start_time` | `Optional[float]` |
| `end_time` | `Optional[float]` |

| Method | Description |
|--------|-------------|
| `elapsed_seconds() -> float` | Total elapsed time. |
| `format_elapsed() -> str` | Format elapsed time as human-readable string. |

### ProgressBar

**File**: `src/de_funk/pipelines/base/progress_tracker.py:132`

**Purpose**: Renders a text-based progress bar.

| Method | Description |
|--------|-------------|
| `render(percent: float, current: int, total: int) -> str` | Render progress bar string. |

### PipelineProgressTracker

**File**: `src/de_funk/pipelines/base/progress_tracker.py:157`

**Purpose**: Unified progress tracker for pipeline operations.

| Method | Description |
|--------|-------------|
| `set_phase_total(phase: str, total: int) -> None` | Set the total count for a specific phase. |
| `start_phase(phase: str, total: int) -> None` | Mark a phase as started. |
| `update_phase(phase: str, ticker: str, success: bool, error: Optional[str], force_display: bool) -> None` | Update progress for a specific phase. |
| `complete_phase(phase: str) -> None` | Mark a phase as complete and print summary. |
| `complete_ticker(ticker: str) -> None` | Mark a ticker as fully complete (all phases done for this ticker). |
| `get_overall_progress() -> float` | Get overall progress percentage (0-100). |
| `print_overall_status() -> None` | Print overall pipeline status (called periodically or on demand). |
| `finish() -> Dict` | Finalize tracking and print summary. |

### TickerProgressCallback

**File**: `src/de_funk/pipelines/base/progress_tracker.py:460`

**Purpose**: Progress callback adapter for existing _fetch_calls interface.

### StepProgressTracker

**File**: `src/de_funk/pipelines/base/progress_tracker.py:489`

**Purpose**: Simple progress tracker for multi-step operations (build, forecast, etc).

| Method | Description |
|--------|-------------|
| `update(step: int, item: str)` | Update progress. |
| `step_complete(message: str)` | Mark current step as complete and print completion message. |
| `finish(success: bool)` | Finish tracking and print summary. |

### BatchProgressTracker

**File**: `src/de_funk/pipelines/base/progress_tracker.py:600`

**Purpose**: Progress tracker with batch-aware display for per-ticker ingestion.

| Attribute | Type |
|-----------|------|
| `DATA_TYPE_SHORT_NAMES` | `—` |

| Method | Description |
|--------|-------------|
| `start_batch(batch_num: int, total_batches: int, tickers: List[str])` | Start a new batch. |
| `update(ticker: str, data_type: str, success: bool, error: Optional[str])` | Update progress for a ticker's data type. |
| `complete_ticker(ticker: str)` | Mark a ticker as complete. |
| `complete_batch(write_time_ms: float)` | Mark current batch as complete. |
| `finish() -> Dict` | Print final summary and return statistics. |

### StepMetric

**File**: `src/de_funk/pipelines/base/metrics.py:42`

**Purpose**: Metrics for a single step/operation.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `count` | `int` |
| `total_ms` | `float` |
| `min_ms` | `float` |
| `max_ms` | `float` |
| `errors` | `int` |

| Method | Description |
|--------|-------------|
| `avg_ms() -> float` | Average time in milliseconds. |
| `total_seconds() -> float` | Total time in seconds. |
| `record(elapsed_ms: float, error: bool)` | Record a single measurement. |

### TimingContext

**File**: `src/de_funk/pipelines/base/metrics.py:71`

**Purpose**: Context manager for timing operations.

### MetricsCollector

**File**: `src/de_funk/pipelines/base/metrics.py:91`

**Purpose**: Collects performance metrics during pipeline execution.

| Method | Description |
|--------|-------------|
| `time(step_name: str) -> TimingContext` | Context manager for timing a step. |
| `record(step_name: str, elapsed_ms: float, error: bool)` | Record a timing measurement. |
| `finish()` | Mark metrics collection as complete. |
| `elapsed_seconds() -> float` | Total elapsed time in seconds. |
| `summary() -> Dict` | Generate summary dictionary. |
| `print_report()` | Print formatted metrics report to console. |
| `get_slowest_steps(n: int) -> list` | Get the N slowest steps by total time. |

### BronzeSink

**File**: `src/de_funk/pipelines/ingestors/bronze_sink.py:18`

**Purpose**: Writes DataFrames to Bronze layer as Delta Lake tables.

| Method | Description |
|--------|-------------|
| `exists(table: str, partitions: Optional[Dict]) -> bool` | Check if a Bronze table (and optional partition) exists on disk. |
| `write_if_missing(table: str, partitions: Optional[Dict], df) -> bool` | Write only if the table or partition does not already exist. Returns True if written. |
| `append_immutable(df, table: str, key_columns: List[str], partitions: Optional[List[str]], date_column: str) -> str` | Append immutable time-series data efficiently using INSERT-only semantics. |
| `upsert(df, table: str, key_columns: List[str], partitions: Optional[List[str]], update_existing: bool) -> str` | Upsert DataFrame into bronze table using Read-Merge-Overwrite strategy. |
| `smart_write(df, table: str) -> str` | Universal write method that picks strategy based on storage.json config. |
| `write(df, table: str, partitions: Optional[List[str]], mode: str) -> str` | Write DataFrame to bronze table as Delta Lake format. |
| `overwrite(df, table: str, partitions: Optional[List[str]]) -> str` | Simple overwrite for tables not in storage.json. |
| `append(df, table: str, partitions: Optional[List[str]]) -> str` | Append data to existing Delta table. |
| `streaming_writer(table: str, df_factory: callable, batch_size: int, partitions: Optional[List[str]]) -> 'StreamingBronzeWriter'` | Create a streaming writer for incremental batch writes. |
| `rebuild_from_raw(provider: str, endpoint: str) -> str` | Rebuild a Bronze table from Raw files. |

### StreamingBronzeWriter

**File**: `src/de_funk/pipelines/ingestors/bronze_sink.py:622`

**Purpose**: Context manager for streaming batch writes to Bronze layer.

| Method | Description |
|--------|-------------|
| `add_records(records: List[Dict]) -> None` | Add records to buffer, auto-flushing if batch_size reached. |
| `add_batch(batch: List[Dict]) -> None` | Alias for add_records for clarity. |
| `flush() -> None` | Write buffered records to Delta and clear buffer. |
| `total_records() -> int` | Total records written (not including current buffer). |
| `buffered_records() -> int` | Records currently in buffer. |
| `batches_written() -> int` | Number of batches flushed to storage. |

### RawSink

**File**: `src/de_funk/pipelines/ingestors/raw_sink.py:22`

**Purpose**: Writes raw API responses to the raw storage tier.

| Method | Description |
|--------|-------------|
| `write(data: Any, provider: str, endpoint: str, partition: str) -> Path` | Write raw data to storage. |
| `exists(provider: str, endpoint: str, partition: str) -> bool` | Check if raw data exists for a provider/endpoint/partition. |
| `read(provider: str, endpoint: str, partition: str) -> Any` | Read raw data for a provider/endpoint/partition. |

### AlphaVantageProvider (BaseProvider)

**File**: `src/de_funk/pipelines/providers/alpha_vantage/alpha_vantage_provider.py:62`

**Purpose**: Alpha Vantage implementation of BaseProvider.

| Attribute | Type |
|-----------|------|
| `PROVIDER_NAME` | `—` |

| Method | Description |
|--------|-------------|
| `enable_raw_save(storage_path: Path, enabled: bool) -> None` | Enable/disable saving raw API responses (JSON files) before transformation. |
| `has_raw_data(ticker: str, endpoint_id: str) -> bool` | Check if raw data exists for a ticker/endpoint combination. |
| `set_tickers(tickers: List[str]) -> None` | Set tickers to process for ingestion. |
| `list_work_items() -> List[str]` | List available data types for ingestion. |
| `populate_raw_cache(work_item: str, force_api: bool) -> Dict[str, int]` | Populate raw JSON cache by fetching from API (no transformation). |
| `fetch(work_item: str, max_records: Optional[int], force_api: bool) -> Generator[List[Dict], None, None]` | Fetch data for a data type, yielding batches of records. |
| `normalize(records: List[Dict], work_item: str) -> DataFrame` | Normalize raw records to a Spark DataFrame. |
| `get_table_name(work_item: str) -> str` | Get Bronze table name from endpoint config. |
| `get_partitions(work_item: str) -> Optional[List[str]]` | Get partition columns from endpoint config. |
| `get_key_columns(work_item: str) -> List[str]` | Get key columns from endpoint config. |
| `get_raw_path(work_item: str) -> Optional[str]` | Get path to raw JSON files for bulk reading. |
| `read_raw_as_df(work_item: str, raw_path: str) -> Optional[DataFrame]` | Read raw JSON files with Spark and return normalized DataFrame. |
| `discover_tickers(state: str) -> tuple` | Discover tickers using LISTING_STATUS endpoint. |
| `get_tickers_by_market_cap(max_tickers: int, min_market_cap: float, storage_cfg: Dict) -> List[str]` | Get tickers sorted by market cap from existing reference data. |
| `seed_tickers(state: str, filter_us_exchanges: bool) -> Any` | Seed tickers from LISTING_STATUS endpoint to Bronze layer. |

### AlphaVantageRegistry (BaseRegistry)

**File**: `src/de_funk/pipelines/providers/alpha_vantage/alpha_vantage_registry.py:16`

**Purpose**: Registry for Alpha Vantage API endpoints.

| Method | Description |
|--------|-------------|
| `render(ep_name)` | Render an endpoint with given parameters. |

### ProviderInfo

**File**: `src/de_funk/pipelines/providers/registry.py:43`

**Purpose**: Metadata about a data provider.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `description` | `str` |
| `version` | `str` |
| `models` | `List[str]` |
| `bronze_tables` | `List[str]` |
| `config_key` | `str` |
| `module_path` | `str` |
| `class_name` | `str` |
| `tags` | `List[str]` |
| `enabled` | `bool` |

| Method | Description |
|--------|-------------|
| `to_dict() -> Dict[str, Any]` | Serialize to a plain dict via `dataclasses.asdict()`. |

### ProviderRegistry

**File**: `src/de_funk/pipelines/providers/registry.py:83`

**Purpose**: Registry for data providers with auto-discovery.

| Attribute | Type |
|-----------|------|
| `_providers` | `Dict[str, ProviderInfo]` |
| `_discovered` | `bool` |
| `_providers_dir` | `Path` |

| Method | Description |
|--------|-------------|
| `discover(force: bool) -> None` | Discover available providers. |
| `list_available() -> List[str]` | List all available provider names. |
| `get_info(provider_name: str) -> Optional[ProviderInfo]` | Get metadata for a specific provider. |
| `get_ingestor(provider_name: str, spark: Any, storage_cfg: Dict, api_config: Dict) -> Any` | Get an instantiated ingestor for a provider. |
| `get_all_info() -> Dict[str, ProviderInfo]` | Get metadata for all providers. |
| `get_providers_for_model(model_name: str) -> List[str]` | Get providers that feed data to a specific model. |
| `get_providers_by_tag(tag: str) -> List[str]` | Get providers with a specific tag. |
| `register(info: ProviderInfo) -> None` | Manually register a provider. |
| `reset() -> None` | Reset the registry (for testing). |

## How to Use

### Common Operations

**Running ingestion for a provider:**

```python
from de_funk.pipelines.base.ingestor_engine import IngestorEngine
from de_funk.pipelines.providers.alpha_vantage.alpha_vantage_provider import AlphaVantageProvider
from pathlib import Path

# Create provider from markdown config
provider = AlphaVantageProvider(
    provider_id="alpha_vantage",
    spark=spark_session,
    docs_path=Path("data_sources"),
)
provider.set_tickers(["AAPL", "MSFT", "GOOGL"])

# Create engine and run
engine = IngestorEngine.from_session(session, provider)
results = engine.run(work_items=["prices", "reference"])
results.print_summary()
# INGESTION SUMMARY
# Work items: 2/2 completed
# Records: 15,420
# Time: 34.2s
# Throughput: 451 records/sec
```

**Using the rate limiter directly:**

```python
from de_funk.pipelines.base.rate_limiter import RateLimiterManager

manager = RateLimiterManager()
manager.configure_provider("alpha_vantage", calls_per_minute=75, burst_size=10)

# Before each API call
manager.wait("alpha_vantage")  # blocks until a token is available
response = make_api_call()
```

**Using the circuit breaker:**

```python
from de_funk.pipelines.base.circuit_breaker import CircuitBreakerManager

manager = CircuitBreakerManager()
breaker = manager.get_breaker("alpha_vantage")

if breaker.allow_request():
    try:
        result = api_call()
        breaker.record_success()
    except Exception as e:
        breaker.record_failure(e)
else:
    # Circuit is open -- fail fast
    logger.warning("Circuit open, skipping API call")
```

**Writing to Bronze with BronzeSink:**

```python
from de_funk.pipelines.ingestors.bronze_sink import BronzeSink

sink = BronzeSink(spark=spark, storage_cfg=storage_cfg)

# Append immutable time-series data
sink.append_immutable(
    df=prices_df,
    table="alpha_vantage.daily_prices",
    key_columns=["ticker", "trade_date"],
    date_column="trade_date",
)

# Upsert reference data
sink.upsert(
    df=reference_df,
    table="alpha_vantage.listing_status",
    key_columns=["ticker"],
)
```

### Integration Examples

**Full ingestion pipeline with checkpointing:**

```python
from de_funk.orchestration.checkpoint import CheckpointManager

checkpoint_mgr = CheckpointManager()
checkpoint = checkpoint_mgr.find_resumable_checkpoint("alpha_vantage_ingestion")

if checkpoint:
    tickers = checkpoint_mgr.get_pending_tickers()
    logger.info(f"Resuming with {len(tickers)} pending tickers")
else:
    tickers = provider.discover_tickers(state="active")
    checkpoint = checkpoint_mgr.create_checkpoint("alpha_vantage_ingestion", tickers)

for ticker in tickers:
    checkpoint_mgr.mark_ticker_started(ticker)
    try:
        # ... ingest ticker data ...
        checkpoint_mgr.mark_ticker_completed(ticker, endpoints={"prices": "ok"})
    except Exception as e:
        checkpoint_mgr.mark_ticker_failed(ticker, str(e))

checkpoint_mgr.mark_pipeline_completed()
```

**Provider registry for dynamic provider discovery:**

```python
from de_funk.pipelines.providers.registry import ProviderRegistry

registry = ProviderRegistry(providers_dir=Path("data_sources"))
registry.discover()

for name in registry.list_available():
    info = registry.get_info(name)
    print(f"{name}: {info.description} (tables: {info.bronze_tables})")
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `HTTPError 429 Too Many Requests` | Rate limit exceeded for the provider | Check `PROVIDER_RATE_LIMITS` config. For Alpha Vantage free tier, limit is 5/min. Consider upgrading API key tier or reducing `calls_per_minute`. |
| `CircuitOpenError: Circuit 'xxx' is OPEN` | Circuit breaker tripped after repeated failures | Check the underlying API status. Call `CircuitBreakerManager().get_breaker("xxx").reset()` to manually close the circuit. |
| `No API key found in environment` | The environment variable for the provider's API key is not set | Set the env var specified in `provider.md` frontmatter (e.g. `export ALPHA_VANTAGE_API_KEY=xxx`) |
| Ingestion produces 0 records for an endpoint | API returned empty data, or the `response_key` in markdown config is wrong | Check the raw API response manually. Verify the `response_key` in the endpoint markdown matches the actual JSON structure. |
| `DeltaTableAlreadyExistsException` during write | Attempting to overwrite a Delta table with `mode=error` | Use `mode=overwrite` or switch to `upsert()`/`append_immutable()` |
| Ingestion hangs / very slow | Rate limiter cooldown is too aggressive, or API is returning slow responses | Check `RateLimiterManager().get_all_stats()` for wait times. Check network connectivity. |
| `SparkException` during normalize | Raw data has unexpected types or NULL values that break Spark schema inference | Check the endpoint's `schema:` section in markdown for correct type coercions. Add `{coerce: type}` rules. |
| Progress tracker shows ETA as "unknown" | Phase not started or total count is 0 | Call `start_phase()` before `update_phase()` |

### Debug Checklist

- [ ] Verify API key is set: `echo $ALPHA_VANTAGE_API_KEY` (or the provider's env var)
- [ ] Test raw API call manually: `curl "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=AAPL&apikey=$ALPHA_VANTAGE_API_KEY"`
- [ ] Check rate limiter stats: `RateLimiterManager().get_all_stats()` for total_waits and total_wait_time
- [ ] Check circuit breaker status: `CircuitBreakerManager().get_all_status()` for any OPEN circuits
- [ ] Enable raw save mode to inspect API responses: `provider.enable_raw_save(Path("storage/raw"), True)`
- [ ] Check Bronze table exists after ingestion: `ls storage/bronze/<provider>/<table>/`
- [ ] Verify endpoint markdown config: check `data_sources/<provider>/endpoints/<endpoint>.md` for correct `resource_id`, `schema`, `write_strategy`
- [ ] For Socrata providers, verify resource ID with: `curl "https://data.cityofchicago.org/resource/<id>.json?$limit=1"`

### Common Pitfalls

1. **Forgetting to call `provider.set_tickers()` for Alpha Vantage**: Unlike Socrata providers (which discover work items from endpoint configs), Alpha Vantage needs explicit ticker lists. Without `set_tickers()`, `list_work_items()` returns data types but `fetch()` has no tickers to iterate over.

2. **Mixing up work_item semantics**: For Alpha Vantage, a work_item is a data type ("prices", "reference"). For Socrata, it is an endpoint ID ("crimes", "budget"). The `IngestorEngine.run()` method is provider-agnostic but the work_items you pass must match the provider's convention.

3. **Rate limiter is per-process singleton**: `RateLimiterManager` and `CircuitBreakerManager` use class-level singletons. Running multiple ingestion processes against the same API will not share rate limit state. Use a single process or external rate limiting for multi-process scenarios.

4. **BronzeSink write strategy must match data characteristics**: Using `overwrite` on time-series data loses historical records. Using `append_immutable` on reference data creates duplicates. The endpoint markdown's `write_strategy` field should match the data type: `append_immutable` for prices, `upsert` for reference, `overwrite` for snapshots.

5. **ApiKeyPool cooldown vs rate limiter**: The `ApiKeyPool` has its own cooldown per key (default 60s), separate from the `TokenBucket` rate limiter. If you have multiple API keys, the pool rotates between them, but the rate limiter still enforces the overall calls-per-minute budget.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/pipelines/base/ingestor_engine.py` | Unified Ingestor Engine with Async Writes. | `IngestionResults`, `WriteTask`, `IngestorEngine` |
| `src/de_funk/pipelines/base/provider.py` | Base Provider Interface. | `DataType`, `FetchResult`, `WorkItemResult`, `BaseProvider` |
| `src/de_funk/pipelines/base/socrata_client.py` | Socrata (SODA) API Client. | `SocrataClient` |
| `src/de_funk/pipelines/base/socrata_provider.py` | Socrata Base Provider. | `SocrataBaseProvider` |
| `src/de_funk/pipelines/base/http_client.py` | HTTP client for API requests with rate limiting and retry logic. | `HttpClient` |
| `src/de_funk/pipelines/base/facet.py` | Base Facet class for data transformation pipelines. | `Facet` |
| `src/de_funk/pipelines/base/key_pool.py` | — | `ApiKeyPool` |
| `src/de_funk/pipelines/base/normalizer.py` | SparkNormalizer - Standard data normalization utilities for all providers. | `SparkNormalizer` |
| `src/de_funk/pipelines/base/registry.py` | — | `Endpoint`, `BaseRegistry` |
| `src/de_funk/pipelines/base/circuit_breaker.py` | Circuit Breaker Pattern - Failure isolation for API calls. | `CircuitState`, `CircuitBreakerConfig`, `CircuitStats`, `CircuitBreaker`, `CircuitOpenError`, `CircuitBreakerManager` |
| `src/de_funk/pipelines/base/rate_limiter.py` | Token Bucket Rate Limiter - Per-provider rate limiting for API calls. | `RateLimitConfig`, `TokenBucket`, `RateLimiterManager` |
| `src/de_funk/pipelines/base/progress_tracker.py` | Progress Tracker for Pipeline Operations. | `PhaseProgress`, `PipelineStats`, `ProgressBar`, `PipelineProgressTracker`, `TickerProgressCallback`, `StepProgressTracker`, `BatchProgressTracker` |
| `src/de_funk/pipelines/base/metrics.py` | Performance Metrics Collector for Pipeline Operations. | `StepMetric`, `TimingContext`, `MetricsCollector` |
| `src/de_funk/pipelines/ingestors/bronze_sink.py` | Bronze Sink - Writes data to Bronze layer using Delta Lake format. | `BronzeSink`, `StreamingBronzeWriter` |
| `src/de_funk/pipelines/ingestors/raw_sink.py` | RawSink — writes raw API responses to the Raw storage tier. | `RawSink` |
| `src/de_funk/pipelines/providers/alpha_vantage/alpha_vantage_provider.py` | Alpha Vantage Provider Implementation. | `AlphaVantageProvider` |
| `src/de_funk/pipelines/providers/alpha_vantage/alpha_vantage_registry.py` | Alpha Vantage Registry | `AlphaVantageRegistry` |
| `src/de_funk/pipelines/providers/registry.py` | Provider Registry - Dynamic provider discovery and management. | `ProviderInfo`, `ProviderRegistry` |

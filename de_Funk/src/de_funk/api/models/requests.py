"""
Pydantic request and response models for the de_funk API.

These types mirror the de_funk block data contract — every field in a
de_funk YAML block maps to a field here.
"""
from __future__ import annotations

from typing import Any, Optional, Union
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------

class FilterSpec(BaseModel):
    """A single filter applied to a field."""
    model_config = {"populate_by_name": True}
    field: str
    operator: str = Field("in", alias="op")  # in | eq | gte | lte | between | like
    value: Union[list, str, int, float, dict]


class PageFilters(BaseModel):
    """Page-level filter inheritance control."""
    ignore: list[str] = Field(default_factory=list)
    # ["*"] = ignore all; [] = inherit all; ["sector"] = skip specific ids


class SortSpec(BaseModel):
    """Sort directive — applied at query level."""
    by: Optional[str] = None        # measure key or domain.field
    order: str = "asc"              # asc | desc
    values: Optional[list[str]] = None  # prescriptive ordering


class BucketSpec(BaseModel):
    """Binning config for a dimension."""
    size: Optional[float] = None    # equal-width bins
    edges: Optional[list[float]] = None  # custom break points
    count: Optional[int] = None     # equal-frequency (quantile) bins


class WindowSpec(BaseModel):
    """Row-over-row window calculation."""
    key: str
    source: str                     # source measure key
    type: str                       # pct_change | diff | running_sum | rank
    label: Optional[str] = None


class TotalsSpec(BaseModel):
    """Backend-computed summary rows/cols."""
    rows: bool = False
    cols: bool = False


class SortConfig(BaseModel):
    """Sort config for pivot rows and cols."""
    rows: Optional[SortSpec] = None
    cols: Optional[SortSpec] = None


class MeasureTuple(BaseModel):
    """
    Measure definition as a tuple.

    Mirrors the YAML positional syntax: [key, field_or_fn, aggregation, format, label]
    """
    key: str
    field: Union[str, dict]         # domain.field or {fn: ..., ...} computation
    aggregation: Optional[str] = None
    format: Optional[str] = None
    label: Optional[str] = None


class ColumnTuple(BaseModel):
    """Column definition for table.data."""
    key: str
    field: str                      # domain.field
    aggregation: Optional[str] = None
    format: Optional[str] = None
    label: Optional[str] = None


# ---------------------------------------------------------------------------
# Request models — one per block type
# ---------------------------------------------------------------------------

class GraphicalQueryRequest(BaseModel):
    """Request for plotly.line, plotly.bar, plotly.scatter, plotly.area, plotly.pie, plotly.heatmap."""
    type: str                       # catalog key
    x: Optional[str] = None        # domain.field
    y: Optional[Union[str, list[str]]] = None
    group_by: Optional[str] = None
    size: Optional[str] = None      # scatter bubble
    color: Optional[str] = None     # scatter color dimension
    labels: Optional[str] = None    # pie labels
    values: Optional[str] = None    # pie values
    z: Optional[str] = None         # heatmap z
    aggregation: Optional[str] = None
    sort: Optional[SortSpec] = None
    limit: Optional[int] = None
    filters: list[FilterSpec] = Field(default_factory=list)
    page_filters: Optional[PageFilters] = None
    models: list[str] = Field(default_factory=list)


class BoxQueryRequest(BaseModel):
    """Request for plotly.box (OHLCV or generic)."""
    type: str = "plotly.box"
    category: str
    open: Optional[str] = None
    high: Optional[str] = None
    low: Optional[str] = None
    close: Optional[str] = None
    y: Optional[str] = None         # generic box mode
    group_by: Optional[str] = None  # split into separate traces per group
    sort: Optional[SortSpec] = None
    filters: list[FilterSpec] = Field(default_factory=list)
    page_filters: Optional[PageFilters] = None
    models: list[str] = Field(default_factory=list)


class TableDataQueryRequest(BaseModel):
    """Request for table.data."""
    type: str = "table.data"
    columns: list[ColumnTuple]
    sort_by: Optional[str] = None
    sort_order: str = "asc"
    filters: list[FilterSpec] = Field(default_factory=list)
    page_filters: Optional[PageFilters] = None
    models: list[str] = Field(default_factory=list)


class PivotQueryRequest(BaseModel):
    """Request for table.pivot — always renders via Great Tables."""
    type: str = "table.pivot"
    rows: Union[str, list[str]]
    cols: Optional[Union[str, list[str]]] = None
    layout: str = "by_measure"      # by_measure | by_column | by_dimension
    measures: list[MeasureTuple]
    buckets: Optional[dict[str, BucketSpec]] = None
    windows: Optional[list[WindowSpec]] = None
    totals: Optional[TotalsSpec] = None
    sort: Optional[SortConfig] = None
    filters: list[FilterSpec] = Field(default_factory=list)
    page_filters: Optional[PageFilters] = None
    models: list[str] = Field(default_factory=list)

    @property
    def row_fields(self) -> list[str]:
        """Normalize rows to a list."""
        return [self.rows] if isinstance(self.rows, str) else self.rows

    @property
    def col_fields(self) -> list[str]:
        """Normalize cols to a list (empty if None)."""
        if self.cols is None:
            return []
        return [self.cols] if isinstance(self.cols, str) else self.cols


class MetricQueryRequest(BaseModel):
    """Request for cards.metric."""
    type: str = "cards.metric"
    metrics: list[MeasureTuple]
    filters: list[FilterSpec] = Field(default_factory=list)
    page_filters: Optional[PageFilters] = None
    models: list[str] = Field(default_factory=list)


# Union type for the generic /api/query endpoint
QueryRequest = Union[
    GraphicalQueryRequest,
    BoxQueryRequest,
    TableDataQueryRequest,
    PivotQueryRequest,
    MetricQueryRequest,
]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SeriesData(BaseModel):
    """One series in a graphical response."""
    name: str
    x: list = Field(default_factory=list)
    y: list = Field(default_factory=list)
    size: Optional[list] = None


class GraphicalResponse(BaseModel):
    series: list[SeriesData]
    truncated: bool = False     # True when MB cap was hit
    formatting: Optional[dict[str, Any]] = None  # pass-through for frontend


class TableColumn(BaseModel):
    key: str
    label: str
    format: Optional[str] = None
    group: Optional[str] = None     # spanner group label (for Great Tables tab_spanner)


class TableResponse(BaseModel):
    columns: list[TableColumn]
    rows: list[list[Any]]
    truncated: bool = False     # True when MB cap was hit
    formatting: Optional[dict[str, Any]] = None  # pass-through for frontend


class ExpandableData(BaseModel):
    """Overflow detail rows for hierarchical expand/collapse pivots.

    When GROUPING SETS produces more rows than the HTML render cap,
    the initial HTML shows subtotals only. Detail rows are sent here,
    keyed by their parent subtotal value, so the plugin can expand
    them on click without re-querying.
    """
    columns: list[dict[str, Any]]           # [{key, label, format?}]
    children: dict[str, list[list[Any]]]    # parent_key → child detail rows
    total_rows: int                         # total row count before split


class GreatTablesResponse(BaseModel):
    html: str
    expandable: Optional[ExpandableData] = None


class MetricValue(BaseModel):
    key: str
    label: str
    value: Any
    format: Optional[str] = None


class MetricResponse(BaseModel):
    metrics: list[MetricValue]


class DimensionValuesResponse(BaseModel):
    field: str
    values: list[Any]


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0"

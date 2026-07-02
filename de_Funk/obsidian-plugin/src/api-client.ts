/**
 * HTTP client for the de_funk backend API.
 * Handles auth headers, error normalization, and response caching.
 */
import type { DeFunkSettings } from "./settings";
import type { ApiResponse, DimensionValuesResponse } from "./contract";

interface CacheEntry {
  value: unknown;
  expiresAt: number;
}

export class ApiClient {
  private cache = new Map<string, CacheEntry>();
  private inflight = new Map<string, Promise<unknown>>();

  constructor(private settings: DeFunkSettings) {}

  private get headers(): HeadersInit {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.settings.apiKey) {
      h["X-API-Key"] = this.settings.apiKey;
    }
    return h;
  }

  private cacheKey(method: string, path: string, body?: unknown): string {
    return `${method}:${path}:${JSON.stringify(body ?? "")}`;
  }

  private fromCache(key: string): unknown | null {
    const entry = this.cache.get(key);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }
    return entry.value;
  }

  private toCache(key: string, value: unknown): void {
    const ttl = this.settings.cacheTtlSeconds * 1000;
    if (ttl <= 0) return;
    this.cache.set(key, { value, expiresAt: Date.now() + ttl });
  }

  async get<T>(path: string): Promise<T> {
    const key = this.cacheKey("GET", path);
    const cached = this.fromCache(key);
    if (cached !== null) return cached as T;

    const url = `${this.settings.serverUrl}${path}`;
    const res = await fetch(url, { headers: this.headers });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      throw new Error(`GET ${path} → ${res.status}: ${text}`);
    }
    const data = await res.json() as T;
    this.toCache(key, data);
    return data;
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    const key = this.cacheKey("POST", path, body);
    const cached = this.fromCache(key);
    if (cached !== null) return cached as T;

    // Deduplicate concurrent identical requests — if the same query is
    // already in-flight, return the existing promise instead of firing again.
    const pending = this.inflight.get(key);
    if (pending) return pending as Promise<T>;

    const request = (async () => {
      const url = `${this.settings.serverUrl}${path}`;
      const res = await fetch(url, {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`POST ${path} → ${res.status}: ${text}`);
      }
      const data = await res.json() as T;
      this.toCache(key, data);
      return data;
    })();

    this.inflight.set(key, request);
    request.finally(() => this.inflight.delete(key));
    return request;
  }

  async query(payload: unknown): Promise<ApiResponse> {
    return this.post<ApiResponse>("/api/query", payload);
  }

  async bronzeQuery(payload: unknown): Promise<ApiResponse> {
    return this.post<ApiResponse>("/api/bronze/query", payload);
  }

  async getDimensions(
    ref: string,
    orderBy?: string,
    orderDir: "asc" | "desc" = "desc",
    contextFilters?: Array<{ field: string; value: unknown }>,
    layer: "silver" | "bronze" = "silver",
  ): Promise<DimensionValuesResponse> {
    // Convert last dot to slash for URL path: "corporate.entity.sector" → "corporate.entity/sector"
    const lastDot = ref.lastIndexOf(".");
    const urlPath = lastDot > 0 ? ref.slice(0, lastDot) + "/" + ref.slice(lastDot + 1) : ref;
    const prefix = layer === "bronze" ? "/api/bronze" : "/api";
    const base = `${prefix}/dimensions/${urlPath}`;
    const params = new URLSearchParams();
    if (orderBy) {
      params.set("order_by", orderBy);
      params.set("order_dir", orderDir);
    }
    if (contextFilters && contextFilters.length > 0) {
      params.set("filters", JSON.stringify(contextFilters));
    }
    const qs = params.toString() ? `?${params.toString()}` : "";
    return this.get<DimensionValuesResponse>(`${base}${qs}`);
  }

  async getDomains(): Promise<Record<string, unknown>> {
    return this.get<Record<string, unknown>>("/api/domains");
  }

  async health(): Promise<{ status: string }> {
    return this.get<{ status: string }>("/api/health");
  }

  clearCache(): void {
    this.cache.clear();
  }
}

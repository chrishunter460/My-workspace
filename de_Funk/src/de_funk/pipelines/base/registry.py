# src/data_pipelines/base_pipeline/registry.py
from dataclasses import dataclass

@dataclass
class Endpoint:
    name: str
    base: str
    method: str
    path_template: str
    required_params: list
    default_query: dict
    response_key: str

class BaseRegistry:
    def __init__(self, cfg):
        self.headers = cfg.get("headers", {})
        self.base_urls = cfg["base_urls"]
        self.rate_limit = cfg.get("rate_limit_per_sec", 0.0834)
        self.endpoints = cfg["endpoints"]

    def render(self, ep_name, **params):
        """
        - Accepts required params either at the top-level or inside params['query'].
        - Renders path with path params only (top-level + default_path_params).
        - Builds final query from default_query + params['query'] + any extra top-level keys
          that are NOT used in the path and look like query params.
        """
        e = self.endpoints[ep_name]

        # Gather what's been provided
        top = dict(params)
        q_in = dict(top.pop("query", {}) or {})  # extract query dict if present

        # Determine required presence across BOTH top-level and query
        provided_keys = set(top.keys()) | set(q_in.keys())
        required = e.get("required_params", []) or []
        missing = [r for r in required if r not in provided_keys]
        if missing:
            raise ValueError(f"{ep_name}: missing {missing}")

        # Path formatting uses only path params (merge defaults + top-level)
        path_params = {**e.get("default_path_params", {}), **top}
        path = e["path_template"].format(**path_params)

        # Build final query: defaults + explicit query + any remaining top-level scalars
        # that aren't used in the path (treat as query keys). This allows either style.
        default_q = dict(e.get("default_query", {}) or {})
        # Anything in top that wasn't consumed by path placeholders becomes query
        # (exclude non-scalars to avoid passing nested dicts/lists inadvertently).
        path_placeholders = set()
        # Rough parse for {placeholder} occurrences:
        for frag in e["path_template"].split("{")[1:]:
            path_placeholders.add(frag.split("}")[0])

        spill_into_query = {
            k: v for k, v in top.items()
            if k not in path_placeholders and not isinstance(v, (dict, list, tuple, set))
        }

        query = {**default_q, **q_in, **spill_into_query}

        return (
            Endpoint(
                name=ep_name,
                base=e["base"],
                method=e["method"],
                path_template=e["path_template"],
                required_params=required,
                default_query=default_q,
                response_key=e["response_key"],
            ),
            path,
            query,
        )

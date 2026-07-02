def interpolate(expr: str, params: dict) -> str:
    out = expr
    for k, v in params.items():
        out = out.replace("${"+k+"}", v)
    return out

def as_graph(model_cfg: dict) -> dict:
    return model_cfg["graph"]

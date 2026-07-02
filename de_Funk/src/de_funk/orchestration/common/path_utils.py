from pathlib import Path

def repo_root(start=None):
    here = Path(start).resolve() if start else Path.cwd()
    for p in [here, *here.parents]:
        if (p / "configs").exists():
            return p
    return Path.cwd()

def storage_root(start=None):
    return repo_root(start) / "storage"


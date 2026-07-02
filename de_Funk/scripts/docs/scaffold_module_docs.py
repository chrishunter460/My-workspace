#!/usr/bin/env python
"""Scaffold module documentation from source code via AST parsing.

Scans src/de_funk/ and generates docs/modules/*.md files with:
- Frontmatter (title, date, status, source_files)
- Key Classes section (class name, file, purpose from docstring, method table)
- File Reference table

Manual sections (Purpose, Design Decisions, Triage) are left as TODO markers.

Usage:
    python -m scripts.docs.scaffold_module_docs           # Generate all
    python -m scripts.docs.scaffold_module_docs --force    # Overwrite existing
    python -m scripts.docs.scaffold_module_docs --check    # Check staleness only
"""
from __future__ import annotations

import ast
import re
import sys
from datetime import date
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = REPO_ROOT / "src" / "de_funk"
DOCS_DIR = REPO_ROOT / "docs" / "modules"
TEMPLATE = DOCS_DIR / "_template.md"

# ──────────────────────────────────────────────────────────────
# Group definitions: doc_name → (title, summary, file patterns)
# ──────────────────────────────────────────────────────────────
GROUPS: Dict[str, Tuple[str, str, List[str]]] = {
    "01-application": (
        "Application",
        "DeFunk entry point — assembles config, engine, graph, and sessions into a single app object.",
        ["app"],
    ),
    "02-configuration": (
        "Configuration & Data Classes",
        "Typed dataclasses mirroring YAML frontmatter, config loaders, and markdown parsers.",
        ["config/data_classes", "config/models", "config/loader",
         "config/domain", "config/markdown_loader", "config/constants"],
    ),
    "03-engine-sessions": (
        "Engine & Sessions",
        "Backend-agnostic Engine (read/write/transform), scoped Sessions (Build/Query/Ingest), and connection wrappers.",
        ["core/engine", "core/ops", "core/sql", "core/sessions",
         "core/session/filters", "core/storage",
         "core/connection", "core/duckdb_connection"],
    ),
    "04-graph-resolution": (
        "Graph & Field Resolution",
        "DomainGraph (BFS join paths), FieldResolver (domain.field → table.column), and BronzeResolver.",
        ["core/graph", "api/resolver", "api/bronze_resolver"],
    ),
    "05-api": (
        "API Layer",
        "FastAPI routers, exhibit handlers, and pydantic request/response models — the Obsidian connection point.",
        ["api/handlers", "api/models", "api/routers", "api/main"],
    ),
    "06-build-pipeline": (
        "Build Pipeline & Hooks",
        "BaseModel → DomainModel → GraphBuilder → NodeExecutor build chain, plus HookRunner and ArtifactStore.",
        ["models/base/model", "models/base/domain_model", "models/base/builder",
         "models/base/domain_builder", "models/base/graph_builder",
         "models/base/data_validator", "core/executor",
         "core/hooks", "core/artifacts", "core/plugins"],
    ),
    "07-ingestion": (
        "Ingestion Pipeline",
        "Download raw data, normalize to Bronze Delta tables — IngestorEngine, providers, HTTP client, rate limiting, circuit breakers.",
        ["pipelines/base/ingestor_engine", "pipelines/base/provider",
         "pipelines/base/socrata_client", "pipelines/base/socrata_provider",
         "pipelines/base/http_client", "pipelines/base/facet",
         "pipelines/base/key_pool", "pipelines/base/normalizer",
         "pipelines/base/registry",
         "pipelines/base/circuit_breaker", "pipelines/base/rate_limiter",
         "pipelines/base/progress_tracker", "pipelines/base/metrics",
         "pipelines/ingestors",
         "pipelines/providers"],
    ),
    "08-orchestration": (
        "Orchestration",
        "Pipeline scheduling, dependency resolution, and checkpointing.",
        ["orchestration"],
    ),
    "09-error-handling": (
        "Error Handling",
        "Exception hierarchy (23 typed errors), ErrorContext for structured debugging, and validation utilities.",
        ["core/exceptions", "core/error_handling", "core/validation"],
    ),
    "10-logging": (
        "Logging",
        "Structured + colored logging, LogTimer context manager, file + console output.",
        ["config/logging"],
    ),
    "11-utilities": (
        "Utilities",
        "Repo context, API validator, pipeline tracker — small cross-cutting helpers.",
        ["core/context", "utils"],
    ),
    "12-obsidian-plugin": (
        "Obsidian Plugin",
        "TypeScript plugin that renders exhibit blocks in Obsidian notes by calling the FastAPI backend.",
        [],  # No Python source — TypeScript in obsidian-plugin/
    ),
}


def extract_classes(py_file: Path) -> List[dict]:
    """Extract class info from a Python file via AST."""
    try:
        tree = ast.parse(py_file.read_text())
    except SyntaxError:
        return []

    classes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Get docstring
        docstring = ""
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value.strip().split("\n")[0]

        # Get bases
        bases = [ast.unparse(b).split(".")[-1] for b in node.bases
                 if ast.unparse(b) not in ("ABC", "object")]

        # Get public methods with signatures
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                # Build signature
                args = []
                for a in item.args.args[1:]:  # skip self
                    ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
                    args.append(f"{a.arg}{ann}")
                ret = f" -> {ast.unparse(item.returns)}" if item.returns else ""
                sig = f"{item.name}({', '.join(args)}){ret}"

                # Get method docstring
                m_doc = ""
                if (item.body and isinstance(item.body[0], ast.Expr)
                        and isinstance(item.body[0].value, ast.Constant)
                        and isinstance(item.body[0].value.value, str)):
                    m_doc = item.body[0].value.value.strip().split("\n")[0]

                methods.append({"name": item.name, "sig": sig, "doc": m_doc})

        # Get class-level attributes
        attrs = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                ann = ast.unparse(item.annotation) if item.annotation else ""
                attrs.append({"name": item.target.id, "type": ann})
            elif isinstance(item, ast.Assign):
                for t in item.targets:
                    if isinstance(t, ast.Name):
                        attrs.append({"name": t.id, "type": ""})

        classes.append({
            "name": node.name,
            "bases": bases,
            "docstring": docstring,
            "methods": methods,
            "attrs": attrs,
            "line": node.lineno,
        })

    return classes


def get_module_docstring(py_file: Path) -> str:
    """Get the module-level docstring."""
    try:
        tree = ast.parse(py_file.read_text())
    except SyntaxError:
        return ""
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        return tree.body[0].value.value.strip().split("\n")[0]
    return ""


def find_files(patterns: List[str]) -> List[Path]:
    """Find Python files matching patterns."""
    files = []
    for pattern in patterns:
        p = SRC / pattern
        if p.with_suffix(".py").exists():
            files.append(p.with_suffix(".py"))
        elif p.exists() and p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
        else:
            # Try as prefix
            parent = p.parent
            if parent.exists():
                for f in sorted(parent.glob(f"{p.name}*.py")):
                    if "__pycache__" not in str(f):
                        files.append(f)
    # Dedupe and filter
    seen = set()
    result = []
    for f in files:
        if f not in seen and "__pycache__" not in str(f) and f.name != "__init__.py":
            seen.add(f)
            result.append(f)
    return result


def generate_doc(doc_name: str, title: str, summary: str, patterns: List[str],
                 force: bool = False) -> str:
    """Generate a module doc from source files."""
    out_path = DOCS_DIR / f"{doc_name}.md"
    if out_path.exists() and not force:
        return f"  SKIP (exists): {out_path.name}"

    files = find_files(patterns)
    today = date.today().isoformat()

    # Collect source file paths for frontmatter
    src_files = [str(f.relative_to(REPO_ROOT)) for f in files]

    # ── Frontmatter ──
    lines = [
        "---",
        f'title: "{title}"',
        f'last_updated: "{today}"',
        f'status: "draft"',
        f"source_files:",
    ]
    for sf in src_files:
        lines.append(f"  - {sf}")
    lines.extend(["---", ""])

    # ── Header ──
    lines.extend([
        f"# {title}",
        "",
        f"> {summary}",
        "",
    ])

    # ── Purpose & Design Decisions ──
    lines.extend([
        "## Purpose & Design Decisions",
        "",
        "### What Problem This Solves",
        "",
        "<!-- TODO: Explain the problem this group addresses. -->",
        "",
        "### Key Design Decisions",
        "",
        "| Decision | Rationale | Alternative Considered |",
        "|----------|-----------|----------------------|",
        "| <!-- TODO --> | | |",
        "",
        "### Config-Driven Aspects",
        "",
        "| Behavior | Controlled By | Location |",
        "|----------|--------------|----------|",
        "| <!-- TODO --> | | |",
        "",
    ])

    # ── Architecture ──
    lines.extend([
        "## Architecture",
        "",
        "### Where This Fits",
        "",
        "```",
        "[Upstream] --> [THIS GROUP] --> [Downstream]",
        "```",
        "",
        "<!-- TODO: Brief explanation of data/control flow. -->",
        "",
        "### Dependencies",
        "",
        "| Depends On | What For |",
        "|------------|----------|",
        "| <!-- TODO --> | |",
        "",
        "| Depended On By | What For |",
        "|----------------|----------|",
        "| <!-- TODO --> | |",
        "",
    ])

    # ── Key Classes (auto-generated) ──
    lines.extend(["## Key Classes", ""])

    for f in files:
        classes = extract_classes(f)
        if not classes:
            continue

        rel = str(f.relative_to(REPO_ROOT))
        mod_doc = get_module_docstring(f)

        for cls in classes:
            base_str = f" ({', '.join(cls['bases'])})" if cls['bases'] else ""
            lines.append(f"### {cls['name']}{base_str}")
            lines.append("")
            lines.append(f"**File**: `{rel}:{cls['line']}`")
            lines.append("")
            if cls["docstring"]:
                lines.append(f"**Purpose**: {cls['docstring']}")
            else:
                lines.append("**Purpose**: <!-- TODO -->")
            lines.append("")

            # Attributes table
            if cls["attrs"]:
                lines.append("| Attribute | Type |")
                lines.append("|-----------|------|")
                for attr in cls["attrs"]:
                    t = attr["type"] if attr["type"] else "—"
                    lines.append(f"| `{attr['name']}` | `{t}` |")
                lines.append("")

            # Methods table
            if cls["methods"]:
                lines.append("| Method | Description |")
                lines.append("|--------|-------------|")
                for m in cls["methods"]:
                    doc = m["doc"] if m["doc"] else "<!-- TODO -->"
                    lines.append(f"| `{m['sig']}` | {doc} |")
                lines.append("")

    # ── How to Use ──
    lines.extend([
        "## How to Use",
        "",
        "### Common Operations",
        "",
        "<!-- TODO: Runnable code examples with expected output -->",
        "",
        "### Integration Examples",
        "",
        "<!-- TODO: Show cross-group usage -->",
        "",
    ])

    # ── Triage & Debugging ──
    lines.extend([
        "## Triage & Debugging",
        "",
        "### Symptom Table",
        "",
        "| Symptom | Likely Cause | Fix |",
        "|---------|-------------|-----|",
        "| <!-- TODO --> | | |",
        "",
        "### Debug Checklist",
        "",
        "- [ ] <!-- TODO -->",
        "",
        "### Common Pitfalls",
        "",
        "1. <!-- TODO -->",
        "",
    ])

    # ── File Reference (auto-generated) ──
    lines.extend(["## File Reference", ""])
    lines.append("| File | Purpose | Key Exports |")
    lines.append("|------|---------|-------------|")

    for f in files:
        rel = str(f.relative_to(REPO_ROOT))
        mod_doc = get_module_docstring(f)
        classes = extract_classes(f)
        exports = ", ".join(f"`{c['name']}`" for c in classes) if classes else "—"
        purpose = mod_doc if mod_doc else "—"
        lines.append(f"| `{rel}` | {purpose} | {exports} |")

    lines.append("")

    # Write
    out_path.write_text("\n".join(lines))
    class_count = sum(len(extract_classes(f)) for f in files)
    return f"  WROTE: {out_path.name} ({len(files)} files, {class_count} classes)"


def generate_obsidian_doc(force: bool = False) -> str:
    """Generate the Obsidian plugin doc (TypeScript, no AST parsing)."""
    out_path = DOCS_DIR / "12-obsidian-plugin.md"
    if out_path.exists() and not force:
        return f"  SKIP (exists): {out_path.name}"

    today = date.today().isoformat()
    ts_dir = REPO_ROOT / "obsidian-plugin" / "src"
    ts_files = sorted(ts_dir.rglob("*.ts")) if ts_dir.exists() else []

    lines = [
        "---",
        f'title: "Obsidian Plugin"',
        f'last_updated: "{today}"',
        f'status: "draft"',
        "source_files:",
    ]
    for f in ts_files:
        lines.append(f"  - {f.relative_to(REPO_ROOT)}")
    lines.extend(["---", ""])

    lines.extend([
        "# Obsidian Plugin",
        "",
        "> TypeScript plugin that renders exhibit blocks in Obsidian notes by calling the FastAPI backend.",
        "",
        "## Purpose & Design Decisions",
        "",
        "### What Problem This Solves",
        "",
        "<!-- TODO -->",
        "",
        "### Connection to Python Backend",
        "",
        "The plugin calls these API endpoints:",
        "",
        "| Endpoint | Plugin File | What It Does |",
        "|----------|------------|-------------|",
        "| `POST /api/query` | `api-client.ts` | Execute exhibit queries (charts, tables, metrics) |",
        "| `GET /api/dimensions/{ref}` | `api-client.ts` | Populate filter sidebar dropdowns |",
        "| `GET /api/domains` | `api-client.ts` | Discover available domains |",
        "| `POST /api/bronze/query` | `api-client.ts` | Query Bronze layer directly |",
        "| `GET /api/health` | `api-client.ts` | Health check on startup |",
        "",
        "## File Reference",
        "",
        "| File | Purpose |",
        "|------|---------|",
    ])

    for f in ts_files:
        name = str(f.relative_to(ts_dir))
        lines.append(f"| `{name}` | <!-- TODO --> |")

    lines.extend([
        "",
        "## How to Use",
        "",
        "### Block Syntax",
        "",
        "See [docs/obsidian-plugin.md](../obsidian-plugin.md) for full block syntax reference.",
        "",
        "## Triage & Debugging",
        "",
        "### Symptom Table",
        "",
        "| Symptom | Likely Cause | Fix |",
        "|---------|-------------|-----|",
        "| <!-- TODO --> | | |",
        "",
    ])

    out_path.write_text("\n".join(lines))
    return f"  WROTE: {out_path.name} ({len(ts_files)} TypeScript files)"


def main():
    force = "--force" in sys.argv
    check = "--check" in sys.argv

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    if check:
        print("Staleness check:")
        for doc_name in GROUPS:
            p = DOCS_DIR / f"{doc_name}.md"
            if p.exists():
                # Read last_updated from frontmatter
                text = p.read_text()
                m = re.search(r'last_updated:\s*"(\d{4}-\d{2}-\d{2})"', text)
                if m:
                    print(f"  {doc_name}: last_updated={m.group(1)}")
                else:
                    print(f"  {doc_name}: no last_updated")
            else:
                print(f"  {doc_name}: MISSING")
        return

    print(f"Scaffolding {len(GROUPS) + 1} module docs...")
    print(f"  Source: {SRC}")
    print(f"  Output: {DOCS_DIR}")
    print(f"  Force: {force}")
    print()

    for doc_name, (title, summary, patterns) in GROUPS.items():
        if doc_name == "12-obsidian-plugin":
            result = generate_obsidian_doc(force)
        else:
            result = generate_doc(doc_name, title, summary, patterns, force)
        print(result)

    # Also generate Obsidian if not already done
    if "12-obsidian-plugin" not in GROUPS:
        result = generate_obsidian_doc(force)
        print(result)

    print("\nDone.")


if __name__ == "__main__":
    main()

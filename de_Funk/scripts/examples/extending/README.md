# Extending de_Funk - Developer Examples

This directory contains examples for developers who want to extend de_Funk with custom components.

## Examples

### custom_facet.py
Shows how to create custom data transformation facets for the pipeline.

**When to use:**
- Adding new data providers
- Implementing custom data transformations
- Normalizing API responses

**Key Concepts:**
- Inherit from `BaseFacet`
- Implement `transform()` method
- Define schema mapping

**Run:**
```bash
python -m scripts.examples.extending.custom_facet
```

### custom_model.py
Demonstrates how to create custom domain models.

**When to use:**
- Adding new data domains
- Implementing domain-specific logic
- Creating specialized measure calculations

**Key Concepts:**
- Inherit from `BaseModel`
- Define YAML configuration
- Implement custom methods

**Run:**
```bash
python -m scripts.examples.extending.custom_model
```

### custom_provider.py
Shows how to implement custom data providers.

**When to use:**
- Integrating new data sources
- Implementing custom API clients
- Adding new data ingestion pipelines

**Key Concepts:**
- Implement provider interface
- Handle rate limiting
- Error handling and retries

**Run:**
```bash
python -m scripts.examples.extending.custom_provider
```

### custom_notebook.md
Example of creating custom analysis notebooks.

**When to use:**
- Creating interactive dashboards
- Building analytical reports
- Sharing analysis templates

**Key Concepts:**
- YAML front matter for metadata
- `$filter${}` syntax for dynamic filters
- `$exhibits${}` syntax for visualizations
- Markdown for narrative content

**View in app:**
1. Place in `configs/notebooks/`
2. Run `python run_app.py`
3. Navigate to notebook in UI

## Development Workflow

1. **Study the example** - Read the code and comments
2. **Copy as template** - Use as starting point for your extension
3. **Customize** - Modify for your specific needs
4. **Test** - Write unit tests for your component
5. **Document** - Add docstrings and usage examples

## Best Practices

- **Follow existing patterns** - Match architectural patterns in codebase
- **Write tests** - All custom components should have tests
- **Document thoroughly** - Clear docstrings and examples
- **Type hints** - Use type hints for better IDE support
- **Error handling** - Graceful error handling and validation

## Related Documentation

- `/CLAUDE.md` - Architecture and patterns
- `/PIPELINE_GUIDE.md` - Data pipeline architecture
- `/docs/guide/` - Detailed technical guides
- `/scripts/examples/README.md` - Examples overview

## Need Help?

- Review existing implementations in codebase
- Check `/docs/guide/` for detailed documentation
- Run tests to see expected behavior: `pytest tests/`

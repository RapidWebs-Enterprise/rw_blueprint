# Auto-Documentation Guide

This document describes the auto-documentation setup for rw_blueprint.

## OpenAPI Specification

An OpenAPI 3.0 specification is maintained at `openapi.json` for the MCP server.

### Generating OpenAPI from Typer

```bash
# Install dependencies
uv pip install "typer[all]"

# Export CLI help as markdown
rw-blueprint --output-format markdown > docs/cli-reference.md

# Or generate JSON schema for CLI
rw-blueprint --output-format json > docs/cli-schema.json
```

### MCP Server Documentation

The MCP server exposes 4 tools and 2 resources:

| Type | Name | Description |
|------|------|-------------|
| Tool | `validate_topology` | Validate topology YAML |
| Tool | `generate_artifacts` | Generate docs and IaC |
| Tool | `run_probes` | Collect live state |
| Tool | `detect_drift` | Compare declared vs actual |
| Resource | `schema://topology` | JSON Schema |
| Resource | `report://drift` | Latest drift report |

See `openapi.json` for full API specification.

## Sphinx Documentation (Optional)

To generate HTML documentation with Sphinx:

```bash
# Install sphinx
uv pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints

# Create docs directory
mkdir -p docs/sphinx

# Initialize sphinx
sphinx-quickstart docs/sphinx

# Add to conf.py
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode']
source_suffix = '.rst'
master_doc = 'index'

# Build docs
cd docs/sphinx && make html
```

## MkDocs with Material Theme (Recommended)

For a modern documentation site:

```bash
# Install mkdocs
uv pip install mkdocs-material mkdocstrings[python]

# Create config
cat > mkdocs.yml << 'EOF'
site_name: rw_blueprint
theme:
  name: material
  palette:
    primary: blue
    accent: blue
nav:
  - Home: index.md
  - CLI Reference: cli.md
  - API Reference: api.md
  - Examples: examples.md
  - Deployment Guide: guides/deployment.md
  - Troubleshooting: guides/troubleshooting.md
plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            show_source: true
            show_root_toc: true
EOF

# Build site
mkdocs build
```

## Docstrings and Type Hints

All public functions use proper docstrings:

```python
def validate_topology(path: str) -> dict:
    """Validate a topology YAML file.
    
    Args:
        path: Path to topology YAML file
        
    Returns:
        Validation result with status and errors
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If topology is invalid
    """
    ...
```

## CI Documentation Generation

Add to `.github/workflows/ci.yml`:

```yaml
  docs:
    name: generate documentation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v5
        
      - name: Install docs dependencies
        run: uv pip install mkdocs-material mkdocstrings[python]
        
      - name: Generate documentation
        run: mkdocs build --strict
        
      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main'
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
```

## Current Documentation Status

| Component | Status | Location |
|-----------|--------|----------|
| README | ✅ Complete | Root |
| CLI Reference | ✅ In README | Root |
| Architecture | ✅ Complete | ARCHITECTURE.md |
| API Reference | 🟡 Partial | openapi.json |
| User Guides | ✅ Complete | docs/guides/ |
| Examples | ✅ Complete | examples/ |
| CHANGELOG | ✅ Complete | Root |
| CONTRIBUTING | ✅ Complete | Root |

## Recommendations

1. **For CLI-focused projects**: Use Typer's built-in `--help` output (already good)
2. **For API-focused projects**: Use OpenAPI/Swagger (see `openapi.json`)
3. **For library projects**: Use Sphinx with autodoc
4. **For mixed projects**: Use MkDocs with mkdocstrings plugin

See [mkdocs-material](https://squidfunk.github.io/mkdocs-material/) or [Sphinx](https://www.sphinx-doc.org/) for more options.

# Airflow DAG Factory

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.0+-blue.svg)](https://airflow.apache.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready DAG factory implementation for Apache Airflow that enables standardized DAG generation from YAML configurations with template inheritance, environment overrides, and security features.

## Features

🚀 **Template Inheritance**: Hierarchical template system with base templates and environment-specific overrides  
🔒 **Security**: Built-in encryption, access control, and audit logging  
🌍 **Environment Management**: Multi-environment support with automatic environment detection  
📊 **Self-Service UI**: Web interface for non-technical users to create and manage DAGs  
🛡️ **Validation**: Comprehensive configuration validation with JSON Schema  
⚡ **Performance**: Efficient DAG generation with caching and optimization  

## Quick Start

### Installation

Using uv (recommended):
```bash
uv pip install airflow-dag-factory
```

Using pip:
```bash
pip install airflow-dag-factory
```

For development:
```bash
git clone https://github.com/yourusername/airflow-dag-factory.git
cd airflow-dag-factory
uv pip install -e ".[dev]"
```

### Basic Usage

#### Command Line Interface

```bash
# List available templates
dag-factory list-templates

# Generate DAG from configuration
dag-factory generate config/my_dag.yaml

# Validate configuration
dag-factory validate config/my_dag.yaml --strict

# Start self-service UI
dag-factory ui --port 8080
```

#### Python API

```python
from src.dag_factory import DAGFactory

# Initialize factory
factory = DAGFactory()

# Generate DAG
dag = factory.create_dag_from_file('config/my_dag.yaml')

# Generate all DAGs from directory
dags = factory.generate_dags_from_directory('dags/configs/')
```

## Configuration Format

### Basic DAG Configuration

```yaml
# config/example_dag.yaml
dag_id: example_etl_pipeline
description: "Example ETL pipeline"
schedule: "@daily"
start_date: "2024-01-01"
tags: ["etl", "example"]

# Template inheritance
template: base_etl
extends: daily_etl

# Environment-specific overrides
environments:
  dev:
    schedule: "@hourly"
    max_active_runs: 1
  prod:
    schedule: "@daily"
    max_active_runs: 3

# Task definitions
tasks:
  extract_data:
    operator: BashOperator
    bash_command: "python scripts/extract.py"
    
  transform_data:
    operator: PythonOperator
    python_callable: transform_function
    depends_on: [extract_data]
    
  load_data:
    operator: BashOperator
    bash_command: "python scripts/load.py"
    depends_on: [transform_data]
```

### Template System

Create reusable templates:

```yaml
# templates/base_etl.yaml
template_type: base
description: "Base template for ETL workflows"
default_args:
  owner: "data-team"
  retries: 3
  retry_delay: 300
tags: ["etl", "template"]

# templates/daily_etl.yaml
extends: base_etl
description: "Daily ETL workflow template"
schedule: "@daily"
max_active_runs: 2
tags: ["etl", "daily"]
```

## Development

### Project Structure

```
src/
├── __init__.py          # Package initialization
├── cli.py              # Command-line interface
├── dag_factory.py      # Core DAG Factory implementation
├── utils.py            # Utility functions and helpers
├── self_service_ui.py  # Web UI for self-service
└── managers/
    ├── __init__.py
    ├── template.py     # Template management
    └── security.py     # Security features
```

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/airflow-dag-factory.git
cd airflow-dag-factory

# Install uv (if not already installed)
pip install uv

# Install in development mode
uv pip install -e ".[dev]"

# Run linting
python -m ruff check src/

# Run formatting
python -m black src/

# Run tests
python -m pytest tests/ -v
```

### Modern Python Tooling

This project uses modern Python development tools:

- **pyproject.toml**: Modern package configuration
- **uv**: Fast Python package manager
- **ruff**: Lightning-fast linting and formatting
- **black**: Code formatting
- **mypy**: Type checking
- **pytest**: Testing framework

## Security Features

### Encryption

```python
from src.managers.security import SecurityManager

# Initialize security manager
security = SecurityManager()

# Encrypt sensitive data
encrypted = security.encrypt_data("sensitive_info")

# Decrypt data
decrypted = security.decrypt_data(encrypted)
```

### Access Control

```python
# Set access levels
security.set_access_level("user1", AccessLevel.READ_ONLY)
security.set_access_level("admin1", AccessLevel.ADMIN)

# Check permissions
if security.can_modify_config("user1"):
    # Allow modification
    pass
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/yourusername/airflow-dag-factory/issues)
- 💬 [Discussions](https://github.com/yourusername/airflow-dag-factory/discussions)

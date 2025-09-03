# DAG Factory Documentation

Welcome to the comprehensive documentation for Apache Airflow DAG Factory - a modern, production-ready solution for generating standardized DAGs from YAML configurations.

## 📚 Documentation Overview

### Quick Start Guides
- **[User Guide](user_guide.md)** - Complete user manual with examples and best practices
- **[Deployment Guide](deployment_guide.md)** - Installation, setup, and deployment instructions  
- **[API Reference](api_reference.md)** - Complete API documentation with examples

### Specialized Guides  
- **[Security Guide](security_guide.md)** - Comprehensive security features and best practices
- **[Implementation Requirements](implementation-requirements.md)** - Requirements and implementation status

## 🚀 Quick Start

### Installation

```bash
# Using uv (recommended)
uv pip install airflow-dag-factory

# Using pip
pip install airflow-dag-factory

# With optional features
pip install "airflow-dag-factory[security,ui]"
```

### Basic Usage

1. **Create a configuration file:**

```yaml
# dags/configs/my_dag.yaml
dag_id: my_first_dag
description: "My first DAG using DAG Factory"
schedule: "@daily"
start_date: "2024-01-01"
tags: ["tutorial"]

tasks:
  - task_id: hello_world
    operator: bash
    parameters:
      bash_command: "echo 'Hello World!'"
```

2. **Generate the DAG:**

```bash
dag-factory generate dags/configs/my_dag.yaml
```

3. **Integrate with Airflow:**

```python
# dags/dag_factory_loader.py
from src.dag_factory import DAGFactory

factory = DAGFactory()
generated_dags = factory.generate_dags_from_directory('dags/configs')

for dag in generated_dags:
    globals()[dag.dag_id] = dag
```

## 🏗️ Architecture Overview

### Core Components

- **DAGFactory**: Main class for DAG generation and configuration processing
- **TemplateManager**: Handles template inheritance and composition
- **SecurityManager**: Provides encryption, access control, and audit logging
- **ConfigurationValidator**: Validates configurations against JSON schemas
- **CLI Interface**: Command-line tools for validation, generation, and management

### Project Structure

```
src/
├── __init__.py              # Package initialization
├── cli.py                   # Enhanced CLI interface  
├── dag_factory.py           # Core DAG Factory implementation
├── utils.py                 # Utility functions and helpers
├── self_service_ui.py       # Web interface for self-service
└── managers/
    ├── __init__.py
    ├── template.py          # Template inheritance system
    └── security.py          # Security and access control
```

## 🎯 Key Features

### ✅ **Template Inheritance**
- Hierarchical template system with base templates and overrides
- Jinja2 templating for dynamic configurations
- Environment-specific template variations

### ✅ **Environment Management**  
- Multi-environment support (dev/staging/prod)
- Environment-specific configuration overrides
- Automatic environment detection

### ✅ **Security Features**
- Configuration encryption at rest
- Role-based access control (RBAC)
- Comprehensive audit logging
- Integration with external secret managers

### ✅ **Validation Framework**
- JSON Schema-based configuration validation
- Dependency cycle detection
- Template inheritance validation
- Pre-deployment validation tools

### ✅ **Modern Development**
- Modern Python packaging with pyproject.toml
- Type hints and comprehensive testing
- CLI tools and web interface
- Integration with modern tooling (ruff, black, mypy)

## 📖 Documentation Structure

### For Users
- **[User Guide](user_guide.md)** - Start here for comprehensive usage instructions
- **[CLI Reference](user_guide.md#cli-reference)** - Command-line interface documentation
- **[Configuration Examples](user_guide.md#configuration-guide)** - Sample configurations and patterns

### For Developers
- **[API Reference](api_reference.md)** - Complete API documentation
- **[Development Setup](deployment_guide.md#development-installation)** - Setting up development environment
- **[Security Implementation](security_guide.md)** - Security features and implementation

### For Operations
- **[Deployment Guide](deployment_guide.md)** - Production deployment instructions
- **[Security Guide](security_guide.md)** - Security configuration and best practices
- **[Monitoring](deployment_guide.md#monitoring-and-observability)** - Monitoring and observability setup

## 🔧 Configuration Examples

### Basic DAG Configuration

```yaml
dag_id: customer_etl_pipeline
description: "Customer data ETL pipeline"
schedule: "@daily"
start_date: "2024-01-01"
tags: ["etl", "customer"]

tasks:
  - task_id: extract_customers
    operator: bash
    parameters:
      bash_command: "python extract_customers.py"
      
  - task_id: transform_customers
    operator: python
    parameters:
      python_callable: "transformers.customer.process"
    depends_on: [extract_customers]
    
  - task_id: load_customers
    operator: bash
    parameters:
      bash_command: "python load_customers.py"
    depends_on: [transform_customers]
```

### Template Inheritance

```yaml
# templates/base_etl.yaml
description: "Base ETL template"
default_args:
  owner: "data-team"
  retries: 3
  retry_delay: 300
tags: ["etl"]

# configs/my_etl.yaml  
template:
  extends: "base_etl"
dag_id: my_etl_pipeline
schedule: "@daily"
start_date: "2024-01-01"
# Inherits all base_etl settings
```

### Environment-Specific Configuration

```yaml
dag_id: multi_env_pipeline
schedule: "@daily"
start_date: "2024-01-01"

environments:
  dev:
    schedule: "@hourly"
    max_active_runs: 1
  staging:
    schedule: "0 2 * * *"
    email: ["staging-team@company.com"]
  prod:
    schedule: "@daily"
    max_active_runs: 3
    email: ["ops@company.com"]
```

## 🛠️ CLI Usage

### Common Commands

```bash
# Validate configuration
dag-factory validate config.yaml

# Generate DAG
dag-factory generate config.yaml --environment prod

# List available templates
dag-factory list-templates --verbose

# Start web interface
dag-factory ui --port 8080

# Security management
dag-factory security list-users
dag-factory security check-permissions --username user@company.com
```

### Development Workflow

```bash
# Install in development mode
uv pip install -e ".[dev]"

# Validate all configurations
find dags/configs -name "*.yaml" -exec dag-factory validate {} \;

# Run tests
python -m pytest tests/ -v

# Code quality checks
python -m ruff check src/
python -m black src/
python -m mypy src/
```

## 🔐 Security Features

### Encryption

```bash
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Enable encryption
export DAG_FACTORY_ENCRYPTION_KEY="your-key"
export DAG_FACTORY_ENABLE_SECURITY=true
```

### Access Control

```yaml
# dags/security/roles.yaml
roles:
  developer:
    users: ["dev@company.com"]
    permissions: ["read", "write"]
    environments: ["dev", "staging"]
    
  admin:
    users: ["admin@company.com"]  
    permissions: ["read", "write", "delete", "deploy"]
    environments: ["dev", "staging", "prod"]
```

## 📊 Monitoring and Observability

### Built-in Health Checks

The DAG Factory includes automatic health monitoring:

```yaml
# Automatically created health monitoring DAG
dag_id: dag_factory_health_monitoring
schedule: "*/15 * * * *"  # Every 15 minutes
tasks:
  - validate_configs
  - check_template_availability  
  - monitor_generation_performance
  - alert_on_failures
```

### Metrics Collection

```python
# Prometheus metrics automatically collected
from src.dag_factory_monitor import DAGFactoryMonitor

monitor = DAGFactoryMonitor()
monitor.start_monitoring()
```

## 🚀 Getting Help

### Documentation Navigation

1. **New Users**: Start with [User Guide](user_guide.md)
2. **Deployment**: Follow [Deployment Guide](deployment_guide.md)  
3. **Security Setup**: Review [Security Guide](security_guide.md)
4. **API Integration**: Check [API Reference](api_reference.md)
5. **Troubleshooting**: See [User Guide - Troubleshooting](user_guide.md#troubleshooting)

### Support Channels

- **Documentation**: Comprehensive guides in the `docs/` directory
- **Examples**: Sample configurations in the `examples/` directory  
- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Join community discussions for questions and tips

### Quick Links

- [Installation Instructions](deployment_guide.md#installation-methods)
- [Configuration Schema](api_reference.md#configuration-schema)
- [CLI Command Reference](user_guide.md#cli-reference)
- [Security Best Practices](security_guide.md#best-practices)
- [Template System Guide](user_guide.md#template-system)
- [Environment Management](user_guide.md#environment-management)

## 📝 Contributing

We welcome contributions! Please see:

- **Development Setup**: [Deployment Guide - Development Installation](deployment_guide.md#development-installation)
- **Code Standards**: Modern Python with ruff, black, and mypy
- **Testing**: Comprehensive test suite with pytest
- **Documentation**: Keep documentation updated with changes

---

**Next Steps**: Choose the appropriate guide based on your role and needs, or start with the [User Guide](user_guide.md) for a comprehensive introduction to DAG Factory.

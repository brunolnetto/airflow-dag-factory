# DAG Factory Deployment Guide

## Modern Project Structure
```
airflow-dag-factory/
├── src/                              # Source package
│   ├── __init__.py                   # Package initialization
│   ├── cli.py                        # Enhanced CLI interface
│   ├── dag_factory.py                # Core factory implementation
│   ├── utils.py                      # Utility functions
│   ├── self_service_ui.py            # Web interface
│   └── managers/                     # Management modules
│       ├── __init__.py
│       ├── template.py               # Template inheritance
│       └── security.py               # Security features
├── dags/                             # Airflow DAGs directory
│   ├── configs/                      # Configuration files
│   │   ├── etl_user_data.yaml
│   │   ├── ml_model_training.yaml
│   │   └── data_quality_checks.yaml
│   ├── templates/                    # DAG templates
│   │   ├── base_etl.yaml
│   │   ├── daily_etl.yaml
│   │   └── ml_pipeline.yaml
│   ├── security/                     # Security configurations
│   │   ├── roles.yaml
│   │   └── encryption_keys/
│   ├── functions/                    # Custom functions
│   │   ├── __init__.py
│   │   ├── etl.py
│   │   ├── ml.py
│   │   ├── data_validation.py
│   │   └── data_quality.py
│   └── generated/                    # Generated DAG files
├── tests/                            # Test suite
├── docs/                             # Documentation
├── docker/                           # Docker configurations
├── pyproject.toml                    # Modern package configuration
└── Makefile                          # Development commands
```

### From Legacy DAGs

1. **Export existing DAG configurations**
2. **Create templates for common patterns**
3. **Validate new configurations**
4. **Gradual migration with parallel running**
5. **Monitor performance and adjust**

### Version Compatibility

- **v1.0+**: Modern pyproject.toml structure
- **v0.x**: Legacy setup.py structure (deprecated)

For detailed migration assistance, see the migration scripts in the `tools/` directory. Management modules


## Installation Methods

### Method 1: Package Installation (Recommended)

#### Using uv (fastest)
```bash
# Install uv if not already installed
pip install uv

# Install DAG Factory
uv pip install airflow-dag-factory

# Install with optional features
uv pip install "airflow-dag-factory[security,ui,dev]"
```

#### Using pip
```bash
# Basic installation
pip install airflow-dag-factory

# With optional features
pip install "airflow-dag-factory[security,ui]"
```

### Method 2: Development Installation

```bash
# Clone repository
git clone https://github.com/yourusername/airflow-dag-factory.git
cd airflow-dag-factory

# Install in development mode
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

## Dependencies

### Core Dependencies
```toml
# Automatically installed with the package
jinja2 >= 3.0.0        # Template rendering
jsonschema >= 4.0.0    # Configuration validation
pyyaml >= 6.0          # YAML processing
```

### Optional Dependencies
```toml
# Security features
cryptography >= 3.4.8  # Encryption support
passlib >= 1.7.4       # Password hashing

# Web UI
fastapi >= 0.68.0      # Web framework
uvicorn >= 0.15.0      # ASGI server

# Development tools
ruff >= 0.1.0          # Linting and formatting
black >= 23.0.0        # Code formatting
mypy >= 1.0.0          # Type checking
pytest >= 7.0.0        # Testing framework
```

### Airflow Requirements
```bash
# Minimum Airflow version
apache-airflow >= 2.5.0

# Recommended with providers
apache-airflow[postgres,redis,crypto] >= 2.8.0
```

## Environment Setup

### Environment Variables
```bash
# Required environment variables
export AIRFLOW_HOME=/path/to/airflow
export AIRFLOW__CORE__DAGS_FOLDER=/path/to/airflow/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False

# DAG Factory specific
export DAG_FACTORY_CONFIG_DIR=/path/to/dags/configs
export DAG_FACTORY_TEMPLATES_DIR=/path/to/dags/templates
export DAG_FACTORY_SECURITY_DIR=/path/to/dags/security

# Optional: Enable security features
export DAG_FACTORY_ENABLE_SECURITY=true
export DAG_FACTORY_ENCRYPTION_KEY=your-encryption-key

# Development mode
export DAG_FACTORY_DEV_MODE=true
```

### CLI Usage

```bash
# Using the console script (after installation)
dag-factory --help

# Using Python module execution
python -m src.cli --help

# Available commands
dag-factory list-templates              # List available templates
dag-factory validate config.yaml        # Validate configuration
dag-factory generate config.yaml        # Generate DAG
dag-factory security list-users         # Security management
dag-factory ui --port 8080             # Start web interface
```

### Configuration Management

#### Basic Configuration
```yaml
# dags/configs/example_dag.yaml
dag_id: example_etl_pipeline
description: "Example ETL pipeline"
schedule: "@daily"
start_date: "2024-01-01"
tags: ["etl", "example"]

# Template inheritance
template:
  extends: "base_etl"
  overrides:
    retries: 5
    retry_delay: 600

# Environment-specific settings
environments:
  dev:
    schedule: "@hourly"
    max_active_runs: 1
  prod:
    schedule: "@daily"
    max_active_runs: 3
    email: ["ops@company.com"]

# Task definitions
tasks:
  - task_id: extract_data
    operator: bash
    parameters:
      bash_command: "python scripts/extract.py"
      
  - task_id: transform_data
    operator: python
    parameters:
      python_callable: "functions.etl.transform_data"
    depends_on: [extract_data]
    
  - task_id: load_data
    operator: bash
    parameters:
      bash_command: "python scripts/load.py"
    depends_on: [transform_data]
```

#### Template System
```yaml
# dags/templates/base_etl.yaml
description: "Base template for ETL workflows"
tags: ["etl", "template"]
default_args:
  owner: "data-team"
  retries: 3
  retry_delay: 300
  email_on_failure: true
  email_on_retry: false
max_active_runs: 1
catchup: false
```

# For data sources
```bash
export POSTGRES_CONN_ID=postgres_default
export REDSHIFT_CONN_ID=redshift_default
export S3_CONN_ID=s3_default
```

## Airflow Integration

### DAG Registration

Add to your Airflow DAGs directory:

```python
# dags/dag_factory_loader.py
"""
DAG Factory Loader - Automatically discovers and loads DAG configurations
"""
from src.dag_factory import DAGFactory
import os

# Initialize factory
factory = DAGFactory(
    config_dir=os.getenv('DAG_FACTORY_CONFIG_DIR', 'dags/configs'),
    templates_dir=os.getenv('DAG_FACTORY_TEMPLATES_DIR', 'dags/templates'),
    enable_security=os.getenv('DAG_FACTORY_ENABLE_SECURITY', 'false').lower() == 'true'
)

# Generate all DAGs and add to globals
generated_dags = factory.generate_dags_from_directory()
for dag in generated_dags:
    globals()[dag.dag_id] = dag
```

### Airflow Configuration Updates

Add to `airflow.cfg`:
```ini
[core]
# Enable DAG Factory parsing
dagbag_import_timeout = 300
dag_file_processor_timeout = 300

# Performance optimization for generated DAGs
max_active_runs_per_dag = 3
parallelism = 32
dag_concurrency = 16

[scheduler]
# Increase parsing performance
dag_dir_list_interval = 300
catchup_by_default = False

[webserver]
# UI enhancements
expose_config = True
enable_proxy_fix = True
```

### Docker Deployment

```dockerfile
# Dockerfile.dag-factory
FROM apache/airflow:2.8.0-python3.11

# Install DAG Factory
USER root
RUN apt-get update && apt-get install -y git
USER airflow

# Install package
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install airflow-dag-factory[security,ui]

# Copy configurations
COPY dags/ ${AIRFLOW_HOME}/dags/
COPY config/ ${AIRFLOW_HOME}/config/

# Set environment variables
ENV DAG_FACTORY_CONFIG_DIR=${AIRFLOW_HOME}/dags/configs
ENV DAG_FACTORY_TEMPLATES_DIR=${AIRFLOW_HOME}/dags/templates
ENV DAG_FACTORY_ENABLE_SECURITY=true
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  airflow-webserver:
    build: .
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - DAG_FACTORY_CONFIG_DIR=/opt/airflow/dags/configs
      - DAG_FACTORY_TEMPLATES_DIR=/opt/airflow/dags/templates
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
    ports:
      - "8080:8080"
    depends_on:
      - postgres
      
  postgres:
    image: postgres:13
    environment:
      - POSTGRES_USER=airflow
      - POSTGRES_PASSWORD=airflow
      - POSTGRES_DB=airflow
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
volumes:
  postgres_data:
```

## Database Connections Setup

```bash
# Add via Airflow CLI
airflow connections add 'postgres_default' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-schema 'analytics' \
    --conn-login 'analyst' \
    --conn-password 'password'

airflow connections add 'redshift_default' \
    --conn-type 'redshift' \
    --conn-host 'cluster.region.redshift.amazonaws.com' \
    --conn-schema 'dev' \
    --conn-login 'username' \
    --conn-password 'password'

# Add AWS S3 connection
airflow connections add 's3_default' \
    --conn-type 'aws' \
    --conn-extra '{"aws_access_key_id":"YOUR_KEY","aws_secret_access_key":"YOUR_SECRET"}'
```

## Monitoring and Observability

### Built-in Monitoring

The DAG Factory includes built-in monitoring capabilities:

```python
# Automatic metrics collection
from src.dag_factory_monitor import DAGFactoryMonitor

# Monitor DAG generation performance
monitor = DAGFactoryMonitor()
monitor.start_monitoring()
```

### Health Check DAG

A health monitoring DAG is automatically created:

```yaml
# Health check configuration
dag_id: dag_factory_health_monitoring
schedule: "*/15 * * * *"  # Every 15 minutes
tasks:
  - validate_configs
  - check_template_availability
  - monitor_generation_performance
  - alert_on_failures
```

### Prometheus Metrics

Available metrics:
- `dag_factory_config_parse_duration_seconds`
- `dag_factory_dag_generation_total`
- `dag_factory_validation_errors_total`
- `dag_factory_template_usage_count`

## Security Configuration

### Encryption Setup

```bash
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set environment variable
export DAG_FACTORY_ENCRYPTION_KEY="your-generated-key"
```

### Access Control

```yaml
# dags/security/roles.yaml
roles:
  admin:
    users: ["admin@company.com"]
    permissions: ["read", "write", "delete", "deploy"]
    
  developer:
    users: ["dev1@company.com", "dev2@company.com"]
    permissions: ["read", "write"]
    
  viewer:
    users: ["analyst@company.com"]
    permissions: ["read"]

audit:
  enabled: true
  log_level: INFO
  retention_days: 90
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Check package installation
   python -c "from src.dag_factory import DAGFactory; print('OK')"
   
   # Verify environment
   dag-factory --help
   ```

2. **Configuration Validation Errors**
   ```bash
   # Validate specific config
   dag-factory validate dags/configs/my_dag.yaml --verbose
   
   # Check template inheritance
   dag-factory list-templates --verbose
   ```

3. **DAG Generation Issues**
   ```bash
   # Generate with dry-run
   dag-factory generate dags/configs/my_dag.yaml --dry-run
   
   # Check specific environment
   dag-factory generate dags/configs/my_dag.yaml --environment prod
   ```

### Performance Optimization

```python
# Optimize DAG parsing
import os
os.environ['DAG_FACTORY_CACHE_ENABLED'] = 'true'
os.environ['DAG_FACTORY_PARALLEL_PROCESSING'] = 'true'
```

### Logging Configuration

```python
# Enhanced logging
import logging
logging.getLogger('dag_factory').setLevel(logging.DEBUG)
```

## Migration Guide

### From Legacy DAGs

1. **Export existing DAG configurations**
2. **Create templates for common patterns**
3. **Validate new configurations**
4. **Gradual migration with parallel running**
5. **Monitor performance and adjust**

### Version Compatibility

- **v1.0+**: Modern pyproject.toml structure
- **v0.x**: Legacy setup.py structure (deprecated)

For detailed migration assistance, see the migration scripts in the `tools/` directory.


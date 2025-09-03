# DAG Factory User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Concepts](#basic-concepts)
3. [Configuration Guide](#configuration-guide)
4. [Template System](#template-system)
5. [Environment Management](#environment-management)
6. [Security Features](#security-features)
7. [CLI Reference](#cli-reference)
8. [Web Interface](#web-interface)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

Choose your preferred installation method:

```bash
# Using uv (fastest, recommended)
uv pip install airflow-dag-factory

# Using pip
pip install airflow-dag-factory

# With optional features
pip install "airflow-dag-factory[security,ui]"

# Development installation
git clone https://github.com/yourusername/airflow-dag-factory.git
cd airflow-dag-factory
uv pip install -e ".[dev]"
```

### Quick Start

1. **Create your first configuration:**

```yaml
# dags/configs/my_first_dag.yaml
dag_id: my_first_etl
description: "My first DAG using DAG Factory"
schedule: "@daily"
start_date: "2024-01-01"
tags: ["tutorial", "etl"]

tasks:
  - task_id: hello_world
    operator: bash
    parameters:
      bash_command: "echo 'Hello from DAG Factory!'"
      
  - task_id: python_task
    operator: python
    parameters:
      python_callable: "datetime.datetime.now"
    depends_on: [hello_world]
```

2. **Validate your configuration:**

```bash
dag-factory validate dags/configs/my_first_dag.yaml
```

3. **Generate the DAG:**

```bash
dag-factory generate dags/configs/my_first_dag.yaml
```

4. **Use in Airflow:**

```python
# dags/dag_factory_loader.py
from src.dag_factory import DAGFactory

factory = DAGFactory()
generated_dags = factory.generate_dags_from_directory('dags/configs')

# Make DAGs available to Airflow
for dag in generated_dags:
    globals()[dag.dag_id] = dag
```

## Basic Concepts

### DAG Configuration Structure

Every DAG configuration consists of these main sections:

- **Metadata**: `dag_id`, `description`, `schedule`, `start_date`
- **Template**: Inheritance and composition settings
- **Environment**: Environment-specific overrides
- **Tasks**: Task definitions with operators and parameters
- **Dependencies**: Task relationships and data flows

### Template Inheritance

Templates allow you to define reusable DAG patterns:

```yaml
# templates/base_etl.yaml (parent template)
description: "Base ETL template"
default_args:
  owner: "data-team"
  retries: 3
  retry_delay: 300
  email_on_failure: true
tags: ["etl"]

# configs/my_etl.yaml (inherits from base)
template:
  extends: "base_etl"
dag_id: customer_etl
schedule: "@hourly"
# Inherits all settings from base_etl
```

### Environment Management

Different environments can have different configurations:

```yaml
dag_id: production_pipeline
schedule: "@daily"

environments:
  dev:
    schedule: "@hourly"
    max_active_runs: 1
  staging:
    schedule: "0 2 * * *"  # 2 AM daily
  prod:
    schedule: "@daily"
    max_active_runs: 3
    email: ["ops@company.com"]
```

## Configuration Guide

### DAG-Level Configuration

```yaml
# Required fields
dag_id: unique_dag_identifier          # Must be unique across Airflow
description: "Human readable description"
schedule: "@daily"                     # Cron or Airflow preset
start_date: "2024-01-01"              # ISO date format

# Optional DAG settings
end_date: "2024-12-31"                # When DAG should stop
tags: ["etl", "production"]          # List of tags for organization
max_active_runs: 1                    # Concurrent DAG instances
catchup: false                        # Process historical dates
depends_on_past: false                # Wait for previous run
wait_for_downstream: false            # Wait for downstream DAGs

# Default arguments applied to all tasks
default_args:
  owner: "data-team"
  retries: 3
  retry_delay: 300                    # Seconds
  email_on_failure: true
  email_on_retry: false
  email: ["alerts@company.com"]
  pool: "default_pool"
  priority_weight: 1
```

### Task Configuration

```yaml
tasks:
  - task_id: extract_data              # Required: unique within DAG
    operator: bash                     # Required: operator type
    depends_on: []                     # Optional: list of task dependencies
    
    # Operator-specific parameters
    parameters:
      bash_command: "python extract.py"
      env:
        DATA_SOURCE: "production"
        
    # Task-level overrides
    retries: 5                         # Override DAG default
    retry_delay: 600                   # Override DAG default
    pool: "extract_pool"               # Use specific resource pool
    priority_weight: 10                # Higher priority
    
    # Task timing
    timeout: 3600                      # Task timeout in seconds
    execution_timeout: 1800            # Execution timeout
    
    # Email settings (override defaults)
    email_on_failure: true
    email_on_retry: false
    email: ["extract-team@company.com"]
```

### Supported Operators

#### Bash Operator

```yaml
- task_id: run_script
  operator: bash
  parameters:
    bash_command: "python /path/to/script.py"
    env:                              # Environment variables
      DB_HOST: "localhost"
      DB_PORT: "5432"
    cwd: "/working/directory"         # Working directory
```

#### Python Operator

```yaml
- task_id: process_data
  operator: python
  parameters:
    python_callable: "my_module.process_function"
    op_args: ["arg1", "arg2"]        # Positional arguments
    op_kwargs:                       # Keyword arguments
      param1: "value1"
      param2: 42
      param3: true
```

#### Email Operator

```yaml
- task_id: send_notification
  operator: email
  parameters:
    to: ["user@company.com"]
    subject: "DAG Completed Successfully"
    html_content: "<h1>Success!</h1><p>The ETL process completed.</p>"
    files: ["/path/to/report.pdf"]   # Optional attachments
```

#### Dummy/Empty Operator

```yaml
- task_id: checkpoint
  operator: dummy                    # No parameters needed
```

### Task Dependencies

Define task execution order:

```yaml
tasks:
  - task_id: extract
    operator: bash
    parameters:
      bash_command: "extract_data.py"
      
  - task_id: transform
    operator: python
    parameters:
      python_callable: "transform.main"
    depends_on: [extract]             # Runs after extract
    
  - task_id: load_warehouse
    operator: bash
    parameters:
      bash_command: "load_warehouse.py"
    depends_on: [transform]
    
  - task_id: load_lake
    operator: bash
    parameters:
      bash_command: "load_lake.py"
    depends_on: [transform]           # Parallel with load_warehouse
    
  - task_id: generate_report
    operator: python
    parameters:
      python_callable: "reporting.generate"
    depends_on: [load_warehouse, load_lake]  # Runs after both loads
```

### Task Groups

Organize related tasks into groups:

```yaml
task_groups:
  - group_id: data_extraction
    tooltip: "Extract data from various sources"
    tasks: [extract_users, extract_orders, extract_products]
    
  - group_id: data_transformation
    tooltip: "Transform and clean data"
    tasks: [validate_data, clean_data, enrich_data]

tasks:
  # Extraction tasks
  - task_id: extract_users
    operator: bash
    parameters:
      bash_command: "extract_users.py"
      
  - task_id: extract_orders
    operator: bash
    parameters:
      bash_command: "extract_orders.py"
      
  # Transformation tasks depend on all extraction tasks
  - task_id: validate_data
    operator: python
    parameters:
      python_callable: "validation.validate_all"
    depends_on: [extract_users, extract_orders, extract_products]
```

### Assets (Datasets)

Use Airflow Assets for cross-DAG dependencies:

```yaml
# Producer DAG
dag_id: data_producer
assets:
  produces: 
    - "s3://bucket/processed/users.parquet"
    - "s3://bucket/processed/orders.parquet"

# Consumer DAG
dag_id: data_consumer
schedule: null                        # Asset-driven, not time-based
assets:
  consumes:
    - "s3://bucket/processed/users.parquet"
    - "s3://bucket/processed/orders.parquet"
```

## Template System

### Creating Templates

Templates are reusable DAG configurations stored in the templates directory:

```yaml
# templates/base_data_pipeline.yaml
description: "Base template for data pipelines"
tags: ["data", "pipeline", "template"]

default_args:
  owner: "data-team"
  retries: 3
  retry_delay: 300
  email_on_failure: true
  email: ["data-alerts@company.com"]

# Common settings
max_active_runs: 1
catchup: false
depends_on_past: false

# Default tasks that most pipelines need
tasks:
  - task_id: start_pipeline
    operator: dummy
    
  - task_id: end_pipeline
    operator: dummy
```

### Template Inheritance

Create specialized templates that extend base templates:

```yaml
# templates/etl_pipeline.yaml
template:
  extends: "base_data_pipeline"

description: "ETL pipeline template"
tags: ["etl", "template"]

# Add ETL-specific tasks
tasks:
  - task_id: extract
    operator: bash
    parameters:
      bash_command: "echo 'Override with actual extract command'"
    depends_on: [start_pipeline]
    
  - task_id: transform
    operator: python
    parameters:
      python_callable: "transform.placeholder"
    depends_on: [extract]
    
  - task_id: load
    operator: bash
    parameters:
      bash_command: "echo 'Override with actual load command'"
    depends_on: [transform]
    
  - task_id: end_pipeline
    depends_on: [load]
```

### Using Templates in Configurations

```yaml
# configs/customer_etl.yaml
template:
  extends: "etl_pipeline"
  overrides:
    # Override specific tasks
    tasks:
      - task_id: extract
        parameters:
          bash_command: "python extract_customers.py"
      - task_id: transform
        parameters:
          python_callable: "customer_transform.main"
      - task_id: load
        parameters:
          bash_command: "python load_customers.py"

dag_id: customer_etl_pipeline
description: "Customer data ETL pipeline"
schedule: "@daily"
start_date: "2024-01-01"
tags: ["customer", "etl"]
```

### Template Variables

Use Jinja2 templating for dynamic configurations:

```yaml
# templates/parameterized_etl.yaml
description: "Parameterized ETL template"
tags: ["{{ table_name }}", "etl"]

tasks:
  - task_id: extract_{{ table_name }}
    operator: bash
    parameters:
      bash_command: "python extract.py --table {{ table_name }}"
      
  - task_id: transform_{{ table_name }}
    operator: python
    parameters:
      python_callable: "transform.process_{{ table_name }}"
    depends_on: [extract_{{ table_name }}]
```

Usage:

```yaml
# configs/users_etl.yaml
template:
  extends: "parameterized_etl"
  variables:
    table_name: "users"

dag_id: users_etl_pipeline
schedule: "@daily"
start_date: "2024-01-01"
```

## Environment Management

### Environment Configuration

Define environment-specific settings:

```yaml
dag_id: multi_environment_pipeline
description: "Pipeline with environment-specific settings"
schedule: "@daily"
start_date: "2024-01-01"

# Default configuration
max_active_runs: 1
default_args:
  retries: 3
  email_on_failure: true

# Environment-specific overrides
environments:
  dev:
    schedule: "@hourly"              # More frequent in dev
    max_active_runs: 1
    default_args:
      retries: 1                     # Fail fast in dev
      email_on_failure: false       # No emails in dev
    tasks:
      - task_id: extract_data
        parameters:
          bash_command: "python extract.py --env dev --sample 1000"
          
  staging:
    schedule: "0 2 * * *"           # 2 AM daily
    max_active_runs: 1
    default_args:
      retries: 2
      email: ["staging-alerts@company.com"]
    tasks:
      - task_id: extract_data
        parameters:
          bash_command: "python extract.py --env staging"
          
  prod:
    schedule: "@daily"               # Default schedule
    max_active_runs: 3
    default_args:
      retries: 5                     # More retries in prod
      email: ["prod-alerts@company.com", "oncall@company.com"]
    tasks:
      - task_id: extract_data
        parameters:
          bash_command: "python extract.py --env prod --full-load"
```

### Using Environment Variables

Reference environment variables in configurations:

```yaml
dag_id: environment_aware_pipeline
description: "Pipeline using environment variables"

tasks:
  - task_id: connect_database
    operator: bash
    parameters:
      bash_command: "python connect.py"
      env:
        DB_HOST: "${DB_HOST}"
        DB_PORT: "${DB_PORT:-5432}"        # Default value
        DB_NAME: "${DB_NAME}"
        DB_USER: "${DB_USER}"
        DB_PASSWORD: "${DB_PASSWORD}"
        
  - task_id: process_with_config
    operator: python
    parameters:
      python_callable: "processor.main"
      op_kwargs:
        api_endpoint: "${API_ENDPOINT}"
        batch_size: "${BATCH_SIZE:-1000}"
        debug_mode: "${DEBUG_MODE:-false}"
```

### Environment Detection

The factory can automatically detect the environment:

```bash
# Set environment explicitly
export DAG_FACTORY_ENVIRONMENT=prod
dag-factory generate config.yaml

# Or specify via CLI
dag-factory generate config.yaml --environment staging
```

## Security Features

### Enabling Security

```bash
# Install with security features
pip install "airflow-dag-factory[security]"

# Enable security
export DAG_FACTORY_ENABLE_SECURITY=true
export DAG_FACTORY_ENCRYPTION_KEY="your-encryption-key"
```

### Role-Based Access Control

```yaml
# dags/security/roles.yaml
roles:
  data_engineer:
    users: ["engineer@company.com"]
    permissions: ["read", "write", "validate"]
    environments: ["dev", "staging"]
    templates: ["etl_*", "data_*"]
    
  data_analyst:
    users: ["analyst@company.com"]
    permissions: ["read", "validate"]
    environments: ["dev"]
    
  admin:
    users: ["admin@company.com"]
    permissions: ["read", "write", "delete", "deploy"]
    environments: ["dev", "staging", "prod"]
```

### Encrypted Configurations

```yaml
# Regular configuration
database_password: "my-secret-password"

# Encrypted configuration
database_password: "encrypted:gAAAAABhZ..."
```

### CLI with Security

```bash
# Validate with user context
dag-factory validate config.yaml --username "engineer@company.com" --enable-security

# Security management
dag-factory security list-users
dag-factory security check-permissions --username "user@company.com"
```

## CLI Reference

### Global Options

```bash
dag-factory [global-options] <command> [command-options]

Global Options:
  -h, --help              Show help message
  --version               Show version information
  --config-dir DIR        Configuration directory (default: dags/configs)
  --templates-dir DIR     Templates directory (default: dags/templates)
  --enable-security       Enable security features
  --verbose, -v           Verbose output
```

### Commands

#### validate

Validate configuration files:

```bash
dag-factory validate <config-file> [options]

Options:
  --environment ENV       Target environment (dev/staging/prod)
  --username USER         User context for security validation
  --strict               Strict validation mode
  --output-format FORMAT  Output format (text/json/yaml)

Examples:
  dag-factory validate config.yaml
  dag-factory validate config.yaml --environment prod --strict
  dag-factory validate config.yaml --username admin@company.com
```

#### generate

Generate DAGs from configurations:

```bash
dag-factory generate <config-file> [options]

Options:
  --environment ENV       Target environment
  --output-dir DIR        Output directory for generated DAGs
  --dry-run              Generate without writing files
  --format FORMAT        Output format (python/yaml)

Examples:
  dag-factory generate config.yaml
  dag-factory generate config.yaml --environment prod
  dag-factory generate config.yaml --dry-run
```

#### list-templates

List available templates:

```bash
dag-factory list-templates [options]

Options:
  --verbose, -v          Show detailed template information
  --filter PATTERN       Filter templates by pattern

Examples:
  dag-factory list-templates
  dag-factory list-templates --verbose
  dag-factory list-templates --filter "etl_*"
```

#### security

Security management commands:

```bash
dag-factory security <subcommand> [options]

Subcommands:
  list-users             List all users
  list-roles             List all roles
  check-permissions      Check user permissions
  audit-log             View audit logs
  encrypt-config        Encrypt configuration file
  decrypt-config        Decrypt configuration file

Examples:
  dag-factory security list-users
  dag-factory security check-permissions --username user@company.com
  dag-factory security audit-log --days 7
  dag-factory security encrypt-config config.yaml
```

#### ui

Start the web interface:

```bash
dag-factory ui [options]

Options:
  --port PORT            Server port (default: 8080)
  --host HOST            Server host (default: localhost)
  --debug               Enable debug mode

Examples:
  dag-factory ui
  dag-factory ui --port 5000
  dag-factory ui --host 0.0.0.0 --port 8080
```

## Web Interface

### Starting the UI

```bash
dag-factory ui --port 8080
```

Navigate to `http://localhost:8080` to access the web interface.

### Features

- **Configuration Editor**: Create and edit DAG configurations with syntax highlighting
- **Template Browser**: Browse and preview available templates
- **Validation**: Real-time configuration validation
- **Generation**: Generate and preview DAGs
- **Security**: User authentication and role-based access

### API Endpoints

The web interface exposes a REST API:

```
GET    /api/templates              List templates
GET    /api/templates/{name}       Get template details
POST   /api/validate               Validate configuration
POST   /api/generate               Generate DAG
GET    /api/configs                List configurations
POST   /api/configs                Create configuration
PUT    /api/configs/{name}         Update configuration
DELETE /api/configs/{name}         Delete configuration
```

## Best Practices

### Configuration Organization

```
dags/
├── configs/
│   ├── etl/                      # ETL pipelines
│   │   ├── customer_etl.yaml
│   │   └── order_etl.yaml
│   ├── ml/                       # ML pipelines
│   │   ├── model_training.yaml
│   │   └── model_inference.yaml
│   └── monitoring/               # Monitoring DAGs
│       └── data_quality.yaml
├── templates/
│   ├── base_etl.yaml            # Base templates
│   ├── ml_pipeline.yaml
│   └── monitoring.yaml
└── security/
    └── roles.yaml
```

### Naming Conventions

- **DAG IDs**: Use descriptive prefixes (`etl_`, `ml_`, `monitor_`)
- **Task IDs**: Use verb_noun pattern (`extract_data`, `transform_users`)
- **Templates**: Use descriptive names (`base_etl`, `ml_training`)
- **Files**: Use snake_case for file names

### Performance Tips

- Use template inheritance to reduce duplication
- Enable caching for better performance
- Validate configurations before deployment
- Use environment-specific settings appropriately
- Organize configurations in logical directories

### Error Prevention

- Always validate configurations before deployment
- Use strict validation in production
- Implement proper testing for custom functions
- Use descriptive task and DAG names
- Document complex configurations

## Troubleshooting

### Common Issues

#### Configuration Validation Errors

```bash
# Problem: Invalid YAML syntax
Error: Invalid YAML: mapping values are not allowed here

# Solution: Check YAML indentation and syntax
dag-factory validate config.yaml --verbose
```

#### Template Not Found

```bash
# Problem: Template inheritance fails
Error: Template 'base_etl' not found

# Solution: Check template name and location
dag-factory list-templates
```

#### Import Errors

```bash
# Problem: Python callable not found
Error: Cannot import 'my_module.my_function'

# Solution: Verify Python path and function exists
python -c "from my_module import my_function; print('OK')"
```

#### Permission Denied

```bash
# Problem: Security validation fails
Error: User 'user@company.com' does not have 'write' permission

# Solution: Check user roles and permissions
dag-factory security check-permissions --username user@company.com
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Enable debug output
export DAG_FACTORY_LOG_LEVEL=DEBUG
dag-factory validate config.yaml --verbose

# Check generated DAG
dag-factory generate config.yaml --dry-run --verbose
```

### Validation Tools

Use built-in validation tools:

```bash
# Comprehensive validation
dag-factory validate config.yaml --strict --verbose

# Template validation
dag-factory validate-template template.yaml

# Security validation
dag-factory validate config.yaml --enable-security --username user@company.com
```

### Getting Help

- **Documentation**: Check the `docs/` directory
- **Examples**: See `examples/` directory for sample configurations
- **API Reference**: Use `dag-factory --help` and command-specific help
- **Issues**: Report bugs and feature requests on GitHub
- **Community**: Join discussions and ask questions

For additional support, refer to the [API Reference](api_reference.md) and [Security Guide](security_guide.md).

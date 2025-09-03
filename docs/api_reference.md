# DAG Factory API Documentation

## Overview

The DAG Factory provides a comprehensive API for programmatic DAG generation, template management, and configuration validation. This document covers all public APIs and their usage.

## Core Classes

### DAGFactory

The main factory class for generating DAGs from configurations.

```python
from src.dag_factory import DAGFactory

# Initialize factory
factory = DAGFactory(
    config_dir="dags/configs",
    templates_dir="dags/templates", 
    enable_security=False,
    enable_caching=True
)
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config_dir` | `str` | `"dags/configs"` | Directory containing configuration files |
| `templates_dir` | `str` | `"dags/templates"` | Directory containing template files |
| `enable_security` | `bool` | `False` | Enable security features |
| `enable_caching` | `bool` | `True` | Enable configuration caching |

#### Methods

##### `create_dag_from_file(config_path: str, environment: str = None) -> DAG`

Creates a single DAG from a configuration file.

```python
# Basic usage
dag = factory.create_dag_from_file("configs/etl_pipeline.yaml")

# With environment override
dag = factory.create_dag_from_file("configs/etl_pipeline.yaml", environment="prod")
```

**Parameters:**
- `config_path`: Path to configuration file
- `environment`: Environment for overrides ("dev", "staging", "prod")

**Returns:** Apache Airflow DAG object

**Raises:**
- `ConfigurationError`: Invalid configuration
- `TemplateError`: Template processing issues
- `ValidationError`: Configuration validation failures

##### `generate_dags_from_directory(pattern: str = "*.yaml") -> List[DAG]`

Generates all DAGs from configuration directory.

```python
# Generate all YAML configs
dags = factory.generate_dags_from_directory()

# Filter by pattern
dags = factory.generate_dags_from_directory("etl_*.yaml")
```

**Parameters:**
- `pattern`: Glob pattern for filtering files

**Returns:** List of DAG objects

##### `validate_configuration(config_path: str) -> ValidationResult`

Validates a configuration file without generating DAG.

```python
result = factory.validate_configuration("configs/test.yaml")
if result.is_valid:
    print("Configuration is valid")
else:
    for error in result.errors:
        print(f"Error: {error}")
```

**Returns:** `ValidationResult` object with validation details

### TemplateManager

Manages template inheritance and composition.

```python
from src.managers.template import TemplateManager

template_manager = TemplateManager("dags/templates")
```

#### Methods

##### `load_template(template_name: str) -> Dict[str, Any]`

Loads and processes a template with inheritance.

```python
template_data = template_manager.load_template("base_etl.yaml")
```

##### `list_templates() -> List[str]`

Returns list of available templates.

```python
templates = template_manager.list_templates()
for template in templates:
    print(f"Available: {template}")
```

##### `validate_template(template_path: str) -> ValidationResult`

Validates template structure and inheritance.

```python
result = template_manager.validate_template("templates/my_template.yaml")
```

### SecurityManager

Handles encryption, access control, and audit logging.

```python
from src.managers.security import SecurityManager

security = SecurityManager(
    username="user@company.com",
    enable_encryption=True
)
```

#### Methods

##### `encrypt_data(data: str) -> str`

Encrypts sensitive data.

```python
encrypted = security.encrypt_data("my-secret-password")
```

##### `decrypt_data(encrypted_data: str) -> str`

Decrypts encrypted data.

```python
decrypted = security.decrypt_data(encrypted_data)
```

##### `can_access_config(config_path: str, access_level: AccessLevel) -> bool`

Checks if user has access to configuration.

```python
from src.managers.security import AccessLevel

if security.can_access_config("prod/pipeline.yaml", AccessLevel.READ):
    # User can read this config
    pass
```

## CLI Integration

### Command Line Interface

The CLI provides a convenient interface to the API.

```python
from src.cli import main

# Programmatic CLI usage
import sys
sys.argv = ["cli.py", "validate", "config.yaml"]
main()
```

### Available Commands

#### `validate`

```bash
dag-factory validate config.yaml [options]
```

**Options:**
- `--environment {dev,staging,prod}`: Target environment
- `--enable-security`: Enable security validation
- `--username USERNAME`: User context for security
- `--verbose`: Detailed output

#### `generate`

```bash
dag-factory generate config.yaml [options]
```

**Options:**
- `--dry-run`: Generate without writing files
- `--output-dir DIR`: Output directory for generated DAGs
- `--environment ENV`: Environment overrides

#### `list-templates`

```bash
dag-factory list-templates [options]
```

**Options:**
- `--verbose`: Show template details
- `--filter PATTERN`: Filter by pattern

#### `security`

```bash
dag-factory security [subcommand] [options]
```

**Subcommands:**
- `list-users`: List all users
- `list-roles`: List all roles  
- `check-permissions`: Check user permissions
- `audit-log`: View audit logs

#### `ui`

```bash
dag-factory ui [options]
```

**Options:**
- `--port PORT`: Server port (default: 8080)
- `--host HOST`: Server host (default: localhost)

## Configuration Schema

### DAG Configuration

```yaml
# Complete configuration schema
dag_id: string                    # Required: Unique DAG identifier
description: string               # Optional: DAG description
schedule: string                  # Required: Cron or preset schedule
start_date: string               # Required: ISO date format
end_date: string                 # Optional: ISO date format
tags: [string]                   # Optional: List of tags
max_active_runs: int             # Optional: Default 1
catchup: bool                    # Optional: Default false

# Template inheritance
template:
  extends: string                # Optional: Parent template name
  overrides: object              # Optional: Override specific values

# Environment-specific configurations  
environments:
  dev: object                    # Development overrides
  staging: object                # Staging overrides
  prod: object                   # Production overrides

# Default arguments for all tasks
default_args:
  owner: string
  retries: int
  retry_delay: int               # Seconds
  email_on_failure: bool
  email_on_retry: bool
  email: [string]

# Task definitions
tasks:
  - task_id: string              # Required: Unique task identifier
    operator: string             # Required: Operator type
    depends_on: [string]         # Optional: Task dependencies
    parameters: object           # Optional: Operator-specific parameters
    retries: int                 # Optional: Override default retries
    retry_delay: int             # Optional: Override default retry delay
    pool: string                 # Optional: Resource pool
    priority_weight: int         # Optional: Task priority

# Task groups for logical organization
task_groups:
  - group_id: string
    tasks: [string]              # Task IDs to include in group
    tooltip: string              # Optional: Group description

# Airflow Assets (Datasets) for cross-DAG dependencies
assets:
  consumes: [string]             # Asset URIs this DAG depends on
  produces: [string]             # Asset URIs this DAG produces
```

### Template Configuration

```yaml
# Template schema
description: string              # Required: Template description
tags: [string]                   # Required: Template tags

# Template inheritance
template:
  extends: string                # Optional: Parent template
  overrides: object              # Optional: Override parent values

# Default values for DAGs using this template
default_args: object
schedule: string
max_active_runs: int
catchup: bool
tags: [string]

# Default tasks (can be extended by configs)
tasks: [object]
task_groups: [object]
assets: object
```

## Error Handling

### Exception Hierarchy

```python
from src.utils import (
    DAGFactoryBaseError,        # Base exception
    ConfigurationError,         # Configuration issues
    ValidationError,            # Validation failures
    TemplateError,             # Template processing errors
    SecurityError              # Security-related errors
)

try:
    dag = factory.create_dag_from_file("config.yaml")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except ValidationError as e:
    print(f"Validation failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### ValidationResult

```python
class ValidationResult:
    is_valid: bool               # Overall validation status
    errors: List[str]            # List of error messages
    warnings: List[str]          # List of warning messages
    metadata: Dict[str, Any]     # Additional validation metadata
    
    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        
    def __str__(self) -> str:
        """Human-readable validation summary"""
```

## Operator Support

### Built-in Operators

| Operator Key | Airflow Class | Required Parameters | Optional Parameters |
|--------------|---------------|-------------------|-------------------|
| `bash` | `BashOperator` | `bash_command` | `env`, `cwd` |
| `python` | `PythonOperator` | `python_callable` | `op_args`, `op_kwargs` |
| `email` | `EmailOperator` | `to`, `subject` | `html_content`, `files` |
| `dummy` | `DummyOperator` | None | None |

### Custom Operator Registration

```python
from airflow.operators.custom import CustomOperator

# Register custom operator
factory.register_operator(
    key="custom",
    operator_class=CustomOperator,
    required_params=["custom_param"],
    optional_params=["optional_param"]
)
```

### Usage in Configuration

```yaml
tasks:
  - task_id: my_bash_task
    operator: bash
    parameters:
      bash_command: "echo 'Hello World'"
      
  - task_id: my_python_task  
    operator: python
    parameters:
      python_callable: "my_module.my_function"
      op_kwargs:
        param1: "value1"
        param2: 42
        
  - task_id: my_custom_task
    operator: custom
    parameters:
      custom_param: "required_value"
      optional_param: "optional_value"
```

## Best Practices

### Performance Optimization

```python
# Enable caching for better performance
factory = DAGFactory(enable_caching=True)

# Use parallel processing for multiple configs
dags = factory.generate_dags_from_directory(parallel=True)

# Validate configurations before generation
for config_file in config_files:
    result = factory.validate_configuration(config_file)
    if not result.is_valid:
        continue  # Skip invalid configs
```

### Memory Management

```python
# For large numbers of DAGs, use generator pattern
def dag_generator():
    for config_file in config_files:
        yield factory.create_dag_from_file(config_file)

# Process DAGs one at a time
for dag in dag_generator():
    # Process DAG
    pass
```

### Error Handling Best Practices

```python
import logging

logger = logging.getLogger(__name__)

def safe_dag_generation(config_path: str):
    try:
        # Validate first
        result = factory.validate_configuration(config_path)
        if not result.is_valid:
            logger.error(f"Invalid config {config_path}: {result.errors}")
            return None
            
        # Generate DAG
        return factory.create_dag_from_file(config_path)
        
    except Exception as e:
        logger.exception(f"Failed to generate DAG from {config_path}")
        return None
```

## Integration Examples

### Flask Application Integration

```python
from flask import Flask, request, jsonify
from src.dag_factory import DAGFactory

app = Flask(__name__)
factory = DAGFactory()

@app.route('/validate', methods=['POST'])
def validate_config():
    config_data = request.json
    result = factory.validate_configuration_dict(config_data)
    return jsonify(result.to_dict())

@app.route('/generate', methods=['POST'])
def generate_dag():
    config_path = request.json['config_path']
    try:
        dag = factory.create_dag_from_file(config_path)
        return jsonify({'success': True, 'dag_id': dag.dag_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

### Airflow Plugin Integration

```python
from airflow.plugins_manager import AirflowPlugin
from src.dag_factory import DAGFactory

class DAGFactoryPlugin(AirflowPlugin):
    name = "dag_factory"
    
    @staticmethod
    def get_factory():
        return DAGFactory()
        
# Use in DAG files
from airflow import DAG
from plugins.dag_factory_plugin import DAGFactoryPlugin

factory = DAGFactoryPlugin.get_factory()
dag = factory.create_dag_from_file(__file__.replace('.py', '.yaml'))
```

For complete examples and advanced usage patterns, see the `examples/` directory in the repository.

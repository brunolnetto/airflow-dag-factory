"""
Apache Airflow DAG Factory Implementation
Production-ready solution for generating standardized DAGs from YAML configurations.
Enhanced with template inheritance, environment overrides, and security features.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from pathlib import Path
import importlib
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import jsonschema
from jinja2 import Template, Environment, FileSystemLoader

# Import new modules
from .managers.template import ConfigurationComposer, TemplateManager, EnvironmentManager
from .managers.security import SecurityManager, AccessLevel, AuditAction
from .utils import (
    logger, ConfigurationError, DAGFactoryBaseError as DAGFactoryError,
    substitute_env_vars, validate_dag_id, DEFAULT_DAG_ARGS, SUPPORTED_OPERATORS
)

try:
    import yaml
except ImportError:
    yaml = None

# Airflow imports (will be available in Airflow environment)
try:
    from airflow import DAG
    from airflow.operators.dummy import DummyOperator
    from airflow.operators.bash import BashOperator
    from airflow.operators.python import PythonOperator
    from airflow.operators.email import EmailOperator
    from airflow.utils.dates import days_ago
    from airflow.models import Variable
    from airflow.utils.task_group import TaskGroup
    from airflow.datasets import Dataset
except ImportError:
    # For development/testing outside Airflow environment
    logger.warning("Airflow modules not available - running in development mode")
    DAG = DummyOperator = BashOperator = PythonOperator = EmailOperator = None
    days_ago = Variable = TaskGroup = Dataset = None

# Configuration Schema for Validation
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["dag_id", "schedule", "tasks"],
    "properties": {
        "dag_id": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
        "description": {"type": "string"},
        "schedule": {"type": "string"},
        "start_date": {"type": "string"},
        "catchup": {"type": "boolean", "default": False},
        "template": {
            "type": "object",
            "properties": {
                "extends": {"type": "string"},
                "overrides": {"type": "object"}
            }
        },
        "environments": {
            "type": "object",
            "properties": {
                "dev": {"type": "object"},
                "staging": {"type": "object"},
                "prod": {"type": "object"}
            }
        },
        "max_active_runs": {"type": "integer", "minimum": 1, "default": 1},
        "max_active_tasks": {"type": "integer", "minimum": 1, "default": 16},
        "tags": {"type": "array", "items": {"type": "string"}},
        "owner": {"type": "string", "default": "data-engineering"},
        "retries": {"type": "integer", "minimum": 0, "default": 1},
        "retry_delay": {"type": "integer", "minimum": 1, "default": 300},
        "email_on_failure": {"type": "boolean", "default": True},
        "email_on_retry": {"type": "boolean", "default": False},
        "email": {"type": "array", "items": {"type": "string", "format": "email"}},
        "assets": {
            "type": "object",
            "properties": {
                "consumes": {"type": "array", "items": {"type": "string"}},
                "produces": {"type": "array", "items": {"type": "string"}}
            }
        },
        "task_groups": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["group_id", "tasks"],
                "properties": {
                    "group_id": {"type": "string"},
                    "tooltip": {"type": "string"},
                    "tasks": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "tasks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["task_id", "operator"],
                "properties": {
                    "task_id": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
                    "operator": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "parameters": {"type": "object"},
                    "retries": {"type": "integer", "minimum": 0},
                    "retry_delay": {"type": "integer", "minimum": 1},
                    "pool": {"type": "string"},
                    "priority_weight": {"type": "integer", "default": 1}
                }
            }
        }
    }
}


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class OperatorRegistry:
    """Registry for available operators and their parameter validation."""
    
    def __init__(self):
        self._operators = {
            'dummy': {
                'class': DummyOperator,
                'required_params': [],
                'optional_params': []
            },
            'bash': {
                'class': BashOperator,
                'required_params': ['bash_command'],
                'optional_params': ['env', 'output_encoding', 'skip_exit_code']
            },
            'python': {
                'class': PythonOperator,
                'required_params': ['python_callable'],
                'optional_params': ['op_args', 'op_kwargs', 'templates_dict']
            },
            'email': {
                'class': EmailOperator,
                'required_params': ['to', 'subject'],
                'optional_params': ['html_content', 'files', 'cc', 'bcc']
            }
        }
    
    def register_operator(self, name: str, operator_class, required_params: List[str], 
                         optional_params: List[str] = None):
        """Register a new operator type."""
        self._operators[name] = {
            'class': operator_class,
            'required_params': required_params,
            'optional_params': optional_params or []
        }
    
    def get_operator_class(self, operator_name: str):
        """Get operator class by name."""
        if operator_name not in self._operators:
            raise ConfigurationError(f"Unknown operator: {operator_name}")
        return self._operators[operator_name]['class']
    
    def validate_operator_params(self, operator_name: str, params: Dict[str, Any]) -> ValidationResult:
        """Validate operator parameters."""
        if operator_name not in self._operators:
            return ValidationResult(False, [f"Unknown operator: {operator_name}"])
        
        operator_def = self._operators[operator_name]
        errors = []
        
        # Check required parameters
        for required_param in operator_def['required_params']:
            if required_param not in params:
                errors.append(f"Missing required parameter '{required_param}' for operator '{operator_name}'")
        
        result = ValidationResult(len(errors) == 0, errors)
        return result


class ConfigurationValidator:
    """Validates DAG configuration files."""
    
    def __init__(self, operator_registry: OperatorRegistry):
        self.operator_registry = operator_registry
        self.schema = CONFIG_SCHEMA
    
    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate complete configuration."""
        result = ValidationResult(True)
        
        # JSON Schema validation
        try:
            jsonschema.validate(config, self.schema)
        except jsonschema.ValidationError as e:
            result.is_valid = False
            result.errors.append(f"Schema validation error: {e.message}")
            return result
        
        # Business logic validation
        self._validate_business_logic(config, result)
        self._validate_task_dependencies(config, result)
        self._validate_operators(config, result)
        
        return result
    
    def _validate_business_logic(self, config: Dict[str, Any], result: ValidationResult):
        """Validate business logic rules."""
        # Validate DAG ID naming convention
        dag_id = config.get('dag_id', '')
        if not dag_id.startswith(('etl_', 'ml_', 'reporting_', 'data_quality_')):
            result.warnings.append(f"DAG ID '{dag_id}' doesn't follow naming convention")
        
        # Validate schedule format
        schedule = config.get('schedule', '')
        if schedule and not any(schedule.startswith(prefix) for prefix in ['@', 'cron(', '0 ']):
            result.warnings.append(f"Schedule '{schedule}' might not be in correct format")
        
        # Validate email configuration
        if config.get('email_on_failure', True) and not config.get('email'):
            result.warnings.append("Email notifications enabled but no email addresses provided")
    
    def _validate_task_dependencies(self, config: Dict[str, Any], result: ValidationResult):
        """Validate task dependencies for cycles and missing tasks."""
        tasks = {task['task_id'] for task in config.get('tasks', [])}
        
        for task in config.get('tasks', []):
            task_id = task['task_id']
            depends_on = task.get('depends_on', [])
            
            # Check for self-dependency
            if task_id in depends_on:
                result.errors.append(f"Task '{task_id}' cannot depend on itself")
            
            # Check for missing dependencies
            for dep in depends_on:
                if dep not in tasks:
                    result.errors.append(f"Task '{task_id}' depends on non-existent task '{dep}'")
        
        # Simple cycle detection (for more complex graphs, use topological sort)
        if self._has_cycles(config.get('tasks', [])):
            result.errors.append("Circular dependencies detected in task graph")
    
    def _validate_operators(self, config: Dict[str, Any], result: ValidationResult):
        """Validate operator configurations."""
        for task in config.get('tasks', []):
            operator_name = task.get('operator', '')
            parameters = task.get('parameters', {})
            
            op_result = self.operator_registry.validate_operator_params(operator_name, parameters)
            if not op_result.is_valid:
                result.errors.extend([f"Task '{task['task_id']}': {error}" for error in op_result.errors])
    
    def _has_cycles(self, tasks: List[Dict[str, Any]]) -> bool:
        """Simple cycle detection using DFS."""
        # Build adjacency list
        graph = {}
        for task in tasks:
            task_id = task['task_id']
            graph[task_id] = task.get('depends_on', [])
        
        # DFS cycle detection
        visited = set()
        rec_stack = set()
        
        def dfs(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor in graph and dfs(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        for task_id in graph:
            if task_id not in visited:
                if dfs(task_id):
                    return True
        
        return False


class TaskBuilder:
    """Builds Airflow tasks from configuration."""
    
    def __init__(self, operator_registry: OperatorRegistry):
        self.operator_registry = operator_registry
    
    def build_task(self, task_config: Dict[str, Any], dag_defaults: Dict[str, Any]) -> Any:
        """Build an Airflow task from configuration."""
        task_id = task_config['task_id']
        operator_name = task_config['operator']
        parameters = task_config.get('parameters', {})
        
        # Get operator class
        operator_class = self.operator_registry.get_operator_class(operator_name)
        
        # Merge task-specific overrides with DAG defaults
        task_args = {
            'task_id': task_id,
            'retries': task_config.get('retries', dag_defaults.get('retries', 1)),
            'retry_delay': timedelta(seconds=task_config.get('retry_delay', dag_defaults.get('retry_delay', 300))),
            'pool': task_config.get('pool'),
            'priority_weight': task_config.get('priority_weight', 1)
        }
        
        # Remove None values
        task_args = {k: v for k, v in task_args.items() if v is not None}
        
        # Handle special parameter processing based on operator type
        processed_params = self._process_parameters(operator_name, parameters)
        task_args.update(processed_params)
        
        try:
            return operator_class(**task_args)
        except Exception as e:
            raise DAGFactoryError(f"Failed to create task '{task_id}': {str(e)}")
    
    def _process_parameters(self, operator_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process parameters based on operator type."""
        processed = parameters.copy()
        
        # Handle Python callable resolution
        if operator_name == 'python' and 'python_callable' in processed:
            callable_str = processed['python_callable']
            if isinstance(callable_str, str):
                # Import and resolve callable from string
                processed['python_callable'] = self._resolve_callable(callable_str)
        
        # Handle Jinja2 template rendering in bash commands
        if operator_name == 'bash' and 'bash_command' in processed:
            command = processed['bash_command']
            if isinstance(command, str) and '{{' in command:
                template = Template(command)
                # For now, just return as-is, Airflow will handle template rendering
                pass
        
        return processed
    
    def _resolve_callable(self, callable_str: str) -> Callable:
        """Resolve Python callable from string."""
        try:
            module_path, function_name = callable_str.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, function_name)
        except Exception as e:
            raise ConfigurationError(f"Cannot resolve callable '{callable_str}': {str(e)}")


class AssetManager:
    """Manages Airflow Assets (Datasets) for cross-DAG dependencies."""
    
    def __init__(self):
        self._assets = {}
    
    def get_asset(self, asset_uri: str) -> Dataset:
        """Get or create an asset."""
        if asset_uri not in self._assets:
            self._assets[asset_uri] = Dataset(asset_uri)
        return self._assets[asset_uri]
    
    def get_consumed_assets(self, asset_uris: List[str]) -> List[Dataset]:
        """Get list of consumed assets."""
        return [self.get_asset(uri) for uri in asset_uris]
    
    def get_produced_assets(self, asset_uris: List[str]) -> List[Dataset]:
        """Get list of produced assets."""
        return [self.get_asset(uri) for uri in asset_uris]


class DAGFactory:
    """Main DAG Factory class for generating Airflow DAGs with enhanced features."""
    
    def __init__(self, config_dir: str = 'dags/configs', templates_dir: str = 'dags/templates', 
                 enable_security: bool = True):
        self.config_dir = Path(config_dir)
        self.templates_dir = Path(templates_dir)
        self.enable_security = enable_security
        
        # Core components
        self.operator_registry = OperatorRegistry()
        self.validator = ConfigurationValidator(self.operator_registry)
        self.task_builder = TaskBuilder(self.operator_registry)
        self.asset_manager = AssetManager()
        
        # Enhanced features
        self.composer = ConfigurationComposer(str(templates_dir))
        if enable_security:
            self.security_manager = SecurityManager(str(config_dir))
        else:
            self.security_manager = None
        
        # Performance tracking
        self.generation_metrics = {
            'total_dags': 0,
            'successful_generations': 0,
            'failed_generations': 0,
            'total_generation_time': 0,
            'template_usage': {},
            'environment_usage': {}
        }
    
    def register_custom_operator(self, name: str, operator_class, required_params: List[str], 
                                 optional_params: List[str] = None):
        """Register a custom operator."""
        self.operator_registry.register_operator(name, operator_class, required_params, optional_params)
    
    def load_config(self, config_path: Union[str, Path], username: str = None, 
                    environment: str = None) -> Dict[str, Any]:
        """Load and validate configuration file with enhanced features."""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        try:
            # Load raw configuration
            if self.enable_security and self.security_manager and username:
                config = self.security_manager.load_secure_configuration(config_path, username)
            else:
                with open(config_path, 'r') as f:
                    if config_path.suffix.lower() in ['.yaml', '.yml']:
                        config = yaml.safe_load(f)
                    elif config_path.suffix.lower() == '.json':
                        config = json.load(f)
                    else:
                        raise ConfigurationError(f"Unsupported configuration format: {config_path.suffix}")
            
            # Apply template inheritance and environment overrides
            config = self.composer.compose_configuration(config, environment)
            
            # Environment variable substitution
            config = substitute_env_vars(config)
            
            # Validate composition
            composition_errors = self.composer.validate_composition(config)
            if composition_errors:
                error_msg = f"Configuration composition failed for {config_path}:\n"
                error_msg += "\n".join([f"  - {error}" for error in composition_errors])
                raise ConfigurationError(error_msg)
            
            # Standard validation
            validation_result = self.validator.validate_config(config)
            
            if not validation_result.is_valid:
                error_msg = f"Configuration validation failed for {config_path}:\n"
                error_msg += "\n".join([f"  - {error}" for error in validation_result.errors])
                raise ConfigurationError(error_msg)
            
            # Log warnings
            for warning in validation_result.warnings:
                logger.warning(f"Config warning in {config_path}: {warning}")
            
            # Track usage metrics
            if 'template' in config and 'extends' in config['template']:
                template_name = config['template']['extends']
                self.generation_metrics['template_usage'][template_name] = \
                    self.generation_metrics['template_usage'].get(template_name, 0) + 1
            
            if environment:
                self.generation_metrics['environment_usage'][environment] = \
                    self.generation_metrics['environment_usage'].get(environment, 0) + 1
            
            return config
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"YAML parsing error in {config_path}: {str(e)}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"JSON parsing error in {config_path}: {str(e)}")
    

    def create_dag(self, config: Dict[str, Any]) -> DAG:
        """Create a DAG from configuration."""
        start_time = datetime.now()
        
        try:
            # Extract DAG parameters
            dag_id = config['dag_id']
            description = config.get('description', f'Generated DAG: {dag_id}')
            schedule = config.get('schedule', '@daily')
            start_date = self._parse_date(config.get('start_date', '2023-01-01'))
            
            # Handle asset dependencies
            consumed_assets = []
            if 'assets' in config and 'consumes' in config['assets']:
                consumed_assets = self.asset_manager.get_consumed_assets(config['assets']['consumes'])
            
            # Create DAG
            default_args = {
                'owner': config.get('owner', 'data-engineering'),
                'depends_on_past': False,
                'start_date': start_date,
                'email_on_failure': config.get('email_on_failure', True),
                'email_on_retry': config.get('email_on_retry', False),
                'email': config.get('email', []),
                'retries': config.get('retries', 1),
                'retry_delay': timedelta(seconds=config.get('retry_delay', 300))
            }
            
            dag = DAG(
                dag_id=dag_id,
                description=description,
                schedule=consumed_assets if consumed_assets else schedule,
                default_args=default_args,
                catchup=config.get('catchup', False),
                max_active_runs=config.get('max_active_runs', 1),
                max_active_tasks=config.get('max_active_tasks', 16),
                tags=config.get('tags', ['generated']),
                is_paused_upon_creation=False
            )
            
            # Build tasks
            tasks = {}
            task_groups = {}
            
            # Create task groups if specified
            for group_config in config.get('task_groups', []):
                group_id = group_config['group_id']
                with TaskGroup(
                    group_id=group_id,
                    tooltip=group_config.get('tooltip', f'Task group: {group_id}'),
                    dag=dag
                ) as task_group:
                    task_groups[group_id] = task_group
            
            # Create tasks
            for task_config in config['tasks']:
                task = self.task_builder.build_task(task_config, default_args)
                task.dag = dag
                tasks[task_config['task_id']] = task
                
                # Handle asset outputs
                if 'assets' in config and 'produces' in config['assets']:
                    produced_assets = self.asset_manager.get_produced_assets(config['assets']['produces'])
                    task.outlets = produced_assets
            
            # Set up dependencies
            for task_config in config['tasks']:
                task_id = task_config['task_id']
                depends_on = task_config.get('depends_on', [])
                
                if depends_on:
                    task = tasks[task_id]
                    upstream_tasks = [tasks[dep] for dep in depends_on if dep in tasks]
                    task.set_upstream(upstream_tasks)
            
            # Assign tasks to task groups
            for group_config in config.get('task_groups', []):
                group_id = group_config['group_id']
                group_tasks = group_config.get('tasks', [])
                
                for task_id in group_tasks:
                    if task_id in tasks:
                        tasks[task_id].task_group = task_groups[group_id]
            
            # Update metrics
            generation_time = (datetime.now() - start_time).total_seconds()
            self.generation_metrics['total_dags'] += 1
            self.generation_metrics['successful_generations'] += 1
            self.generation_metrics['total_generation_time'] += generation_time
            
            logger.info(f"Successfully generated DAG '{dag_id}' in {generation_time:.2f} seconds")
            
            return dag
            
        except Exception as e:
            self.generation_metrics['total_dags'] += 1
            self.generation_metrics['failed_generations'] += 1
            logger.error(f"Failed to generate DAG from config: {str(e)}")
            raise DAGFactoryError(f"DAG generation failed: {str(e)}")
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string into datetime object."""
        if date_str.lower() == 'today':
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_str.lower().startswith('days_ago('):
            # Extract number from days_ago(n)
            import re
            match = re.search(r'days_ago\((\d+)\)', date_str)
            if match:
                days = int(match.group(1))
                return days_ago(days)
        
        # Try to parse as ISO date
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            # Try common date formats
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            raise ConfigurationError(f"Cannot parse date: {date_str}")
    
    def generate_dags_from_directory(self) -> List[DAG]:
        """Generate all DAGs from configuration directory."""
        dags = []
        
        if not self.config_dir.exists():
            logger.warning(f"Configuration directory not found: {self.config_dir}")
            return dags
        
        config_files = list(self.config_dir.glob('*.yaml')) + list(self.config_dir.glob('*.yml')) + list(self.config_dir.glob('*.json'))
        
        for config_file in config_files:
            try:
                config = self.load_config(config_file)
                dag = self.create_dag(config)
                dags.append(dag)
            except Exception as e:
                logger.error(f"Failed to generate DAG from {config_file}: {str(e)}")
                continue
        
        logger.info(f"Generated {len(dags)} DAGs from {len(config_files)} configuration files")
        return dags
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get generation metrics."""
        metrics = self.generation_metrics.copy()
        if metrics['total_dags'] > 0:
            metrics['success_rate'] = metrics['successful_generations'] / metrics['total_dags']
            metrics['average_generation_time'] = metrics['total_generation_time'] / metrics['total_dags']
        else:
            metrics['success_rate'] = 0
            metrics['average_generation_time'] = 0
        
        return metrics


# Factory instance for DAG generation
factory = DAGFactory()

# Example custom operator registration
def example_custom_function(**context):
    """Example custom function for PythonOperator."""
    logger.info("Executing custom function")
    return "success"

# Register the custom function
factory.register_custom_operator(
    'custom_python',
    PythonOperator,
    ['python_callable'],
    ['op_args', 'op_kwargs']
)

# Generate DAGs from configuration files only when in Airflow environment
# This prevents errors when importing for CLI or testing purposes
if __name__ != '__main__':
    # Only generate DAGs if we're being imported by Airflow
    try:
        import airflow
        # We're in an Airflow environment, safe to generate DAGs
        generated_dags = factory.generate_dags_from_directory()

        # Make DAGs available to Airflow
        for dag in generated_dags:
            globals()[dag.dag_id] = dag

        # Log metrics
        if generated_dags:
            metrics = factory.get_metrics()
            logger.info(f"DAG Factory Metrics: {metrics}")
    except ImportError:
        # Not in Airflow environment, skip DAG generation
        logger.debug("Airflow not available, skipping automatic DAG generation")
        generated_dags = []
else:
    generated_dags = []
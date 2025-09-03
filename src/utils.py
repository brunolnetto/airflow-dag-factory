"""
Shared utilities for DAG Factory components.

This module contains common functions and classes used across multiple
DAG Factory modules to eliminate code duplication.
"""

import copy
import os
import re
import logging
from typing import Dict, List, Any, Optional, Union


# Logger setup
logger = logging.getLogger(__name__)


class DAGFactoryBaseError(Exception):
    """Base exception for DAG Factory errors."""
    pass


class ConfigurationError(DAGFactoryBaseError):
    """Raised when configuration validation fails."""
    pass


class TemplateInheritanceError(DAGFactoryBaseError):
    """Raised when template inheritance fails."""
    pass


def deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any], 
                     merge_lists: bool = True, skip_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Deep merge two dictionaries with configurable list handling.
    
    Args:
        base: Base dictionary to merge into
        override: Dictionary with override values
        merge_lists: If True, append lists; if False, replace lists
        skip_keys: Keys to skip during merging
    
    Returns:
        Merged dictionary
    """
    skip_keys = skip_keys or []
    result = copy.deepcopy(base)
    
    for key, value in override.items():
        if key in skip_keys:
            continue
            
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value, merge_lists, skip_keys)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            if merge_lists:
                # Append new items to existing list
                result[key] = result[key] + value
            else:
                # Replace list completely
                result[key] = copy.deepcopy(value)
        else:
            result[key] = copy.deepcopy(value)
    
    return result


def substitute_env_vars(obj: Any) -> Any:
    """
    Recursively substitute environment variables in strings.
    
    Supports patterns like:
    - ${VAR}: Required variable
    - ${VAR:-default}: Variable with default value
    
    Args:
        obj: Object to process (can be dict, list, string, etc.)
        
    Returns:
        Object with environment variables substituted
    """
    if isinstance(obj, str):
        # Pattern: ${VAR} or ${VAR:-default}
        def replace_env_var(match):
            var_expr = match.group(1)
            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                value = os.getenv(var_expr)
                if value is None:
                    raise ConfigurationError(f"Environment variable '{var_expr}' not found")
                return value
        
        return re.sub(r'\$\{([^}]+)\}', replace_env_var, obj)
    elif isinstance(obj, dict):
        return {k: substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_env_vars(item) for item in obj]
    else:
        return obj


def set_nested_value(obj: Dict[str, Any], key_path: str, value: Any) -> None:
    """
    Set nested dictionary value using dot notation.
    
    Args:
        obj: Dictionary to modify
        key_path: Dot-separated path (e.g., 'tasks.0.parameters.email')
        value: Value to set
    """
    keys = key_path.split('.')
    current = obj
    
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    
    current[keys[-1]] = value


def get_nested_value(obj: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get nested dictionary value using dot notation.
    
    Args:
        obj: Dictionary to read from
        key_path: Dot-separated path
        default: Default value if path not found
        
    Returns:
        Value at path or default
    """
    keys = key_path.split('.')
    current = obj
    
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default


def safe_load_yaml_file(file_path: str) -> Dict[str, Any]:
    """
    Safely load YAML file with error handling.
    
    Args:
        file_path: Path to YAML file
        
    Returns:
        Parsed YAML content
        
    Raises:
        ConfigurationError: If file cannot be loaded
    """
    try:
        import yaml
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            
        if content is None:
            return {}
            
        return content
        
    except FileNotFoundError:
        raise ConfigurationError(f"Configuration file not found: {file_path}")
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {file_path}: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error loading {file_path}: {e}")


def safe_save_yaml_file(file_path: str, data: Dict[str, Any]) -> None:
    """
    Safely save data to YAML file.
    
    Args:
        file_path: Path to save to
        data: Data to save
        
    Raises:
        ConfigurationError: If file cannot be saved
    """
    try:
        import yaml
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, indent=2)
            
    except Exception as e:
        raise ConfigurationError(f"Error saving {file_path}: {e}")


def detect_environment() -> str:
    """
    Detect current environment from environment variables.
    
    Returns:
        Environment name (dev, staging, prod, etc.)
    """
    return os.getenv('AIRFLOW_ENV', os.getenv('ENVIRONMENT', 'dev')).lower()


def setup_logger(name: str, level: str = 'INFO') -> logging.Logger:
    """
    Set up a standardized logger.
    
    Args:
        name: Logger name
        level: Log level
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, level.upper()))
    
    return logger


def validate_dag_id(dag_id: str) -> List[str]:
    """
    Validate DAG ID according to Airflow conventions.
    
    Args:
        dag_id: DAG ID to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    if not dag_id:
        errors.append("DAG ID cannot be empty")
        return errors
    
    # Check length
    if len(dag_id) > 250:
        errors.append("DAG ID too long (max 250 characters)")
    
    # Check characters
    if not re.match(r'^[a-zA-Z0-9._-]+$', dag_id):
        errors.append("DAG ID contains invalid characters (use only letters, numbers, dots, underscores, hyphens)")
    
    # Check it doesn't start with number
    if dag_id[0].isdigit():
        errors.append("DAG ID cannot start with a number")
    
    return errors


def get_file_extension(file_path: str) -> str:
    """Get file extension in lowercase."""
    return os.path.splitext(file_path)[1].lower()


def is_config_file(file_path: str) -> bool:
    """Check if file is a configuration file."""
    return get_file_extension(file_path) in ['.yaml', '.yml', '.json']


def is_template_file(file_path: str) -> bool:
    """Check if file is a template file."""
    return get_file_extension(file_path) in ['.yaml', '.yml']


# Common constants
DEFAULT_DAG_ARGS = {
    'owner': 'dag-factory',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': 300  # 5 minutes in seconds
}

SUPPORTED_OPERATORS = {
    'dummy', 'bash', 'python', 'email', 'sql', 'sensor'
}

DAG_ID_PREFIXES = [
    'etl_', 'ml_', 'reporting_', 'data_quality_', 'monitoring_'
]

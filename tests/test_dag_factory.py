"""
Tests for DAG Factory implementation.
Run with: pytest test_dag_factory.py -v
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from datetime import datetime

from src.dag_factory import (
    DAGFactory, 
    ConfigurationValidator, 
    OperatorRegistry, 
    TaskBuilder,
    ConfigurationError,
    DAGFactoryError,
    ValidationResult
)

class TestOperatorRegistry:
    
    def test_register_and_get_operator(self):
        """Test operator registration and retrieval."""
        registry = OperatorRegistry()
        
        # Test built-in operator
        dummy_class = registry.get_operator_class('dummy')
        assert dummy_class.__name__ == 'DummyOperator'
        
        # Test custom operator registration
        from airflow.operators.bash import BashOperator
        registry.register_operator('custom_bash', BashOperator, ['bash_command'])
        
        custom_class = registry.get_operator_class('custom_bash')
        assert custom_class == BashOperator
    
    def test_validate_operator_params(self):
        """Test operator parameter validation."""
        registry = OperatorRegistry()
        
        # Valid parameters
        result = registry.validate_operator_params('bash', {'bash_command': 'echo hello'})
        assert result.is_valid
        
        # Missing required parameter
        result = registry.validate_operator_params('bash', {})
        assert not result.is_valid
        assert 'Missing required parameter' in result.errors[0]

class TestConfigurationValidator:
    
    def test_valid_configuration(self):
        """Test validation of valid configuration."""
        registry = OperatorRegistry()
        validator = ConfigurationValidator(registry)
        
        config = {
            "dag_id": "test_dag",
            "schedule": "@daily",
            "tasks": [
                {
                    "task_id": "test_task",
                    "operator": "dummy",
                    "parameters": {}
                }
            ]
        }
        
        result = validator.validate_config(config)
        assert result.is_valid
    
    def test_invalid_configuration(self):
        """Test validation of invalid configuration."""
        registry = OperatorRegistry()
        validator = ConfigurationValidator(registry)
        
        # Missing required fields
        config = {
            "dag_id": "test_dag"
            # Missing schedule and tasks
        }
        
        result = validator.validate_config(config)
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        registry = OperatorRegistry()
        validator = ConfigurationValidator(registry)
        
        config = {
            "dag_id": "test_dag",
            "schedule": "@daily",
            "tasks": [
                {
                    "task_id": "task1",
                    "operator": "dummy",
                    "depends_on": ["task2"],
                    "parameters": {}
                },
                {
                    "task_id": "task2", 
                    "operator": "dummy",
                    "depends_on": ["task1"],
                    "parameters": {}
                }
            ]
        }
        
        result = validator.validate_config(config)
        assert not result.is_valid
        assert any("Circular dependencies" in error for error in result.errors)

class TestDAGFactory:
    
    def test_load_yaml_config(self):
        """Test loading YAML configuration file."""
        config_data = {
            "dag_id": "test_yaml_dag",
            "schedule": "@daily",
            "tasks": [
                {
                    "task_id": "test_task",
                    "operator": "dummy",
                    "parameters": {}
                }
            ]
        }
        
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        factory = DAGFactory()
        loaded_config = factory.load_config(temp_path)
        
        assert loaded_config['dag_id'] == 'test_yaml_dag'
        assert len(loaded_config['tasks']) == 1
        
        # Cleanup
        Path(temp_path).unlink()
    
    def test_environment_variable_substitution(self):
        """Test environment variable substitution."""
        import os
        
        # Set test environment variable
        os.environ['TEST_VAR'] = 'test_value'
        
        config_data = {
            "dag_id": "test_env_dag",
            "schedule": "@daily",
            "owner": "${TEST_VAR}",
            "tasks": [
                {
                    "task_id": "test_task",
                    "operator": "bash",
                    "parameters": {
                        "bash_command": "echo ${TEST_VAR:-default}"
                    }
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        factory = DAGFactory()
        loaded_config = factory.load_config(temp_path)
        
        assert loaded_config['owner'] == 'test_value'
        assert 'test_value' in loaded_config['tasks'][0]['parameters']['bash_command']
        
        # Cleanup
        Path(temp_path).unlink()
        del os.environ['TEST_VAR']
    
    def test_dag_creation(self):
        """Test DAG creation from configuration."""
        config = {
            "dag_id": "test_create_dag",
            "description": "Test DAG creation",
            "schedule": "@daily",
            "start_date": "2024-01-01",
            "owner": "test",
            "tasks": [
                {
                    "task_id": "start",
                    "operator": "dummy",
                    "parameters": {}
                },
                {
                    "task_id": "end",
                    "operator": "dummy", 
                    "depends_on": ["start"],
                    "parameters": {}
                }
            ]
        }
        
        factory = DAGFactory()
        dag = factory.create_dag(config)
        
        assert dag.dag_id == 'test_create_dag'
        assert dag.description == 'Test DAG creation'
        assert len(dag.tasks) == 2
        
        # Check dependencies
        start_task = next(task for task in dag.tasks if task.task_id == 'start')
        end_task = next(task for task in dag.tasks if task.task_id == 'end')
        
        assert len(start_task.downstream_task_ids) == 1
        assert 'end' in start_task.downstream_task_ids
        assert len(end_task.upstream_task_ids) == 1
        assert 'start' in end_task.upstream_task_ids
    
    def test_metrics_tracking(self):
        """Test metrics tracking during DAG generation."""
        factory = DAGFactory()
        
        config = {
            "dag_id": "metrics_test_dag",
            "schedule": "@daily",
            "tasks": [{"task_id": "test", "operator": "dummy", "parameters": {}}]
        }
        
        # Generate DAG
        dag = factory.create_dag(config)
        
        # Check metrics
        metrics = factory.get_metrics()
        assert metrics['total_dags'] == 1
        assert metrics['successful_generations'] == 1
        assert metrics['failed_generations'] == 0
        assert metrics['success_rate'] == 1.0
        assert metrics['average_generation_time'] > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
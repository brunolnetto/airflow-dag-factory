# DAG Factory Security Guide and Best Practices

## Security Configuration

### 1. Secrets Management
```python
# Use Airflow's secret backends instead of plain text
from airflow.models import Variable
from airflow.hooks.base import BaseHook

# Instead of hardcoded values in YAML:
# password: "my_secret_password"

# Use Variable or Connection references:
# password: "{{ var.value.db_password }}"
# connection_id: "secure_postgres_conn"

# Or environment variables:
# password: "${DB_PASSWORD}"
```

### 2. Configuration File Security
```yaml
# Best practices for YAML configurations
dag_id: etl_secure_pipeline
owner: "{{ var.value.dag_owner }}"  # Use Variables
email: ["{{ var.value.alert_email }}"]

tasks:
  - task_id: secure_task
    operator: python
    parameters:
      python_callable: "dags.functions.secure.process_data"
      op_kwargs:
        # Never put secrets directly in config
        database_conn: "{{ conn.secure_db.get_uri() }}"
        api_key: "{{ var.value.api_key }}"
```

### 3. Access Control
```python
# Implement role-based access to configurations
class SecureDAGFactory(DAGFactory):
    def __init__(self, config_dir: str = 'dags/configs', user_role: str = None):
        super().__init__(config_dir)
        self.user_role = user_role
        
    def load_config(self, config_path):
        config = super().load_config(config_path)
        
        # Check if user has permission to create this DAG
        if not self._check_permission(config, self.user_role):
            raise ConfigurationError("Insufficient permissions")
            
        return config
    
    def _check_permission(self, config: dict, user_role: str) -> bool:
        # Implement your permission logic
        dag_tags = config.get('tags', [])
        
        # Example: only admin can create production DAGs
        if 'production' in dag_tags and user_role != 'admin':
            return False
            
        return True
```

### 4. Input Validation and Sanitization
```python
import re
from html import escape

class SecureConfigurationValidator(ConfigurationValidator):
    def validate_config(self, config: dict):
        result = super().validate_config(config)
        
        # Additional security validations
        self._validate_sql_injection(config, result)
        self._validate_command_injection(config, result)
        self._validate_path_traversal(config, result)
        
        return result
    
    def _validate_sql_injection(self, config: dict, result: ValidationResult):
        """Check for potential SQL injection in parameters."""
        dangerous_patterns = [
            r";\s*(drop|delete|truncate|update)\s+",
            r"union\s+select",
            r"'\s*or\s+'1'\s*=\s*'1'"
        ]
        
        for task in config.get('tasks', []):
            params = task.get('parameters', {})
            for key, value in params.items():
                if isinstance(value, str):
                    for pattern in dangerous_patterns:
                        if re.search(pattern, value, re.IGNORECASE):
                            result.errors.append(f"Potential SQL injection in task '{task['task_id']}', parameter '{key}'")
    
    def _validate_command_injection(self, config: dict, result: ValidationResult):
        """Check for potential command injection in bash commands."""
        dangerous_chars = [';', '|', '&', '#', '`', '$(', '${']
        
        for task in config.get('tasks', []):
            if task.get('operator') == 'bash':
                command = task.get('parameters', {}).get('bash_command', '')
                for char in dangerous_chars:
                    if char in command and not self._is_safe_usage(command, char):
                        result.warnings.append(f"Potentially unsafe bash command in task '{task['task_id']}'")
    
    def _is_safe_usage(self, command: str, char: str) -> bool:
        """Check if the usage of special characters is safe."""
        # Simple heuristic - in production, use more sophisticated analysis
        if char in ['$(', '${'] and 'var.value' in command:
            return True  # Airflow template usage
        return False
```

## Performance Optimization

### 1. DAG Parsing Performance
```python
# Optimize for large number of configurations
class OptimizedDAGFactory(DAGFactory):
    def __init__(self, config_dir: str = 'dags/configs'):
        super().__init__(config_dir)
        self._config_cache = {}
        self._cache_timestamps = {}
    
    def load_config(self, config_path):
        """Load config with caching for better performance."""
        config_path = Path(config_path)
        
        # Check cache
        if config_path in self._config_cache:
            cached_time = self._cache_timestamps.get(config_path, 0)
            file_time = config_path.stat().st_mtime
            
            if file_time <= cached_time:
                return self._config_cache[config_path]
        
        # Load and cache
        config = super().load_config(config_path)
        self._config_cache[config_path] = config
        self._cache_timestamps[config_path] = config_path.stat().st_mtime
        
        return config
```

### 2. Memory Optimization
```python
# For large deployments, implement lazy loading
class LazyDAGFactory(DAGFactory):
    def generate_dags_from_directory(self):
        """Generate DAGs lazily to reduce memory usage."""
        if not self.config_dir.exists():
            return []
        
        config_files = list(self.config_dir.glob('*.yaml'))
        
        # Process files in batches to avoid memory issues
        batch_size = 10
        for i in range(0, len(config_files), batch_size):
            batch = config_files[i:i + batch_size]
            
            for config_file in batch:
                try:
                    config = self.load_config(config_file)
                    dag = self.create_dag(config)
                    
                    # Yield DAG instead of storing all in memory
                    yield dag
                    
                except Exception as e:
                    self.logger.error(f"Failed to generate DAG from {config_file}: {str(e)}")
                    continue
```

## Error Handling and Logging

### 1. Comprehensive Error Reporting
```python
import traceback
from airflow.utils.email import send_email

class RobustDAGFactory(DAGFactory):
    def create_dag(self, config: dict):
        """Create DAG with comprehensive error handling."""
        try:
            return super().create_dag(config)
        except Exception as e:
            # Log detailed error information
            error_details = {
                'dag_id': config.get('dag_id', 'unknown'),
                'error_type': type(e).__name__,
                'error_message': str(e),
                'traceback': traceback.format_exc(),
                'config_summary': {
                    'task_count': len(config.get('tasks', [])),
                    'has_task_groups': bool(config.get('task_groups')),
                    'has_assets': bool(config.get('assets'))
                }
            }
            
            self.logger.error(f"DAG creation failed: {error_details}")
            
            # Send alert for critical errors
            self._send_error_alert(error_details)
            
            raise DAGFactoryError(f"Failed to create DAG {config.get('dag_id')}: {str(e)}")
    
    def _send_error_alert(self, error_details: dict):
        """Send error alert to operations team."""
        try:
            subject = f"DAG Factory Error: {error_details['dag_id']}"
            html_content = f"""
            <h3>DAG Factory Error Report</h3>
            <p><strong>DAG ID:</strong> {error_details['dag_id']}</p>
            <p><strong>Error:</strong> {error_details['error_message']}</p>
            <p><strong>Type:</strong> {error_details['error_type']}</p>
            <pre>{error_details['traceback']}</pre>
            """
            
            send_email(
                to=['data-ops@company.com'],
                subject=subject,
                html_content=html_content
            )
        except Exception as e:
            self.logger.error(f"Failed to send error alert: {str(e)}")
```

## Testing Strategy

### 1. Configuration Testing
```python
def test_all_configurations():
    """Test all configuration files for validity."""
    factory = DAGFactory()
    config_dir = Path('dags/configs')
    
    results = []
    for config_file in config_dir.glob('*.yaml'):
        try:
            config = factory.load_config(config_file)
            dag = factory.create_dag(config)
            results.append({
                'file': config_file.name,
                'status': 'success',
                'dag_id': dag.dag_id,
                'task_count': len(dag.tasks)
            })
        except Exception as e:
            results.append({
                'file': config_file.name,
                'status': 'failed',
                'error': str(e)
            })
    
    # Generate test report
    failed_configs = [r for r in results if r['status'] == 'failed']
    if failed_configs:
        print(f"❌ {len(failed_configs)} configuration(s) failed:")
        for config in failed_configs:
            print(f"  - {config['file']}: {config['error']}")
    else:
        print(f"✅ All {len(results)} configurations are valid")
    
    return results
```

### 2. Integration Testing
```python
def test_dag_execution():
    """Test actual DAG execution with test data."""
    from airflow.models import DagBag
    from airflow.utils.state import State
    
    dagbag = DagBag(dag_folder='dags', include_examples=False)
    
    # Test each factory-generated DAG
    for dag_id, dag in dagbag.dags.items():
        if 'generated' in dag.tags:
            print(f"Testing DAG: {dag_id}")
            
            # Create test DAG run
            dag_run = dag.create_dagrun(
                run_id=f'test_{int(time.time())}',
                execution_date=datetime.now(),
                state=State.RUNNING
            )
            
            # Test task creation and basic properties
            for task in dag.tasks:
                assert task.dag_id == dag_id
                assert task.task_id is not None
                assert task.owner is not None
                
            print(f"✅ DAG {dag_id} passed basic tests")
```
`

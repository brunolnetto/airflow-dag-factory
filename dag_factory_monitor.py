"""
Monitoring and alerting configuration for DAG Factory.
"""

import logging
from airflow.configuration import conf
from airflow.models import Variable
from prometheus_client import Counter, Histogram, Gauge
import time

# Prometheus metrics for monitoring
dag_generation_counter = Counter('dag_factory_generations_total', 
                                 'Total DAG generations', ['status'])
dag_generation_duration = Histogram('dag_factory_generation_duration_seconds',
                                   'DAG generation duration')
active_dags_gauge = Gauge('dag_factory_active_dags', 
                         'Number of active factory-generated DAGs')

class DAGFactoryMonitor:
    """Monitoring and alerting for DAG Factory operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def record_generation_metrics(self, status: str, duration: float):
        """Record DAG generation metrics."""
        dag_generation_counter.labels(status=status).inc()
        dag_generation_duration.observe(duration)
        
    def check_factory_health(self) -> dict:
        """Perform health check on DAG Factory system."""
        health_status = {
            'status': 'healthy',
            'checks': {
                'config_directory': self._check_config_directory(),
                'schema_validation': self._check_schema_validation(),
                'operator_registry': self._check_operator_registry(),
                'airflow_connectivity': self._check_airflow_connectivity()
            },
            'timestamp': time.time()
        }
        
        # Determine overall health
        failed_checks = [k for k, v in health_status['checks'].items() if not v['healthy']]
        if failed_checks:
            health_status['status'] = 'unhealthy'
            health_status['failed_checks'] = failed_checks
            
        return health_status
    
    def _check_config_directory(self) -> dict:
        """Check if configuration directory is accessible."""
        try:
            from pathlib import Path
            config_dir = Path(Variable.get('dag_factory_config_dir', 'dags/configs'))
            return {
                'healthy': config_dir.exists() and config_dir.is_dir(),
                'message': f'Config directory: {config_dir}',
                'details': {
                    'path': str(config_dir),
                    'exists': config_dir.exists(),
                    'is_directory': config_dir.is_dir() if config_dir.exists() else False
                }
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Config directory check failed: {str(e)}'
            }
    
    def _check_schema_validation(self) -> dict:
        """Check if schema validation is working."""
        try:
            from dag_factory import ConfigurationValidator, OperatorRegistry
            registry = OperatorRegistry()
            validator = ConfigurationValidator(registry)
            
            # Test with minimal valid config
            test_config = {
                'dag_id': 'health_check_dag',
                'schedule': '@daily',
                'tasks': [{
                    'task_id': 'health_check',
                    'operator': 'dummy',
                    'parameters': {}
                }]
            }
            
            result = validator.validate_config(test_config)
            return {
                'healthy': result.is_valid,
                'message': 'Schema validation working' if result.is_valid else f'Validation errors: {result.errors}',
                'details': {
                    'errors': result.errors,
                    'warnings': result.warnings
                }
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Schema validation check failed: {str(e)}'
            }
    
    def _check_operator_registry(self) -> dict:
        """Check operator registry functionality."""
        try:
            from dag_factory import OperatorRegistry
            registry = OperatorRegistry()
            
            # Test basic operators
            basic_operators = ['dummy', 'bash', 'python', 'email']
            working_operators = []
            
            for op_name in basic_operators:
                try:
                    op_class = registry.get_operator_class(op_name)
                    working_operators.append(op_name)
                except:
                    pass
            
            return {
                'healthy': len(working_operators) == len(basic_operators),
                'message': f'Operator registry: {len(working_operators)}/{len(basic_operators)} operators working',
                'details': {
                    'working_operators': working_operators,
                    'total_expected': len(basic_operators)
                }
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Operator registry check failed: {str(e)}'
            }
    
    def _check_airflow_connectivity(self) -> dict:
        """Check Airflow database connectivity."""
        try:
            from airflow.models import DagBag
            dagbag = DagBag(include_examples=False)
            
            return {
                'healthy': True,
                'message': f'Airflow connectivity OK - {len(dagbag.dags)} DAGs loaded',
                'details': {
                    'dag_count': len(dagbag.dags),
                    'import_errors': len(dagbag.import_errors)
                }
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Airflow connectivity check failed: {str(e)}'
            }

# Health check DAG
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta

def perform_health_check(**context):
    """Perform comprehensive health check."""
    monitor = DAGFactoryMonitor()
    health_status = monitor.check_factory_health()
    
    # Log results
    logger = logging.getLogger(__name__)
    logger.info(f"DAG Factory Health Check: {health_status['status']}")
    
    for check_name, check_result in health_status['checks'].items():
        if check_result['healthy']:
            logger.info(f"✅ {check_name}: {check_result['message']}")
        else:
            logger.error(f"❌ {check_name}: {check_result['message']}")
    
    # Fail the task if health check fails
    if health_status['status'] != 'healthy':
        raise Exception(f"Health check failed: {health_status['failed_checks']}")
    
    return health_status

# Health monitoring DAG
dag_factory_health_dag = DAG(
    'dag_factory_health_monitoring',
    description='Health monitoring for DAG Factory system',
    schedule_interval=timedelta(minutes=30),  # Check every 30 minutes
    start_date=days_ago(1),
    catchup=False,
    default_args={
        'owner': 'data-engineering',
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
        'email_on_failure': True,
        'email': ['data-team@company.com']
    },
    tags=['monitoring', 'dag-factory', 'health-check']
)

health_check_task = PythonOperator(
    task_id='perform_health_check',
    python_callable=perform_health_check,
    dag=dag_factory_health_dag
)
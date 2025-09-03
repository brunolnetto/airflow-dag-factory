"""
DAG Factory - Apache Airflow DAG Factory Implementation

A production-ready solution for generating standardized DAGs from YAML configurations
with template inheritance, environment overrides, and security features.
"""

__version__ = "1.0.0"
__author__ = "Bruno Peixoto"
__email__ = "bruno@example.com"

# Import main classes for easy access
from .dag_factory import DAGFactory
from .utils import ConfigurationError, DAGFactoryBaseError
from .managers.template import TemplateManager, ConfigurationComposer
from .managers.security import SecurityManager, AccessLevel, AuditAction

__all__ = [
    "DAGFactory",
    "ConfigurationError", 
    "DAGFactoryBaseError",
    "TemplateManager",
    "ConfigurationComposer", 
    "SecurityManager",
    "AccessLevel",
    "AuditAction"
]
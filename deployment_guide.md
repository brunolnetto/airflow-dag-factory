# DAG Factory Deployment Guide

## Directory Structure
```
airflow/
├── dags/
│   ├── dag_factory.py                 # Main factory implementation
│   ├── configs/                       # Configuration files
│   │   ├── etl_user_data.yaml
│   │   ├── ml_model_training.yaml
│   │   └── data_quality_checks.yaml
│   ├── functions/                     # Custom functions
│   │   ├── __init__.py
│   │   ├── etl.py
│   │   ├── ml.py
│   │   ├── data_validation.py
│   │   └── data_quality.py
│   ├── scripts/                       # Utility scripts
│   │   ├── validate_config.py
│   │   ├── generate_dag.py
│   │   └── schema_validator.py
│   └── schemas/                       # Data schemas
│       ├── user_schema.json
│       └── transaction_schema.json
├── config/                           # Airflow configuration
│   └── airflow.cfg
└── requirements.txt                  # Python dependencies
```

## Installation Steps

### 1. Install Dependencies
```bash
pip install apache-airflow[postgres,s3,crypto]==2.8.0
pip install jsonschema==4.17.3
pip install jinja2==3.1.2
pip install pyyaml==6.0
pip install pytest==7.4.0  # For testing
```

### 2. Environment Variables
```bash
# Required environment variables
export AIRFLOW_HOME=/path/to/airflow
export AIRFLOW__CORE__DAGS_FOLDER=/path/to/airflow/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False

# Optional: Custom configuration paths  
export DAG_FACTORY_CONFIG_DIR=/path/to/configs
export DAG_FACTORY_FUNCTIONS_DIR=/path/to/functions

# For data sources
export POSTGRES_CONN_ID=postgres_default
export REDSHIFT_CONN_ID=redshift_default
export S3_CONN_ID=s3_default
```

### 3. Airflow Configuration Updates

Add to airflow.cfg:
```ini
[core]
# Enable DAG Factory parsing
dagbag_import_timeout = 300
dag_file_processor_timeout = 300

# Performance optimization
max_active_runs_per_dag = 1
parallelism = 16
dag_concurrency = 16

[scheduler]
# Increase parsing performance
dag_dir_list_interval = 300
```

### 4. Database Connections Setup

```python
# Add via Airflow UI or CLI
airflow connections add 'postgres_default' \\
    --conn-type 'postgres' \\
    --conn-host 'localhost' \\
    --conn-schema 'airflow' \\
    --conn-login 'airflow' \\
    --conn-password 'password'

airflow connections add 'redshift_default' \\
    --conn-type 'redshift' \\
    --conn-host 'cluster.region.redshift.amazonaws.com' \\
    --conn-schema 'dev' \\
    --conn-login 'username' \\
    --conn-password 'password'
```
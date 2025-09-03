"""
Example custom functions for DAG Factory.
Place this in dags/functions/ directory.
"""

import logging
import pandas as pd
from typing import Dict, Any, List
from airflow.hooks.postgres_hook import PostgresHook
from airflow.hooks.S3_hook import S3Hook
from airflow.models import Variable

logger = logging.getLogger(__name__)

# ================================
# ETL Functions
# ================================

def extract_user_data(**context) -> Dict[str, Any]:
    """Extract user data from PostgreSQL."""
    query = context['params']['query']
    connection_id = context['params']['connection_id']
    
    pg_hook = PostgresHook(postgres_conn_id=connection_id)
    
    # Execute query and get results
    df = pg_hook.get_pandas_df(query)
    
    logger.info(f"Extracted {len(df)} user records")
    
    # Store data in XCom (for small datasets) or temporary storage
    temp_path = f"/tmp/users_{context['ds_nodash']}.parquet"
    df.to_parquet(temp_path)
    
    return {
        "record_count": len(df),
        "temp_path": temp_path,
        "columns": list(df.columns)
    }

def transform_user_data(**context) -> Dict[str, Any]:
    """Transform user data with specified transformations."""
    task_instance = context['ti']
    extract_result = task_instance.xcom_pull(task_ids='extract_users')
    
    transformations = context['params']['transformations']
    output_format = context['params']['output_format']
    
    # Load data from temporary storage
    df = pd.read_parquet(extract_result['temp_path'])
    
    # Apply transformations
    for transformation in transformations:
        if transformation == 'clean_email':
            df['email'] = df['email'].str.lower().str.strip()
        elif transformation == 'normalize_phone':
            df['phone'] = df['phone'].str.replace(r'[^0-9]', '', regex=True)
        elif transformation == 'calculate_age':
            df['age'] = (pd.Timestamp.now() - pd.to_datetime(df['birth_date'])).dt.days // 365
    
    # Save transformed data
    output_path = f"/tmp/users_transformed_{context['ds_nodash']}.{output_format}"
    
    if output_format == 'parquet':
        df.to_parquet(output_path)
    elif output_format == 'csv':
        df.to_csv(output_path, index=False)
    
    logger.info(f"Transformed {len(df)} records with transformations: {transformations}")
    
    return {
        "record_count": len(df),
        "output_path": output_path,
        "transformations_applied": transformations
    }

def load_data_to_warehouse(**context) -> Dict[str, Any]:
    """Load data to data warehouse."""
    task_instance = context['ti']
    transform_result = task_instance.xcom_pull(task_ids='transform_users')
    
    destination = context['params']['destination']
    table = context['params']['table']
    connection_id = context['params']['connection_id']
    write_mode = context['params']['write_mode']
    
    # Load transformed data
    df = pd.read_parquet(transform_result['output_path'])
    
    if destination == 'redshift':
        # Use appropriate hook for Redshift
        from airflow.providers.amazon.aws.hooks.redshift_sql import RedshiftSQLHook
        hook = RedshiftSQLHook(redshift_conn_id=connection_id)
        
        # Insert data (simplified - in production, use COPY command)
        hook.insert_rows(table, df.values.tolist(), target_fields=df.columns.tolist())
    
    elif destination == 'postgresql':
        pg_hook = PostgresHook(postgres_conn_id=connection_id)
        pg_hook.insert_rows(table, df.values.tolist(), target_fields=df.columns.tolist())
    
    logger.info(f"Loaded {len(df)} records to {destination}.{table}")
    
    return {
        "record_count": len(df),
        "destination": destination,
        "table": table,
        "write_mode": write_mode
    }

# ================================
# Data Validation Functions
# ================================

def validate_raw_data(**context) -> Dict[str, Any]:
    """Validate raw data quality."""
    data_path = context['params']['data_path']
    validation_rules = context['params']['validation_rules']
    
    # For S3 data
    if data_path.startswith('s3://'):
        s3_hook = S3Hook()
        # Implementation would depend on data format and validation rules
        # This is a simplified example
        
        logger.info(f"Validating data at {data_path} with {validation_rules} rules")
        
        # Simulate validation results
        validation_results = {
            "total_files": 5,
            "valid_files": 5,
            "validation_errors": [],
            "data_quality_score": 0.98
        }
        
        if validation_results["data_quality_score"] < 0.95:
            raise ValueError(f"Data quality score {validation_results['data_quality_score']} below threshold")
    
    return validation_results

# ================================
# ML Functions
# ================================

def load_feature_data(**context) -> Dict[str, Any]:
    """Load feature data from feature store."""
    feature_store_path = context['params']['feature_store_path']
    date_range_days = context['params']['date_range_days']
    features = context['params']['features']
    
    logger.info(f"Loading features: {features} for {date_range_days} days")
    
    # Simulate feature loading
    # In production, this would connect to your feature store
    feature_data = {
        "feature_count": len(features) * 100,  # 100 features per category
        "sample_count": 10000,
        "feature_store_path": feature_store_path,
        "loaded_features": features
    }
    
    return feature_data

def train_churn_model(**context) -> Dict[str, Any]:
    """Train customer churn prediction model."""
    model_type = context['params']['model_type']
    hyperparameters = context['params']['hyperparameters']
    cv_folds = context['params']['cross_validation_folds']
    
    logger.info(f"Training {model_type} model with hyperparameters: {hyperparameters}")
    
    # Simulate model training
    # In production, this would use your ML framework (scikit-learn, xgboost, etc.)
    training_results = {
        "model_type": model_type,
        "hyperparameters": hyperparameters,
        "cv_score": 0.87,
        "training_time_minutes": 45,
        "feature_importance": {
            "total_purchases": 0.35,
            "days_since_last_purchase": 0.28,
            "average_order_value": 0.22,
            "customer_service_calls": 0.15
        }
    }
    
    return training_results

# ================================
# Data Quality Functions
# ================================

def check_completeness(**context) -> Dict[str, Any]:
    """Check data completeness."""
    table = context['params']['table']
    required_columns = context['params']['required_columns']
    threshold = context['params']['completeness_threshold']
    
    # Simulate completeness check
    completeness_results = {}
    overall_score = 0.0
    
    for column in required_columns:
        # Simulate column completeness
        completeness = 0.96 if column != 'email' else 0.94  # Email has some missing values
        completeness_results[column] = completeness
        overall_score += completeness
    
    overall_score = overall_score / len(required_columns)
    
    logger.info(f"Completeness check for {table}: {overall_score:.3f}")
    
    if overall_score < threshold:
        raise ValueError(f"Completeness score {overall_score:.3f} below threshold {threshold}")
    
    return {
        "table": table,
        "overall_score": overall_score,
        "column_scores": completeness_results,
        "threshold": threshold,
        "status": "PASSED"
    }

def check_data_freshness(**context) -> Dict[str, Any]:
    """Check if data is fresh enough."""
    table = context['params']['table']
    timestamp_column = context['params']['timestamp_column']
    max_age_hours = context['params']['max_age_hours']
    
    # Simulate freshness check
    from datetime import datetime, timedelta
    
    latest_timestamp = datetime.now() - timedelta(hours=2)  # 2 hours old
    age_hours = 2
    
    logger.info(f"Data freshness check for {table}: {age_hours} hours old")
    
    if age_hours > max_age_hours:
        raise ValueError(f"Data is {age_hours} hours old, exceeds threshold of {max_age_hours} hours")
    
    return {
        "table": table,
        "latest_timestamp": latest_timestamp.isoformat(),
        "age_hours": age_hours,
        "max_age_hours": max_age_hours,
        "status": "FRESH"
    }
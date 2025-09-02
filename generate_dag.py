#!/usr/bin/env python3
"""
DAG Generator CLI tool for testing configuration outside Airflow.
Usage: python generate_dag.py path/to/config.yaml
"""

import argparse
import json
from pathlib import Path
from dag_factory import DAGFactory, ConfigurationError, DAGFactoryError

def main():
    parser = argparse.ArgumentParser(description="Generate DAG from configuration")
    parser.add_argument("config_file", help="Path to configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't generate")
    parser.add_argument("--output", "-o", help="Output file for DAG metadata")
    parser.add_argument("--metrics", action="store_true", help="Show generation metrics")
    
    args = parser.parse_args()
    
    factory = DAGFactory()
    
    try:
        # Load and validate configuration
        config = factory.load_config(args.config_file)
        print(f"✅ Configuration loaded: {config['dag_id']}")
        
        if args.dry_run:
            print("✅ Dry run successful - configuration is valid")
            return
        
        # Generate DAG
        dag = factory.create_dag(config)
        print(f"✅ DAG generated successfully: {dag.dag_id}")
        
        # Extract DAG metadata
        metadata = {
            "dag_id": dag.dag_id,
            "description": dag.description,
            "schedule_interval": str(dag.schedule_interval),
            "start_date": dag.start_date.isoformat() if dag.start_date else None,
            "catchup": dag.catchup,
            "max_active_runs": dag.max_active_runs,
            "tags": dag.tags,
            "task_count": len(dag.tasks),
            "task_ids": [task.task_id for task in dag.tasks]
        }
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"📄 Metadata written to: {args.output}")
        else:
            print("📊 DAG Metadata:")
            print(json.dumps(metadata, indent=2))
        
        # Show metrics if requested
        if args.metrics:
            metrics = factory.get_metrics()
            print("📈 Generation Metrics:")
            print(json.dumps(metrics, indent=2))
        
    except (ConfigurationError, DAGFactoryError) as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
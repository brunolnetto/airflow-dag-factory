#!/usr/bin/env python3
"""
Configuration validation utility for DAG Factory.
Usage: python validate_config.py path/to/config.yaml
"""

import sys
import argparse
from pathlib import Path
from dag_factory import DAGFactory, ConfigurationError

def main():
    parser = argparse.ArgumentParser(description="Validate DAG Factory configuration")
    parser.add_argument("config_file", help="Path to configuration file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    factory = DAGFactory()
    
    try:
        config = factory.load_config(args.config_file)
        print(f"✅ Configuration {args.config_file} is valid")
        
        if args.verbose:
            print(f"DAG ID: {config['dag_id']}")
            print(f"Schedule: {config.get('schedule', 'Not specified')}")
            print(f"Tasks: {len(config.get('tasks', []))}")
            
            if 'task_groups' in config:
                print(f"Task Groups: {len(config['task_groups'])}")
            
            if 'assets' in config:
                consumes = len(config['assets'].get('consumes', []))
                produces = len(config['assets'].get('produces', []))
                print(f"Assets - Consumes: {consumes}, Produces: {produces}")
        
    except ConfigurationError as e:
        print(f"❌ Configuration validation failed:")
        print(f"   {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
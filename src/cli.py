#!/usr/bin/env python3
"""
Enhanced DAG Factory CLI with template inheritance, environment overrides, and security features.
Usage: python enhanced_dag_factory_cli.py [command] [options]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from .dag_factory import DAGFactory
from .utils import ConfigurationError, DAGFactoryBaseError as DAGFactoryError, setup_logger
from .managers.template import TemplateManager, ConfigurationComposer
from .managers.security import SecurityManager, AccessLevel, AuditAction
from .self_service_ui import create_app


def setup_logging():
    """Setup logging configuration."""
    return setup_logger(__name__)


def validate_command(args):
    """Validate configuration with enhanced features."""
    try:
        factory = DAGFactory(
            config_dir=args.config_dir,
            templates_dir=args.templates_dir,
            enable_security=args.enable_security
        )
        
        config = factory.load_config(
            args.config_file, 
            username=args.username,
            environment=args.environment
        )
        
        print(f"✅ Configuration '{args.config_file}' is valid")
        
        if args.verbose:
            print(f"DAG ID: {config['dag_id']}")
            print(f"Schedule: {config.get('schedule', 'Not specified')}")
            print(f"Tasks: {len(config.get('tasks', []))}")
            
            if 'template' in config:
                template_info = config['template']
                if 'extends' in template_info:
                    print(f"Template: {template_info['extends']}")
            
            if args.environment:
                print(f"Environment: {args.environment}")
            
            if 'task_groups' in config:
                print(f"Task Groups: {len(config['task_groups'])}")
            
            if 'assets' in config:
                consumes = len(config['assets'].get('consumes', []))
                produces = len(config['assets'].get('produces', []))
                print(f"Assets - Consumes: {consumes}, Produces: {produces}")
        
        return True
        
    except (ConfigurationError, DAGFactoryError) as e:
        print(f"❌ Configuration validation failed:")
        print(f"   {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False


def generate_command(args):
    """Generate DAG with enhanced features."""
    try:
        factory = DAGFactory(
            config_dir=args.config_dir,
            templates_dir=args.templates_dir,
            enable_security=args.enable_security
        )
        
        # Load and validate configuration
        config = factory.load_config(
            args.config_file,
            username=args.username,
            environment=args.environment
        )
        print(f"✅ Configuration loaded: {config['dag_id']}")
        
        if args.dry_run:
            print("✅ Dry run successful - configuration is valid")
            return True
        
        # Generate DAG (only if Airflow is available)
        try:
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
                "task_ids": [task.task_id for task in dag.tasks],
                "template_used": config.get('template', {}).get('extends'),
                "environment": args.environment
            }
            
        except Exception as e:
            # If Airflow isn't available, create metadata from config
            print(f"⚠️  Airflow not available, creating metadata from config")
            metadata = {
                "dag_id": config['dag_id'],
                "description": config.get('description', ''),
                "schedule_interval": config.get('schedule', '@daily'),
                "start_date": config.get('start_date'),
                "catchup": config.get('catchup', False),
                "max_active_runs": config.get('max_active_runs', 1),
                "tags": config.get('tags', []),
                "task_count": len(config.get('tasks', [])),
                "task_ids": [task['task_id'] for task in config.get('tasks', [])],
                "template_used": config.get('template', {}).get('extends'),
                "environment": args.environment
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
        
        return True
        
    except (ConfigurationError, DAGFactoryError) as e:
        print(f"❌ Error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False


def list_templates_command(args):
    """List available templates."""
    try:
        template_manager = TemplateManager(args.templates_dir)
        templates = template_manager.list_available_templates()
        
        if not templates:
            print("No templates found")
            return True
        
        print(f"📋 Available Templates ({len(templates)}):")
        print("-" * 40)
        
        for template_name in templates:
            try:
                template = template_manager.load_template(template_name)
                description = template.get('description', 'No description')
                tags = template.get('tags', [])
                
                print(f"• {template_name}")
                print(f"  Description: {description}")
                if tags:
                    print(f"  Tags: {', '.join(tags)}")
                
                if args.verbose:
                    extends = template.get('template', {}).get('extends')
                    if extends:
                        print(f"  Extends: {extends}")
                    
                    if 'parameters' in template:
                        param_count = len(template['parameters'])
                        print(f"  Parameters: {param_count}")
                
                print()
                
            except Exception as e:
                print(f"• {template_name} (Error loading: {str(e)})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error listing templates: {str(e)}")
        return False


def security_command(args):
    """Security management commands."""
    try:
        security_manager = SecurityManager()
        
        if args.security_action == 'list-users':
            # List users and their permissions
            roles_config = security_manager.access_control.roles_config
            users = roles_config.get('users', {})
            
            print(f"👥 Users ({len(users)}):")
            print("-" * 50)
            
            for username, user_config in users.items():
                roles = user_config.get('roles', [])
                email = user_config.get('email', 'N/A')
                department = user_config.get('department', 'N/A')
                
                user_info = security_manager.get_user_permissions(username)
                permissions = user_info['permissions']
                
                print(f"• {username}")
                print(f"  Email: {email}")
                print(f"  Department: {department}")
                print(f"  Roles: {', '.join(roles)}")
                print(f"  Permissions: {', '.join(permissions)}")
                print()
        
        elif args.security_action == 'check-access':
            if not args.username or not args.operation:
                print("❌ Username and operation required for access check")
                return False
            
            has_access = security_manager.validate_user_access(
                args.username, args.operation, args.resource
            )
            
            if has_access:
                print(f"✅ User '{args.username}' has '{args.operation}' access")
            else:
                print(f"❌ User '{args.username}' does NOT have '{args.operation}' access")
        
        elif args.security_action == 'audit-logs':
            logs = security_manager.audit_logger.get_audit_logs(
                user=args.username,
                limit=args.limit or 20
            )
            
            print(f"📋 Audit Logs ({len(logs)} entries):")
            print("-" * 80)
            
            for log in logs:
                timestamp = log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                status = "✅" if log.success else "❌"
                
                print(f"{status} {timestamp} | {log.user} | {log.action.value} | {log.resource}")
                if log.details:
                    print(f"    Details: {log.details}")
        
        return True
        
    except Exception as e:
        print(f"❌ Security error: {str(e)}")
        return False


def ui_command(args):
    """Start the self-service UI."""
    if not UI_AVAILABLE:
        print("❌ Self-service UI not available. Install Flask with: pip install flask")
        return False
        
    try:
        print("🚀 Starting DAG Factory Self-Service UI...")
        print(f"   Configuration directory: {args.config_dir}")
        print(f"   Templates directory: {args.templates_dir}")
        print(f"   Web interface: http://localhost:{args.port}")
        print("   Press Ctrl+C to stop")
        
        app = create_app(args.config_dir)
        app.run(debug=args.debug, host='0.0.0.0', port=args.port)
        
    except KeyboardInterrupt:
        print("\n👋 Stopping DAG Factory UI")
    except Exception as e:
        print(f"❌ UI error: {str(e)}")
        return False


def main():
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Enhanced DAG Factory CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Common arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument('--config-dir', default='dags/configs', 
                              help='Configuration directory')
    common_parser.add_argument('--templates-dir', default='dags/templates',
                              help='Templates directory')
    common_parser.add_argument('--enable-security', action='store_true',
                              help='Enable security features')
    common_parser.add_argument('--username', help='Username for security context')
    common_parser.add_argument('--environment', choices=['dev', 'staging', 'prod'],
                              help='Target environment')
    common_parser.add_argument('--verbose', '-v', action='store_true',
                              help='Verbose output')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', parents=[common_parser],
                                           help='Validate configuration')
    validate_parser.add_argument('config_file', help='Configuration file to validate')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', parents=[common_parser],
                                           help='Generate DAG from configuration')
    generate_parser.add_argument('config_file', help='Configuration file')
    generate_parser.add_argument('--dry-run', action='store_true',
                                help='Validate only, don\'t generate')
    generate_parser.add_argument('--output', '-o', help='Output file for metadata')
    generate_parser.add_argument('--metrics', action='store_true',
                                help='Show generation metrics')
    
    # List templates command
    templates_parser = subparsers.add_parser('list-templates', parents=[common_parser],
                                            help='List available templates')
    
    # Security command
    security_parser = subparsers.add_parser('security', parents=[common_parser],
                                           help='Security management')
    security_parser.add_argument('security_action', 
                                choices=['list-users', 'check-access', 'audit-logs'],
                                help='Security action to perform')
    security_parser.add_argument('--operation', help='Operation to check access for')
    security_parser.add_argument('--resource', help='Resource for access check')
    security_parser.add_argument('--limit', type=int, help='Limit for audit logs')
    
    # UI command
    ui_parser = subparsers.add_parser('ui', parents=[common_parser],
                                     help='Start self-service UI')
    ui_parser.add_argument('--port', type=int, default=5000, help='Port for web interface')
    ui_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    success = False
    
    if args.command == 'validate':
        success = validate_command(args)
    elif args.command == 'generate':
        success = generate_command(args)
    elif args.command == 'list-templates':
        success = list_templates_command(args)
    elif args.command == 'security':
        success = security_command(args)
    elif args.command == 'ui':
        success = ui_command(args)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

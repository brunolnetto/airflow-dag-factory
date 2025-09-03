"""
Template inheritance and environment configuration management for DAG Factory.
"""

"""
Template inheritance and environment configuration management for DAG Factory.
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod

try:
    import yaml
except ImportError:
    yaml = None

from ..utils import (
    logger, TemplateInheritanceError, deep_merge_dicts, 
    set_nested_value, safe_load_yaml_file, detect_environment
)


@dataclass
class TemplateConfig:
    """Configuration for template inheritance."""
    name: str
    path: Path
    extends: Optional[str] = None
    overrides: Optional[Dict[str, Any]] = None


class TemplateManager:
    """Manages template inheritance and composition."""
    
    def __init__(self, templates_dir: str = 'dags/templates'):
        self.templates_dir = Path(templates_dir)
        self._template_cache = {}
        self._inheritance_graph = {}
        
    def load_template(self, template_name: str) -> Dict[str, Any]:
        """Load a template with inheritance resolution."""
        if template_name in self._template_cache:
            return self._template_cache[template_name]
        
        template_path = self.templates_dir / f"{template_name}.yaml"
        if not template_path.exists():
            template_path = self.templates_dir / f"{template_name}.yml"
        
        if not template_path.exists():
            raise TemplateInheritanceError(f"Template '{template_name}' not found in {self.templates_dir}")
        
        try:
            with open(template_path, 'r') as f:
                template_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise TemplateInheritanceError(f"Failed to parse template '{template_name}': {str(e)}")
        
        # Resolve inheritance
        resolved_template = self._resolve_inheritance(template_name, template_config)
        self._template_cache[template_name] = resolved_template
        
        return resolved_template
    
    def _resolve_inheritance(self, template_name: str, template_config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve template inheritance chain."""
        # Check for circular dependencies
        if template_name in self._inheritance_graph:
            raise TemplateInheritanceError(f"Circular dependency detected for template '{template_name}'")
        
        self._inheritance_graph[template_name] = True
        
        try:
            template_meta = template_config.get('template', {})
            extends = template_meta.get('extends')
            
            if extends:
                # Load parent template
                parent_template = self.load_template(extends)
                
                # Deep merge parent with current template
                merged_template = deep_merge_dicts(parent_template, template_config, 
                                                 merge_lists=True, skip_keys=['template'])
                
                # Apply overrides if specified
                overrides = template_meta.get('overrides', {})
                if overrides:
                    merged_template = self._apply_overrides(merged_template, overrides)
                
                return merged_template
            
            return template_config
            
        finally:
            # Remove from inheritance graph
            self._inheritance_graph.pop(template_name, None)
    
    def _apply_overrides(self, template: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Apply specific overrides to template."""
        import copy
        result = copy.deepcopy(template)
        
        for key_path, value in overrides.items():
            set_nested_value(result, key_path, value)
        
        return result
    
    def list_available_templates(self) -> List[str]:
        """List all available templates."""
        templates = []
        if self.templates_dir.exists():
            for file_path in self.templates_dir.glob('*.yaml'):
                templates.append(file_path.stem)
            for file_path in self.templates_dir.glob('*.yml'):
                templates.append(file_path.stem)
        return templates
    
    def validate_template(self, template_name: str) -> bool:
        """Validate a template can be loaded without errors."""
        try:
            self.load_template(template_name)
            return True
        except TemplateInheritanceError:
            return False


class EnvironmentManager:
    """Manages environment-specific configuration overrides."""
    
    def __init__(self):
        self.current_environment = detect_environment()
    
    def apply_environment_overrides(self, config: Dict[str, Any], target_env: Optional[str] = None) -> Dict[str, Any]:
        """Apply environment-specific overrides to configuration."""
        import copy
        environment = target_env or self.current_environment
        
        if 'environments' not in config:
            return config
        
        env_overrides = config['environments'].get(environment, {})
        if not env_overrides:
            logger.warning(f"No environment overrides found for '{environment}'")
            return config
        
        # Remove environments section from final config
        result = copy.deepcopy(config)
        result.pop('environments', None)
        
        # Apply environment-specific overrides (lists are replaced, not merged)
        result = deep_merge_dicts(result, env_overrides, merge_lists=False)
        
        logger.info(f"Applied environment overrides for '{environment}'")
        return result
    
    def get_environment_config(self, config: Dict[str, Any], environment: str) -> Dict[str, Any]:
        """Get configuration for specific environment."""
        return self.apply_environment_overrides(config, environment)
    
    def validate_environment_config(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate all environment configurations."""
        errors = {}
        
        if 'environments' not in config:
            return errors
        
        for env_name, env_config in config['environments'].items():
            env_errors = []
            
            # Validate environment-specific config
            try:
                merged_config = self.apply_environment_overrides(config, env_name)
                # Additional validation can be added here
            except Exception as e:
                env_errors.append(f"Failed to apply environment overrides: {str(e)}")
            
            if env_errors:
                errors[env_name] = env_errors
        
        return errors


class ConfigurationComposer:
    """Composes final configuration from templates and environment overrides."""
    
    def __init__(self, templates_dir: str = 'dags/templates'):
        self.template_manager = TemplateManager(templates_dir)
        self.environment_manager = EnvironmentManager()
    
    def compose_configuration(self, config: Dict[str, Any], environment: Optional[str] = None) -> Dict[str, Any]:
        """Compose final configuration with template inheritance and environment overrides."""
        # Step 1: Apply template inheritance
        if 'template' in config and 'extends' in config['template']:
            template_name = config['template']['extends']
            logger.info(f"Applying template inheritance from '{template_name}'")
            
            base_template = self.template_manager.load_template(template_name)
            config = deep_merge_dicts(base_template, config, merge_lists=True, skip_keys=['template'])
        
        # Step 2: Apply environment overrides
        config = self.environment_manager.apply_environment_overrides(config, environment)
        
        return config
    
    def validate_composition(self, config: Dict[str, Any]) -> List[str]:
        """Validate the entire composition process."""
        errors = []
        
        # Validate template inheritance
        if 'template' in config and 'extends' in config['template']:
            template_name = config['template']['extends']
            if not self.template_manager.validate_template(template_name):
                errors.append(f"Invalid template inheritance: '{template_name}' cannot be loaded")
        
        # Validate environment configurations
        env_errors = self.environment_manager.validate_environment_config(config)
        for env, env_error_list in env_errors.items():
            errors.extend([f"Environment '{env}': {error}" for error in env_error_list])
        
        return errors

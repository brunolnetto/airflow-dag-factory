"""
Self-service configuration interface for DAG Factory.
Provides web UI and API for non-technical users to create and manage DAG configurations.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import uuid

from .utils import (
    logger, validate_dag_id, safe_load_yaml_file, safe_save_yaml_file,
    SUPPORTED_OPERATORS, DAG_ID_PREFIXES
)
from .managers.template import ConfigurationComposer, TemplateManager, EnvironmentManager
from .managers.security import SecurityManager, AccessLevel, AuditAction

try:
    import yaml
except ImportError:
    yaml = None

try:
    from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = request = jsonify = render_template_string = session = redirect = url_for = None


@dataclass
class ConfigurationDraft:
    """Draft configuration for editing."""
    id: str
    name: str
    description: str
    template: Optional[str]
    config: Dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime
    status: str  # draft, validated, deployed


class ConfigurationAPI:
    """REST API for configuration management."""
    
    def __init__(self, app: Flask, config_dir: str = 'dags/configs'):
        self.app = app
        self.config_dir = Path(config_dir)
        self.drafts_dir = Path('dags/drafts')
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        
        self.composer = ConfigurationComposer()
        self.security_manager = SecurityManager()
        self.template_manager = TemplateManager()
        self.environment_manager = EnvironmentManager()
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.route('/api/templates', methods=['GET'])
        def list_templates():
            try:
                username = self._get_current_user()
                if not self.security_manager.validate_user_access(username, 'read'):
                    return jsonify({'error': 'Access denied'}), 403
                
                templates = self.template_manager.list_available_templates()
                template_details = []
                
                for template_name in templates:
                    try:
                        template_config = self.template_manager.load_template(template_name)
                        template_details.append({
                            'name': template_name,
                            'description': template_config.get('description', 'No description'),
                            'tags': template_config.get('tags', []),
                            'parameters': self._extract_template_parameters(template_config)
                        })
                    except Exception as e:
                        logger.error(f"Failed to load template {template_name}: {str(e)}")
                
                return jsonify({'templates': template_details})
                
            except Exception as e:
                logger.error(f"Error listing templates: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/configurations', methods=['GET'])
        def list_configurations():
            try:
                username = self._get_current_user()
                if not self.security_manager.validate_user_access(username, 'read'):
                    return jsonify({'error': 'Access denied'}), 403
                
                configs = []
                for config_file in self.config_dir.glob('*.yaml'):
                    try:
                        config = self.security_manager.load_secure_configuration(config_file, username)
                        configs.append({
                            'filename': config_file.name,
                            'dag_id': config.get('dag_id'),
                            'description': config.get('description', ''),
                            'schedule': config.get('schedule'),
                            'tags': config.get('tags', [])
                        })
                    except Exception as e:
                        logger.error(f"Failed to load config {config_file}: {str(e)}")
                
                return jsonify({'configurations': configs})
                
            except Exception as e:
                logger.error(f"Error listing configurations: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/configurations/<config_name>', methods=['GET'])
        def get_configuration(config_name):
            try:
                username = self._get_current_user()
                if not self.security_manager.validate_user_access(username, 'read'):
                    return jsonify({'error': 'Access denied'}), 403
                
                config_path = self.config_dir / f"{config_name}.yaml"
                if not config_path.exists():
                    return jsonify({'error': 'Configuration not found'}), 404
                
                config = self.security_manager.load_secure_configuration(config_path, username)
                return jsonify({'configuration': config})
                
            except Exception as e:
                logger.error(f"Error getting configuration: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/configurations', methods=['POST'])
        def create_configuration():
            try:
                username = self._get_current_user()
                if not self.security_manager.validate_user_access(username, 'write'):
                    return jsonify({'error': 'Access denied'}), 403
                
                config_data = request.get_json()
                if not config_data:
                    return jsonify({'error': 'No configuration data provided'}), 400
                
                # Validate required fields
                if 'dag_id' not in config_data:
                    return jsonify({'error': 'dag_id is required'}), 400
                
                # Apply template inheritance and environment overrides
                composed_config = self.composer.compose_configuration(config_data)
                
                # Validate composition
                validation_errors = self.composer.validate_composition(config_data)
                if validation_errors:
                    return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
                
                # Apply security measures
                secured_config = self.security_manager.secure_configuration(composed_config, username)
                
                # Save configuration
                config_filename = f"{config_data['dag_id']}.yaml"
                config_path = self.config_dir / config_filename
                
                with open(config_path, 'w') as f:
                    yaml.dump(secured_config, f, default_flow_style=False)
                
                return jsonify({
                    'message': 'Configuration created successfully',
                    'filename': config_filename
                }), 201
                
            except Exception as e:
                logger.error(f"Error creating configuration: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/drafts', methods=['GET'])
        def list_drafts():
            try:
                username = self._get_current_user()
                drafts = []
                
                for draft_file in self.drafts_dir.glob(f"{username}_*.json"):
                    try:
                        with open(draft_file, 'r') as f:
                            draft_data = json.load(f)
                        
                        draft = ConfigurationDraft(**draft_data)
                        drafts.append({
                            'id': draft.id,
                            'name': draft.name,
                            'description': draft.description,
                            'template': draft.template,
                            'status': draft.status,
                            'created_at': draft.created_at,
                            'updated_at': draft.updated_at
                        })
                    except Exception as e:
                        logger.error(f"Failed to load draft {draft_file}: {str(e)}")
                
                return jsonify({'drafts': drafts})
                
            except Exception as e:
                logger.error(f"Error listing drafts: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/drafts', methods=['POST'])
        def create_draft():
            try:
                username = self._get_current_user()
                draft_data = request.get_json()
                
                draft = ConfigurationDraft(
                    id=str(uuid.uuid4()),
                    name=draft_data.get('name', 'Untitled'),
                    description=draft_data.get('description', ''),
                    template=draft_data.get('template'),
                    config=draft_data.get('config', {}),
                    created_by=username,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    status='draft'
                )
                
                draft_file = self.drafts_dir / f"{username}_{draft.id}.json"
                with open(draft_file, 'w') as f:
                    # Convert datetime objects to strings for JSON serialization
                    draft_dict = asdict(draft)
                    draft_dict['created_at'] = draft.created_at.isoformat()
                    draft_dict['updated_at'] = draft.updated_at.isoformat()
                    json.dump(draft_dict, f, indent=2)
                
                return jsonify({'draft_id': draft.id}), 201
                
            except Exception as e:
                logger.error(f"Error creating draft: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/validate', methods=['POST'])
        def validate_configuration():
            try:
                username = self._get_current_user()
                if not self.security_manager.validate_user_access(username, 'validate'):
                    return jsonify({'error': 'Access denied'}), 403
                
                config_data = request.get_json()
                if not config_data:
                    return jsonify({'error': 'No configuration data provided'}), 400
                
                # Validate composition
                validation_errors = self.composer.validate_composition(config_data)
                
                # Log validation attempt
                self.security_manager.audit_logger.log_action(
                    user=username,
                    action=AuditAction.VALIDATE,
                    resource=config_data.get('dag_id', 'unknown'),
                    success=len(validation_errors) == 0,
                    details={'errors': validation_errors}
                )
                
                if validation_errors:
                    return jsonify({
                        'valid': False,
                        'errors': validation_errors
                    }), 400
                else:
                    return jsonify({'valid': True}), 200
                
            except Exception as e:
                logger.error(f"Error validating configuration: {str(e)}")
                return jsonify({'error': str(e)}), 500
    
    def _get_current_user(self) -> str:
        """Get current user from session or environment."""
        # In a real implementation, this would get the user from authentication
        return session.get('username', os.getenv('USER', 'anonymous'))
    
    def _extract_template_parameters(self, template_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract configurable parameters from template."""
        parameters = []
        
        # Look for parameter definitions in template
        template_params = template_config.get('parameters', {})
        for param_name, param_config in template_params.items():
            parameters.append({
                'name': param_name,
                'type': param_config.get('type', 'string'),
                'description': param_config.get('description', ''),
                'required': param_config.get('required', False),
                'default': param_config.get('default'),
                'options': param_config.get('options')
            })
        
        return parameters


class ConfigurationUI:
    """Web UI for configuration management."""
    
    def __init__(self, app: Flask):
        self.app = app
        self._setup_ui_routes()
    
    def _setup_ui_routes(self):
        """Setup UI routes."""
        
        @self.app.route('/')
        def index():
            return render_template_string(self._get_main_template())
        
        @self.app.route('/create')
        def create():
            return render_template_string(self._get_create_template())
        
        @self.app.route('/drafts')
        def drafts():
            return render_template_string(self._get_drafts_template())
        
        @self.app.route('/configurations')
        def configurations():
            return render_template_string(self._get_configurations_template())
    
    def _get_main_template(self) -> str:
        """Get main page template."""
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>DAG Factory - Self-Service Configuration</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .header { text-align: center; margin-bottom: 30px; }
                .nav { display: flex; gap: 15px; justify-content: center; margin-bottom: 30px; }
                .nav a { padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }
                .nav a:hover { background: #0056b3; }
                .card { border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 4px; }
                .btn { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
                .btn:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>DAG Factory Self-Service Configuration</h1>
                    <p>Create and manage Airflow DAG configurations without code</p>
                </div>
                
                <div class="nav">
                    <a href="/create">Create New DAG</a>
                    <a href="/drafts">My Drafts</a>
                    <a href="/configurations">View Configurations</a>
                </div>
                
                <div class="card">
                    <h2>Welcome to DAG Factory</h2>
                    <p>This self-service interface allows you to:</p>
                    <ul>
                        <li>Create new DAG configurations using templates</li>
                        <li>Save work as drafts and continue later</li>
                        <li>Validate configurations before deployment</li>
                        <li>View and manage existing configurations</li>
                    </ul>
                </div>
                
                <div class="card">
                    <h3>Quick Actions</h3>
                    <button class="btn" onclick="location.href='/create'">Create New DAG</button>
                    <button class="btn" onclick="loadTemplates()">View Templates</button>
                </div>
                
                <div id="templates-list" style="display:none;">
                    <h3>Available Templates</h3>
                    <div id="templates-content"></div>
                </div>
            </div>
            
            <script>
                async function loadTemplates() {
                    try {
                        const response = await fetch('/api/templates');
                        const data = await response.json();
                        
                        const templatesDiv = document.getElementById('templates-list');
                        const contentDiv = document.getElementById('templates-content');
                        
                        contentDiv.innerHTML = '';
                        data.templates.forEach(template => {
                            const templateCard = document.createElement('div');
                            templateCard.className = 'card';
                            templateCard.innerHTML = `
                                <h4>${template.name}</h4>
                                <p>${template.description}</p>
                                <p><strong>Tags:</strong> ${template.tags.join(', ')}</p>
                                <button class="btn" onclick="useTemplate('${template.name}')">Use Template</button>
                            `;
                            contentDiv.appendChild(templateCard);
                        });
                        
                        templatesDiv.style.display = 'block';
                    } catch (error) {
                        alert('Error loading templates: ' + error.message);
                    }
                }
                
                function useTemplate(templateName) {
                    location.href = `/create?template=${templateName}`;
                }
            </script>
        </body>
        </html>
        '''
    
    def _get_create_template(self) -> str:
        """Get create configuration template."""
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Create DAG Configuration</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input, select, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
                textarea { height: 100px; }
                .btn { padding: 10px 20px; margin: 5px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
                .btn:hover { background: #0056b3; }
                .btn-secondary { background: #6c757d; }
                .btn-secondary:hover { background: #545b62; }
                .error { color: red; margin-top: 5px; }
                .success { color: green; margin-top: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Create DAG Configuration</h1>
                <form id="dag-form">
                    <div class="form-group">
                        <label for="template">Template (Optional):</label>
                        <select id="template" name="template">
                            <option value="">No Template</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="dag_id">DAG ID:</label>
                        <input type="text" id="dag_id" name="dag_id" required pattern="^[a-zA-Z0-9_-]+$">
                        <div class="error" id="dag_id_error"></div>
                    </div>
                    
                    <div class="form-group">
                        <label for="description">Description:</label>
                        <textarea id="description" name="description"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="schedule">Schedule:</label>
                        <select id="schedule" name="schedule">
                            <option value="@daily">Daily</option>
                            <option value="@hourly">Hourly</option>
                            <option value="@weekly">Weekly</option>
                            <option value="@monthly">Monthly</option>
                            <option value="@once">Once</option>
                            <option value="custom">Custom Cron</option>
                        </select>
                    </div>
                    
                    <div class="form-group" id="custom-schedule" style="display:none;">
                        <label for="custom_schedule">Custom Schedule:</label>
                        <input type="text" id="custom_schedule" name="custom_schedule" placeholder="0 0 * * *">
                    </div>
                    
                    <div class="form-group">
                        <label for="start_date">Start Date:</label>
                        <input type="date" id="start_date" name="start_date" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="tags">Tags (comma-separated):</label>
                        <input type="text" id="tags" name="tags" placeholder="etl, data-processing">
                    </div>
                    
                    <div class="form-group">
                        <label for="owner">Owner:</label>
                        <input type="text" id="owner" name="owner" value="data-engineering">
                    </div>
                    
                    <div class="form-group">
                        <button type="button" class="btn" onclick="validateConfig()">Validate</button>
                        <button type="button" class="btn btn-secondary" onclick="saveDraft()">Save as Draft</button>
                        <button type="submit" class="btn">Create Configuration</button>
                        <button type="button" class="btn btn-secondary" onclick="location.href='/'">Cancel</button>
                    </div>
                    
                    <div id="validation-result"></div>
                </form>
            </div>
            
            <script>
                // Load templates
                fetch('/api/templates')
                    .then(response => response.json())
                    .then(data => {
                        const templateSelect = document.getElementById('template');
                        data.templates.forEach(template => {
                            const option = document.createElement('option');
                            option.value = template.name;
                            option.textContent = template.name;
                            templateSelect.appendChild(option);
                        });
                    });
                
                // Handle schedule change
                document.getElementById('schedule').addEventListener('change', function() {
                    const customSchedule = document.getElementById('custom-schedule');
                    if (this.value === 'custom') {
                        customSchedule.style.display = 'block';
                    } else {
                        customSchedule.style.display = 'none';
                    }
                });
                
                // Set default start date to today
                document.getElementById('start_date').value = new Date().toISOString().split('T')[0];
                
                function getFormData() {
                    const form = document.getElementById('dag-form');
                    const formData = new FormData(form);
                    const config = {};
                    
                    for (let [key, value] of formData.entries()) {
                        if (key === 'tags' && value) {
                            config[key] = value.split(',').map(tag => tag.trim());
                        } else if (value) {
                            config[key] = value;
                        }
                    }
                    
                    // Handle custom schedule
                    if (config.schedule === 'custom' && config.custom_schedule) {
                        config.schedule = config.custom_schedule;
                        delete config.custom_schedule;
                    }
                    
                    // Add minimal task structure
                    config.tasks = [{
                        task_id: 'example_task',
                        operator: 'dummy',
                        parameters: {}
                    }];
                    
                    return config;
                }
                
                async function validateConfig() {
                    try {
                        const config = getFormData();
                        const response = await fetch('/api/validate', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(config)
                        });
                        
                        const result = await response.json();
                        const resultDiv = document.getElementById('validation-result');
                        
                        if (response.ok) {
                            resultDiv.innerHTML = '<div class="success">✓ Configuration is valid</div>';
                        } else {
                            resultDiv.innerHTML = '<div class="error">✗ Validation failed:<br>' + 
                                result.errors.join('<br>') + '</div>';
                        }
                    } catch (error) {
                        document.getElementById('validation-result').innerHTML = 
                            '<div class="error">Error validating configuration: ' + error.message + '</div>';
                    }
                }
                
                async function saveDraft() {
                    try {
                        const config = getFormData();
                        const draft = {
                            name: config.dag_id || 'Untitled',
                            description: config.description || '',
                            template: config.template || null,
                            config: config
                        };
                        
                        const response = await fetch('/api/drafts', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(draft)
                        });
                        
                        if (response.ok) {
                            alert('Draft saved successfully!');
                        } else {
                            const error = await response.json();
                            alert('Error saving draft: ' + error.error);
                        }
                    } catch (error) {
                        alert('Error saving draft: ' + error.message);
                    }
                }
                
                document.getElementById('dag-form').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    
                    try {
                        const config = getFormData();
                        const response = await fetch('/api/configurations', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(config)
                        });
                        
                        if (response.ok) {
                            alert('Configuration created successfully!');
                            location.href = '/configurations';
                        } else {
                            const error = await response.json();
                            alert('Error creating configuration: ' + error.error);
                        }
                    } catch (error) {
                        alert('Error creating configuration: ' + error.message);
                    }
                });
            </script>
        </body>
        </html>
        '''
    
    def _get_drafts_template(self) -> str:
        """Get drafts page template."""
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>My Drafts</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .container { max-width: 1000px; margin: 0 auto; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
                th { background-color: #f2f2f2; }
                .btn { padding: 5px 10px; margin: 2px; background: #007bff; color: white; text-decoration: none; border-radius: 3px; border: none; cursor: pointer; }
                .btn:hover { background: #0056b3; }
                .btn-danger { background: #dc3545; }
                .btn-danger:hover { background: #c82333; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>My Drafts</h1>
                <p><a href="/" class="btn">← Back to Home</a></p>
                
                <table id="drafts-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Template</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="drafts-body">
                        <tr><td colspan="6">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <script>
                async function loadDrafts() {
                    try {
                        const response = await fetch('/api/drafts');
                        const data = await response.json();
                        
                        const tbody = document.getElementById('drafts-body');
                        tbody.innerHTML = '';
                        
                        if (data.drafts.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="6">No drafts found</td></tr>';
                            return;
                        }
                        
                        data.drafts.forEach(draft => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${draft.name}</td>
                                <td>${draft.description}</td>
                                <td>${draft.template || 'None'}</td>
                                <td>${draft.status}</td>
                                <td>${new Date(draft.created_at).toLocaleDateString()}</td>
                                <td>
                                    <button class="btn" onclick="editDraft('${draft.id}')">Edit</button>
                                    <button class="btn btn-danger" onclick="deleteDraft('${draft.id}')">Delete</button>
                                </td>
                            `;
                            tbody.appendChild(row);
                        });
                    } catch (error) {
                        document.getElementById('drafts-body').innerHTML = 
                            '<tr><td colspan="6">Error loading drafts: ' + error.message + '</td></tr>';
                    }
                }
                
                function editDraft(draftId) {
                    // Implementation would load draft data into create form
                    alert('Edit functionality would be implemented here');
                }
                
                function deleteDraft(draftId) {
                    if (confirm('Are you sure you want to delete this draft?')) {
                        // Implementation would delete the draft
                        alert('Delete functionality would be implemented here');
                    }
                }
                
                // Load drafts on page load
                loadDrafts();
            </script>
        </body>
        </html>
        '''
    
    def _get_configurations_template(self) -> str:
        """Get configurations page template."""
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>DAG Configurations</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .container { max-width: 1200px; margin: 0 auto; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
                th { background-color: #f2f2f2; }
                .btn { padding: 5px 10px; margin: 2px; background: #007bff; color: white; text-decoration: none; border-radius: 3px; }
                .btn:hover { background: #0056b3; }
                .tags { font-size: 0.8em; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>DAG Configurations</h1>
                <p><a href="/" class="btn">← Back to Home</a></p>
                
                <table id="configs-table">
                    <thead>
                        <tr>
                            <th>DAG ID</th>
                            <th>Description</th>
                            <th>Schedule</th>
                            <th>Tags</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="configs-body">
                        <tr><td colspan="5">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <script>
                async function loadConfigurations() {
                    try {
                        const response = await fetch('/api/configurations');
                        const data = await response.json();
                        
                        const tbody = document.getElementById('configs-body');
                        tbody.innerHTML = '';
                        
                        if (data.configurations.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="5">No configurations found</td></tr>';
                            return;
                        }
                        
                        data.configurations.forEach(config => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${config.dag_id}</td>
                                <td>${config.description}</td>
                                <td>${config.schedule}</td>
                                <td class="tags">${config.tags.join(', ')}</td>
                                <td>
                                    <a href="#" class="btn" onclick="viewConfig('${config.filename}')">View</a>
                                </td>
                            `;
                            tbody.appendChild(row);
                        });
                    } catch (error) {
                        document.getElementById('configs-body').innerHTML = 
                            '<tr><td colspan="5">Error loading configurations: ' + error.message + '</td></tr>';
                    }
                }
                
                function viewConfig(filename) {
                    const configName = filename.replace('.yaml', '');
                    window.open(`/api/configurations/${configName}`, '_blank');
                }
                
                // Load configurations on page load
                loadConfigurations();
            </script>
        </body>
        </html>
        '''


def create_app(config_dir: str = 'dags/configs') -> Flask:
    """Create Flask application with API and UI."""
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    
    # Initialize API and UI
    api = ConfigurationAPI(app, config_dir)
    ui = ConfigurationUI(app)
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)

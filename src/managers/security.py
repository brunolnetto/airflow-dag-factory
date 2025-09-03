"""
Security features for DAG Factory including encryption, access control, and audit logging.
"""

import os
import json
import logging
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import base64

from ..utils import safe_load_yaml_file, safe_save_yaml_file

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class AccessLevel(Enum):
    """Access levels for configuration operations."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class AuditAction(Enum):
    """Audit action types."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    VALIDATE = "validate"
    DEPLOY = "deploy"


@dataclass
class User:
    """User information for access control."""
    username: str
    roles: List[str]
    email: Optional[str] = None
    department: Optional[str] = None


@dataclass
class AuditLogEntry:
    """Audit log entry structure."""
    timestamp: datetime
    user: str
    action: AuditAction
    resource: str
    details: Dict[str, Any]
    success: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class EncryptionManager:
    """Manages encryption/decryption of sensitive configuration data."""
    
    def __init__(self, key_file: str = '.dag_factory_key'):
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available - encryption disabled")
            self._fernet = None
            return
            
        self.key_file = Path(key_file)
        self._fernet = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption key and Fernet instance."""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            # Save key securely
            os.umask(0o077)  # Restrict file permissions
            with open(self.key_file, 'wb') as f:
                f.write(key)
            logger.info(f"Generated new encryption key: {self.key_file}")
        
        self._fernet = Fernet(key)
    
    def encrypt_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in configuration."""
        if not CRYPTO_AVAILABLE or not self._fernet:
            logger.warning("Encryption not available - returning config unchanged")
            return config
            
        sensitive_fields = [
            'password', 'secret', 'token', 'key', 'credential',
            'connection_string', 'api_key', 'private_key'
        ]
        
        encrypted_config = self._deep_copy_and_encrypt(config, sensitive_fields)
        return encrypted_config
    
    def decrypt_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in configuration."""
        decrypted_config = self._deep_copy_and_decrypt(config)
        return decrypted_config
    
    def _deep_copy_and_encrypt(self, obj: Any, sensitive_fields: List[str]) -> Any:
        """Recursively encrypt sensitive fields."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if any(sensitive_field in key.lower() for sensitive_field in sensitive_fields):
                    if isinstance(value, str):
                        result[key] = self._encrypt_string(value)
                    else:
                        result[key] = value
                else:
                    result[key] = self._deep_copy_and_encrypt(value, sensitive_fields)
            return result
        elif isinstance(obj, list):
            return [self._deep_copy_and_encrypt(item, sensitive_fields) for item in obj]
        else:
            return obj
    
    def _deep_copy_and_decrypt(self, obj: Any) -> Any:
        """Recursively decrypt encrypted fields."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith('ENCRYPTED:'):
                    result[key] = self._decrypt_string(value)
                else:
                    result[key] = self._deep_copy_and_decrypt(value)
            return result
        elif isinstance(obj, list):
            return [self._deep_copy_and_decrypt(item) for item in obj]
        else:
            return obj
    
    def _encrypt_string(self, value: str) -> str:
        """Encrypt a string value."""
        try:
            encrypted_bytes = self._fernet.encrypt(value.encode())
            return f"ENCRYPTED:{base64.b64encode(encrypted_bytes).decode()}"
        except Exception as e:
            logger.error(f"Failed to encrypt value: {str(e)}")
            raise
    
    def _decrypt_string(self, encrypted_value: str) -> str:
        """Decrypt an encrypted string value."""
        try:
            if not encrypted_value.startswith('ENCRYPTED:'):
                return encrypted_value
            
            encrypted_data = encrypted_value[10:]  # Remove 'ENCRYPTED:' prefix
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt value: {str(e)}")
            raise
    
    def rotate_encryption_key(self, old_key_file: Optional[str] = None) -> str:
        """Rotate encryption key and return new key file path."""
        # Generate new key
        new_key = Fernet.generate_key()
        backup_key_file = f"{self.key_file}.backup.{int(datetime.now().timestamp())}"
        
        # Backup old key
        if self.key_file.exists():
            self.key_file.rename(backup_key_file)
        
        # Save new key
        with open(self.key_file, 'wb') as f:
            f.write(new_key)
        
        # Update Fernet instance
        self._fernet = Fernet(new_key)
        
        logger.info(f"Rotated encryption key. Backup saved to: {backup_key_file}")
        return str(backup_key_file)


class AccessControlManager:
    """Manages role-based access control for DAG Factory operations."""
    
    def __init__(self, roles_config_file: str = 'dags/security/roles.yaml'):
        self.roles_config_file = Path(roles_config_file)
        self.roles_config = self._load_roles_config()
        self.user_cache = {}
    
    def _load_roles_config(self) -> Dict[str, Any]:
        """Load roles configuration."""
        if not self.roles_config_file.exists():
            # Create default roles configuration
            default_config = {
                'roles': {
                    'viewer': {
                        'permissions': ['read'],
                        'description': 'Can view configurations'
                    },
                    'developer': {
                        'permissions': ['read', 'write'],
                        'description': 'Can create and modify configurations'
                    },
                    'admin': {
                        'permissions': ['read', 'write', 'admin'],
                        'description': 'Full access to all operations'
                    }
                },
                'users': {
                    'default': {
                        'roles': ['viewer'],
                        'email': 'user@company.com'
                    }
                }
            }
            
            self.roles_config_file.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            with open(self.roles_config_file, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            
            return default_config
        
        try:
            import yaml
            with open(self.roles_config_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load roles config: {str(e)}")
            raise
    
    def get_user(self, username: str) -> User:
        """Get user information with roles."""
        if username in self.user_cache:
            return self.user_cache[username]
        
        user_config = self.roles_config.get('users', {}).get(username, {})
        if not user_config:
            # Default user with minimal permissions
            user = User(username=username, roles=['viewer'])
        else:
            user = User(
                username=username,
                roles=user_config.get('roles', ['viewer']),
                email=user_config.get('email'),
                department=user_config.get('department')
            )
        
        self.user_cache[username] = user
        return user
    
    def check_permission(self, username: str, action: AccessLevel, resource: str = None) -> bool:
        """Check if user has permission for specific action."""
        user = self.get_user(username)
        user_permissions = set()
        
        # Collect permissions from all user roles
        for role_name in user.roles:
            role_config = self.roles_config.get('roles', {}).get(role_name, {})
            role_permissions = role_config.get('permissions', [])
            user_permissions.update(role_permissions)
        
        # Check if user has required permission
        required_permission = action.value
        has_permission = required_permission in user_permissions
        
        # Admin users have all permissions
        if 'admin' in user_permissions:
            has_permission = True
        
        # Resource-specific permissions (future enhancement)
        if resource and not has_permission:
            # Check for resource-specific permissions
            pass
        
        return has_permission
    
    def require_permission(self, username: str, action: AccessLevel, resource: str = None):
        """Require specific permission or raise exception."""
        if not self.check_permission(username, action, resource):
            raise PermissionError(f"User '{username}' does not have '{action.value}' permission for resource '{resource}'")
    
    def add_user(self, username: str, roles: List[str], email: str = None, department: str = None):
        """Add new user to roles configuration."""
        self.roles_config.setdefault('users', {})[username] = {
            'roles': roles,
            'email': email,
            'department': department
        }
        
        # Clear cache
        self.user_cache.pop(username, None)
        
        # Save updated configuration
        self._save_roles_config()
    
    def _save_roles_config(self):
        """Save roles configuration to file."""
        import yaml
        with open(self.roles_config_file, 'w') as f:
            yaml.dump(self.roles_config, f, default_flow_style=False)


class AuditLogger:
    """Audit logging for DAG Factory operations."""
    
    def __init__(self, log_file: str = 'dags/security/audit.log'):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure audit logger
        self.audit_logger = logging.getLogger('dag_factory_audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # File handler for audit logs
        if not self.audit_logger.handlers:
            handler = logging.FileHandler(self.log_file)
            formatter = logging.Formatter(
                '%(asctime)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S UTC'
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
    
    def log_action(self, user: str, action: AuditAction, resource: str, 
                   details: Dict[str, Any] = None, success: bool = True,
                   ip_address: str = None, user_agent: str = None):
        """Log an audit event."""
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            user=user,
            action=action,
            resource=resource,
            details=details or {},
            success=success,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Convert to JSON for structured logging
        log_data = asdict(entry)
        log_data['timestamp'] = entry.timestamp.isoformat()
        log_data['action'] = entry.action.value
        
        self.audit_logger.info(json.dumps(log_data))
    
    def get_audit_logs(self, user: str = None, action: AuditAction = None, 
                      resource: str = None, limit: int = 100) -> List[AuditLogEntry]:
        """Retrieve audit logs with optional filtering."""
        logs = []
        
        if not self.log_file.exists():
            return logs
        
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
            
            # Parse logs (most recent first)
            for line in reversed(lines[-limit*2:]):  # Read more lines to account for filtering
                if len(logs) >= limit:
                    break
                
                try:
                    # Extract JSON from log line
                    json_part = line.split(' | ', 1)[1].strip()
                    log_data = json.loads(json_part)
                    
                    # Apply filters
                    if user and log_data.get('user') != user:
                        continue
                    if action and log_data.get('action') != action.value:
                        continue
                    if resource and log_data.get('resource') != resource:
                        continue
                    
                    # Convert back to AuditLogEntry
                    entry = AuditLogEntry(
                        timestamp=datetime.fromisoformat(log_data['timestamp']),
                        user=log_data['user'],
                        action=AuditAction(log_data['action']),
                        resource=log_data['resource'],
                        details=log_data['details'],
                        success=log_data['success'],
                        ip_address=log_data.get('ip_address'),
                        user_agent=log_data.get('user_agent')
                    )
                    logs.append(entry)
                    
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
            
        except Exception as e:
            logger.error(f"Failed to read audit logs: {str(e)}")
        
        return logs


class SecurityManager:
    """Central security manager coordinating all security features."""
    
    def __init__(self, config_dir: str = 'dags/configs'):
        self.config_dir = Path(config_dir)
        self.encryption_manager = EncryptionManager()
        self.access_control = AccessControlManager()
        self.audit_logger = AuditLogger()
    
    def secure_configuration(self, config: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Apply security measures to configuration."""
        # Check permissions
        self.access_control.require_permission(username, AccessLevel.WRITE)
        
        # Encrypt sensitive data
        secured_config = self.encryption_manager.encrypt_sensitive_data(config)
        
        # Log action
        self.audit_logger.log_action(
            user=username,
            action=AuditAction.CREATE,
            resource=config.get('dag_id', 'unknown'),
            details={'config_keys': list(config.keys())}
        )
        
        return secured_config
    
    def load_secure_configuration(self, config_path: Path, username: str) -> Dict[str, Any]:
        """Load and decrypt configuration with security checks."""
        # Check read permissions
        self.access_control.require_permission(username, AccessLevel.READ)
        
        try:
            with open(config_path, 'r') as f:
                import yaml
                config = yaml.safe_load(f)
            
            # Decrypt sensitive data
            decrypted_config = self.encryption_manager.decrypt_sensitive_data(config)
            
            # Log access
            self.audit_logger.log_action(
                user=username,
                action=AuditAction.READ,
                resource=str(config_path),
                success=True
            )
            
            return decrypted_config
            
        except Exception as e:
            # Log failed access
            self.audit_logger.log_action(
                user=username,
                action=AuditAction.READ,
                resource=str(config_path),
                success=False,
                details={'error': str(e)}
            )
            raise
    
    def validate_user_access(self, username: str, operation: str, resource: str = None) -> bool:
        """Validate user access for specific operation."""
        access_level_map = {
            'read': AccessLevel.READ,
            'write': AccessLevel.WRITE,
            'admin': AccessLevel.ADMIN,
            'validate': AccessLevel.READ,
            'deploy': AccessLevel.WRITE
        }
        
        access_level = access_level_map.get(operation.lower(), AccessLevel.READ)
        return self.access_control.check_permission(username, access_level, resource)
    
    def get_user_permissions(self, username: str) -> Dict[str, Any]:
        """Get comprehensive user permissions information."""
        user = self.access_control.get_user(username)
        permissions = set()
        
        for role_name in user.roles:
            role_config = self.access_control.roles_config.get('roles', {}).get(role_name, {})
            role_permissions = role_config.get('permissions', [])
            permissions.update(role_permissions)
        
        return {
            'username': user.username,
            'roles': user.roles,
            'permissions': list(permissions),
            'email': user.email,
            'department': user.department
        }

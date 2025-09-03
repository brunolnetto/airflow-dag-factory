# Encryption Keys Directory

This directory contains encryption keys for DAG Factory security features.

## Security Notice
- Never commit actual encryption keys to version control
- Use environment variables or secure key management systems
- Ensure proper file permissions (600) for key files
- Rotate keys regularly according to security policy

## Key Types
- `master.key`: Master encryption key for configuration encryption
- `signing.key`: Key for signing DAG configurations
- `api.key`: API authentication keys

## Key Generation
```bash
# Generate master encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > master.key

# Set proper permissions
chmod 600 *.key
```

## Environment Variables
Set these environment variables instead of storing keys in files:
- `DAG_FACTORY_MASTER_KEY`: Master encryption key
- `DAG_FACTORY_SIGNING_KEY`: Configuration signing key
- `DAG_FACTORY_API_KEY`: API authentication key

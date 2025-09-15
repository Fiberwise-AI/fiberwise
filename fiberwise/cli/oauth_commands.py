"""
OAuth management commands for FiberWise CLI.
"""
import click
import json
import requests
import tempfile
import os
import yaml
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add fiberwise-common to path


# Import from fiberwise-common
from fiberwise_common.services.fiber_app_manager import (
    validate_instance_config,
    load_instance_config
)

from .app_context import AppOperationContext
from .app_utils import (
    find_manifest_file, 
    load_manifest,
    FIBER_DATA_DIR,
    APP_INFO_FILE
)


def load_local_app_info(app_dir: str = ".", instance_name: str = None) -> Optional[Dict[str, Any]]:
    """Load local app info from .fiber/{instance} directory."""
    try:
        app_path = Path(app_dir)
        
        if instance_name is None:
            try:
                temp_ctx = AppOperationContext(app_path, None, None, False)
                instance_name = temp_ctx.instance_name
            except click.ClickException:
                return None
        
        validated_instance = validate_instance_config(instance_name)
        fw_data_dir = Path(app_dir) / FIBER_DATA_DIR
        instance_dir = fw_data_dir / validated_instance
        app_info_file = instance_dir / APP_INFO_FILE
        
        if not app_info_file.exists():
            return None
        
        with open(app_info_file, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def _is_authenticator_config(data):
    """Check if a data structure looks like an OAuth authenticator configuration."""
    if not isinstance(data, dict):
        return False
    
    required_fields = ['name', 'authenticator_type', 'client_id', 'client_secret']
    return all(field in data for field in required_fields)


def _get_default_scopes_for_provider(provider_type):
    """Get default OAuth scopes based on provider type."""
    provider_scopes = {
        'google': ['openid', 'profile', 'email'],
        'github': ['user:email', 'read:user'], 
        'microsoft': ['openid', 'profile', 'email'],
        'discord': ['identify', 'email'],
        'oauth2': ['openid', 'profile', 'email']
    }
    return provider_scopes.get(provider_type, ['openid', 'profile', 'email'])


def _detect_and_convert_oauth_format(data, filename="unknown"):
    """Detect common OAuth file formats and convert to FiberWise standard format."""
    if not isinstance(data, dict):
        return None
    
    # Pattern 1: Nested 'web' object (Google format)
    if 'web' in data and isinstance(data['web'], dict):
        web_config = data['web']
        if 'client_id' in web_config and 'client_secret' in web_config:
            app_name = web_config.get('project_id', filename.replace('.json', ''))
            oauth_config = {
                'name': app_name,
                'authenticator_type': 'oauth2',
                'client_id': web_config['client_id'],
                'client_secret': web_config['client_secret'],
                'scopes': ['openid', 'profile', 'email']
            }
            
            # Add Google OAuth URLs
            if 'auth_uri' in web_config:
                oauth_config['auth_uri'] = web_config['auth_uri']
                oauth_config['authorize_url'] = web_config['auth_uri']  # Both formats
            if 'token_uri' in web_config:
                oauth_config['token_uri'] = web_config['token_uri'] 
                oauth_config['token_url'] = web_config['token_uri']  # Both formats
            
            return oauth_config
    
    # Pattern 2: Nested 'installed' object (Google desktop format)
    if 'installed' in data and isinstance(data['installed'], dict):
        installed_config = data['installed']
        if 'client_id' in installed_config and 'client_secret' in installed_config:
            app_name = installed_config.get('project_id', filename.replace('.json', ''))
            return {
                'name': f'{app_name} Desktop',
                'authenticator_type': 'oauth2',
                'client_id': installed_config['client_id'],
                'client_secret': installed_config['client_secret'],
                'scopes': ['openid', 'profile', 'email']
            }
    
    # Pattern 3: camelCase format (Microsoft/Azure format)
    if 'clientId' in data and 'clientSecret' in data:
        app_name = data.get('displayName', data.get('name', filename.replace('.json', '')))
        return {
            'name': app_name,
            'authenticator_type': 'oauth2',
            'client_id': data['clientId'],
            'client_secret': data['clientSecret'],
            'scopes': ['openid', 'profile', 'email']
        }
    
    # Pattern 4: Direct format (most common)
    if 'client_id' in data and 'client_secret' in data:
        clean_filename = filename.replace('.json', '').replace('_', ' ').replace('-', ' ')
        app_name = data.get('name', clean_filename)
        
        oauth_type = 'oauth2'
        filename_lower = clean_filename.lower()
        if any(hint in filename_lower for hint in ['google']):
            oauth_type = 'google'
        elif any(hint in filename_lower for hint in ['github']):
            oauth_type = 'github'
        elif any(hint in filename_lower for hint in ['microsoft', 'azure']):
            oauth_type = 'microsoft'
        
        oauth_config = {
            'name': app_name,
            'authenticator_type': oauth_type,
            'client_id': data['client_id'],
            'client_secret': data['client_secret'],
            'scopes': _get_default_scopes_for_provider(oauth_type)
        }
        
        for key in ['domain', 'redirect_uris', 'auth_uri', 'token_uri', 'scopes', 'issuer', 'audience']:
            if key in data:
                oauth_config[key] = data[key]
        
        return oauth_config
    
    return None


def register_oauth_authenticators_from_manifest(app_path: Path, instance_name: str, verbose: bool = False) -> int:
    """Register OAuth authenticators found in the app manifest with the FiberWise API."""
    try:
        manifest_path = find_manifest_file(app_path)
        if not manifest_path:
            return 0
        
        manifest_data, _ = load_manifest(manifest_path, return_format=True)
        oauth_section = manifest_data.get('oauth', {})
        authenticators = oauth_section.get('authenticators', [])
        
        if not authenticators:
            if verbose:
                click.echo("   No OAuth authenticators found in manifest")
            return 0
        
        app_info = load_local_app_info(app_path, instance_name)
        if not app_info or not app_info.get('app_id'):
            if verbose:
                click.echo("   ⚠️  No app_id found - OAuth registration requires app to be installed first")
            return 0
        
        app_id = app_info['app_id']
        
        try:
            config_data = load_instance_config(instance_name)
        except ValueError as e:
            if verbose:
                click.echo(f"   ⚠️  Configuration error: {e}")
            return 0
        
        base_url = config_data.get('base_url', '').rstrip('/')
        api_key = config_data.get('api_key')
        
        if not base_url or not api_key:
            if verbose:
                click.echo("   ⚠️  Invalid configuration - missing API endpoint or key")
            return 0
        
        registered_count = 0
        for auth_ref in authenticators:
            try:
                # Ensure auth_ref is a dictionary
                if not isinstance(auth_ref, dict):
                    if verbose:
                        click.echo(f"   ⚠️  Invalid authenticator format: {auth_ref}")
                    continue
                    
                auth_file = auth_ref.get('file')
                if not auth_file:
                    continue
                
                if auth_file.startswith('.'):
                    auth_file_path = app_path / auth_file
                else:
                    auth_file_path = Path(auth_file)
                
                if not auth_file_path.exists():
                    if verbose:
                        click.echo(f"   ⚠️  OAuth file not found: {auth_file}")
                    continue
                
                with open(auth_file_path, 'r') as f:
                    authenticator_data = json.load(f)
                
                required_fields = ['name', 'authenticator_type', 'client_id', 'client_secret']
                missing_fields = [field for field in required_fields if field not in authenticator_data]
                
                if missing_fields:
                    if verbose:
                        click.echo(f"   ⚠️  OAuth config missing fields: {', '.join(missing_fields)}")
                    continue
                
                # Get scopes from manifest first, fallback to file
                scopes = auth_ref.get('scopes', authenticator_data.get('scopes', ['openid', 'profile', 'email']))
                
                oauth_data = {
                    'name': authenticator_data['name'],
                    'authenticator_type': authenticator_data['authenticator_type'],
                    'client_id': authenticator_data['client_id'],
                    'client_secret': authenticator_data['client_secret'],
                    'scopes': scopes
                }
                
                # Include all OAuth URL fields, checking both naming conventions
                url_mappings = {
                    'authorize_url': ['authorize_url', 'auth_uri'],
                    'token_url': ['token_url', 'token_uri']
                }
                
                for target_field, source_fields in url_mappings.items():
                    for source_field in source_fields:
                        if source_field in authenticator_data:
                            oauth_data[target_field] = authenticator_data[source_field]
                            break  # Use first match
                
                # Include any additional configuration fields
                for optional_field in ['redirect_uri', 'configuration']:
                    if optional_field in authenticator_data:
                        oauth_data[optional_field] = authenticator_data[optional_field]
                
                url = f"{base_url}/api/v1/oauth/authenticators/{app_id}"
                headers = {
                    'Authorization': f'Bearer api_{api_key}',
                    'Content-Type': 'application/json'
                }
                
                if verbose:
                    click.echo(f"   🔍 POST {url}")
                    click.echo(f"   🔍 Data: {oauth_data}")
                
                response = requests.post(url, headers=headers, json=oauth_data)
                
                if response.status_code == 201:
                    registered_count += 1
                    if verbose:
                        auth_name = authenticator_data['name']
                        click.echo(f"   🔑 Registered OAuth authenticator: {auth_name}")
                elif response.status_code == 409:
                    if verbose:
                        auth_name = authenticator_data['name']
                        click.echo(f"   ℹ️  OAuth authenticator already exists: {auth_name}")
                else:
                    if verbose:
                        auth_name = authenticator_data['name']
                        click.echo(f"   ❌ Failed to register {auth_name}: HTTP {response.status_code}")
                        try:
                            error_data = response.json()
                            click.echo(f"      Error: {error_data.get('error', 'Unknown error')}")
                        except:
                            pass
                    
            except Exception as e:
                if verbose:
                    # Handle case where auth_ref might be a string or other type
                    if isinstance(auth_ref, dict):
                        auth_name = auth_ref.get('name', 'Unknown')
                    else:
                        auth_name = str(auth_ref)
                    click.echo(f"   ❌ Failed to register {auth_name}: {e}")
        
        return registered_count
        
    except Exception as e:
        if verbose:
            click.echo(f"   ⚠️  Error processing OAuth authenticators: {e}")
        return 0


def register_authenticator_internal(authenticator_config_path, to_instance=None):
    """Internal function to store OAuth authenticator locally and update manifest and app.json."""
    app_dir = Path.cwd()
    
    if to_instance is None:
        try:
            temp_ctx = AppOperationContext(app_dir, None, None, False)
            to_instance = temp_ctx.instance_name
        except click.ClickException as e:
            raise ValueError(f"Could not resolve instance: {e}")
    
    manifest_path = find_manifest_file(app_dir)
    if not manifest_path:
        raise ValueError("No app manifest file found in current directory")
    
    with open(authenticator_config_path, 'r') as f:
        authenticator_data = json.load(f)
    
    required_fields = ['name', 'authenticator_type', 'client_id', 'client_secret']
    missing_fields = [field for field in required_fields if field not in authenticator_data]
    
    if missing_fields:
        raise ValueError(f"Missing required fields in authenticator config: {', '.join(missing_fields)}")
    
    instance_name = validate_instance_config(to_instance)
    
    fiber_dir = app_dir / FIBER_DATA_DIR
    instance_dir = fiber_dir / instance_name
    oauth_dir = instance_dir / "oauth"
    oauth_dir.mkdir(parents=True, exist_ok=True)
    
    auth_name = authenticator_data.get('name', 'authenticator')
    safe_name = auth_name.lower().replace(' ', '_').replace('-', '_')
    oauth_file = oauth_dir / f"{safe_name}.json"
    
    with open(oauth_file, 'w', encoding='utf-8') as f:
        json.dump(authenticator_data, f, indent=2, ensure_ascii=False)
    
    # Update manifest
    manifest_data, manifest_format = load_manifest(manifest_path, return_format=True)
    
    if 'oauth' not in manifest_data:
        manifest_data['oauth'] = {}
    
    if 'authenticators' not in manifest_data['oauth']:
        manifest_data['oauth']['authenticators'] = []
    
    auth_ref = {
        'name': authenticator_data['name'],
        'type': authenticator_data['authenticator_type'],
        'file': f".fiber/{instance_name}/oauth/{safe_name}.json"
    }
    
    existing_names = [auth.get('name') for auth in manifest_data['oauth']['authenticators']]
    manifest_updated = False
    if authenticator_data['name'] not in existing_names:
        manifest_data['oauth']['authenticators'].append(auth_ref)
        manifest_updated = True
        
        if manifest_format == 'yaml':
            with open(manifest_path, 'w', encoding='utf-8') as f:
                yaml.dump(manifest_data, f, default_flow_style=False, allow_unicode=True)
        else:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    
    # Update app.json with OAuth provider info
    app_json_path = instance_dir / APP_INFO_FILE
    app_json_updated = False
    if app_json_path.exists():
        with open(app_json_path, 'r') as f:
            app_data = json.load(f)
        
        if 'oauth_providers' not in app_data:
            app_data['oauth_providers'] = []
        
        # Check if this authenticator already exists in app.json
        existing_provider_names = [p.get('name') for p in app_data['oauth_providers']]
        if authenticator_data['name'] not in existing_provider_names:
            # Add OAuth provider info to app.json
            oauth_provider = {
                'name': authenticator_data['name'],
                'authenticator_type': authenticator_data['authenticator_type'],
                'client_id': authenticator_data['client_id'],
                'scopes': authenticator_data.get('scopes', ['openid', 'profile', 'email'])
            }
            
            # Add URLs if they exist in the authenticator data
            if 'auth_uri' in authenticator_data:
                oauth_provider['auth_uri'] = authenticator_data['auth_uri']
            if 'token_uri' in authenticator_data:
                oauth_provider['token_uri'] = authenticator_data['token_uri']
            if 'authorize_url' in authenticator_data:
                oauth_provider['authorize_url'] = authenticator_data['authorize_url']
            if 'token_url' in authenticator_data:
                oauth_provider['token_url'] = authenticator_data['token_url']
            
            app_data['oauth_providers'].append(oauth_provider)
            app_json_updated = True
            
            with open(app_json_path, 'w', encoding='utf-8') as f:
                json.dump(app_data, f, indent=2, ensure_ascii=False)
    
    return {
        'name': authenticator_data['name'],
        'type': authenticator_data['authenticator_type'],
        'file_path': str(oauth_file),
        'manifest_updated': manifest_updated,
        'app_json_updated': app_json_updated
    }


@click.group(name='oauth')
def oauth():
    """Manage OAuth authenticators for applications."""
    pass


@oauth.command(name='import')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--to-instance', help='Target FiberWise instance config name (uses default if not specified)')
@click.option('--dry-run', is_flag=True, help='Preview import without making changes')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def import_oauth_config(file_path, to_instance, dry_run, verbose):
    """Import OAuth configurations from common provider formats.
    
    This command automatically detects and converts OAuth configurations from
    various providers (Google, GitHub, Microsoft, etc.) into FiberWise format.
    
    FILE_PATH: Path to the OAuth configuration file to import
    """
    try:
        app_dir = Path.cwd()
        ctx = AppOperationContext(app_dir, to_instance, None, verbose)
        
        # Load and validate the OAuth config file
        config_file = Path(file_path)
        if verbose:
            click.echo(f"📄 Importing from: {config_file.absolute()}")
            click.echo(f"🎯 Target app directory: {app_dir.absolute()}")
            click.echo(f"🌐 Target instance: {ctx.instance_name}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    import yaml
                    raw_data = yaml.safe_load(f)
                else:
                    raw_data = json.load(f)
        except Exception as e:
            click.echo(f"❌ Error reading config file: {e}", err=True)
            return
        
        # Detect and convert OAuth configurations
        filename = config_file.name
        converted_configs = []
        
        # Try to detect multiple configurations in the file
        if isinstance(raw_data, list):
            # Multiple configs in a list
            for i, config_data in enumerate(raw_data):
                converted = _detect_and_convert_oauth_format(config_data, f"{filename}_{i}")
                if converted:
                    converted_configs.append(converted)
        elif isinstance(raw_data, dict):
            # Check if it's a single config or contains multiple configs
            if _is_authenticator_config(raw_data):
                # Single authenticator config
                converted = _detect_and_convert_oauth_format(raw_data, filename)
                if converted:
                    converted_configs.append(converted)
            else:
                # Try to detect format-based configs
                converted = _detect_and_convert_oauth_format(raw_data, filename)
                if converted:
                    converted_configs.append(converted)
                else:
                    # Check if it contains multiple configs as values
                    for key, value in raw_data.items():
                        if isinstance(value, dict):
                            converted = _detect_and_convert_oauth_format(value, f"{filename}_{key}")
                            if converted:
                                converted_configs.append(converted)
        
        if not converted_configs:
            click.echo(f"❌ No valid OAuth configurations found in {filename}", err=True)
            click.echo("💡 Expected format:", err=True)
            click.echo("   • Standard OAuth: {\"client_id\": \"...\", \"client_secret\": \"...\"}", err=True)
            click.echo("   • Google OAuth: {\"web\": {\"client_id\": \"...\", \"client_secret\": \"...\"}}", err=True)
            click.echo("   • Microsoft OAuth: {\"clientId\": \"...\", \"clientSecret\": \"...\"}", err=True)
            click.echo("📖 For setup guides, visit: https://docs.fiberwise.ai/oauth-setup", err=True)
            return
        
        # Display found configurations
        click.echo(f"✅ Found {len(converted_configs)} authenticator(s):")
        for config in converted_configs:
            click.echo(f"   • {config['name']} ({config['authenticator_type']})")
            if verbose:
                click.echo(f"     Client ID: {config['client_id'][:10]}...")
                if config.get('scopes'):
                    click.echo(f"     Scopes: {', '.join(config['scopes'])}")
        
        if dry_run:
            click.echo("🔍 Dry run mode - no changes made")
            click.echo("   Use without --dry-run to import these configurations")
            return
        
        # Confirm import
        if not click.confirm(f"Import {len(converted_configs)} authenticator(s) to instance '{ctx.instance_name}'?"):
            click.echo("Operation cancelled")
            return
        
        # Import each configuration
        imported_count = 0
        failed_count = 0
        
        for config in converted_configs:
            try:
                # Create temporary file for the config
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as temp_file:
                    json.dump(config, temp_file, indent=2)
                    temp_file_path = temp_file.name
                
                try:
                    click.echo(f"📄 Processing {config['name']}...")
                    if verbose:
                        click.echo(f"   🔑 Importing: {config['name']}")
                    
                    # Use the existing register function
                    result = register_authenticator_internal(temp_file_path, ctx.instance_name)
                    
                    if verbose:
                        click.echo(f"   ✅ Successfully imported: {config['name']}")
                        click.echo(f"   📁 Saved to: {result.get('file_path', 'N/A')}")
                        if result.get('app_json_updated'):
                            click.echo(f"   📝 Updated app.json with OAuth provider info")
                        if result.get('manifest_updated'):
                            click.echo(f"   📝 Updated manifest with OAuth reference")
                    else:
                        click.echo(f"   ✅ Successfully imported: {config['name']}")
                    
                    imported_count += 1
                    
                except Exception as e:
                    click.echo(f"   ❌ Failed to import {config['name']}: {e}", err=True)
                    failed_count += 1
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
                        
            except Exception as e:
                click.echo(f"   ❌ Error processing {config['name']}: {e}", err=True)
                failed_count += 1
        
        # Show summary
        click.echo("\n🎉 Import complete!")
        if imported_count > 0:
            click.echo(f"   ✅ Successfully imported: {imported_count}")
        if failed_count > 0:
            click.echo(f"   ❌ Failed to import: {failed_count}")
        
        if imported_count > 0:
            click.echo(f"\n💡 Use 'fiber app oauth list --to-instance {ctx.instance_name}' to view imported authenticators")
    
    except click.ClickException:
        return
    except Exception as e:
        click.echo(f"❌ Error during import: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)


@oauth.command(name='register')
@click.option('--authenticator-config', required=True, type=click.Path(exists=True), 
              help='Path to the JSON file containing the authenticator configuration')
@click.option('--to-instance', help='Target FiberWise instance config name (uses default if not specified)')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def register_authenticator(authenticator_config, to_instance, verbose):
    """Register an OAuth authenticator by storing it locally and updating the manifest."""
    try:
        app_dir = Path.cwd()
        ctx = AppOperationContext(app_dir, to_instance, None, verbose)
        
        result = register_authenticator_internal(authenticator_config, ctx.instance_name)
        
        click.echo("✅ OAuth authenticator registered successfully!")
        click.echo(f"   Name: {result.get('name', 'N/A')}")
        click.echo(f"   Type: {result.get('type', 'N/A')}")
        click.echo(f"   Saved to: {result.get('file_path', 'N/A')}")
        if result.get('manifest_updated'):
            click.echo(f"   ✅ App manifest updated with OAuth reference")
        else:
            click.echo(f"   ℹ️  OAuth reference already exists in manifest")
            
    except click.ClickException:
        return
    except Exception as e:
        click.echo(f"❌ Error registering OAuth authenticator: {e}", err=True)


@oauth.command(name='list')
@click.option('--to-instance', help='Target FiberWise instance config name (uses default if not specified)')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def list_authenticators(to_instance, verbose):
    """List OAuth authenticators for the current app."""
    try:
        app_dir = Path.cwd()
        ctx = AppOperationContext(app_dir, to_instance, None, verbose)
        
        if not ctx.app_info:
            click.echo(f"❌ No app info found for instance '{ctx.instance_name}'", err=True)
            click.echo(f"   Expected path: {app_dir}/{FIBER_DATA_DIR}/{ctx.instance_name}/{APP_INFO_FILE}", err=True)
            return
        
        app_id = ctx.app_info.get('app_id')
        if not app_id:
            click.echo("❌ App ID not found in app info", err=True)
            return
        
        base_url, api_key = ctx.get_api_config()
        
        if not ctx.has_valid_api_config():
            click.echo("❌ Invalid configuration", err=True)
            return
        
        url = f"{base_url}/api/v1/oauth/authenticators"
        headers = {'Authorization': f'Bearer api_{api_key}'}
        params = {'app_id': app_id}
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            authenticators = response.json()
            if not authenticators:
                click.echo(f"No OAuth authenticators found for app: {app_id}")
                return
            
            click.echo(f"OAuth Authenticators for app: {app_id}")
            click.echo("-" * 60)
            for authenticator in authenticators:
                click.echo(f"Authenticator ID: {authenticator.get('id', 'N/A')}")
                click.echo(f"Name: {authenticator.get('name', 'N/A')}")
                click.echo(f"Type: {authenticator.get('authenticator_type', 'N/A')}")
                if authenticator.get('scopes'):
                    click.echo(f"Scopes: {', '.join(authenticator['scopes'])}")
                click.echo(f"Created: {authenticator.get('created_at', 'N/A')}")
                click.echo("-" * 60)
        else:
            click.echo(f"❌ Error fetching authenticators: {response.status_code}", err=True)
    
    except click.ClickException:
        return
    except Exception as e:
        click.echo(f"❌ Error listing authenticators: {e}", err=True)


@oauth.command(name='delete')
@click.argument('authenticator_id')
@click.option('--to-instance', help='Target FiberWise instance config name (uses default if not specified)')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def delete_authenticator(authenticator_id, to_instance, verbose):
    """Delete an OAuth authenticator."""
    try:
        app_dir = Path.cwd()
        ctx = AppOperationContext(app_dir, to_instance, None, verbose)
        
        if not ctx.app_info:
            click.echo(f"❌ No app info found for instance '{ctx.instance_name}'", err=True)
            return
        
        app_id = ctx.app_info.get('app_id')
        if not app_id:
            click.echo("❌ App ID not found in app info", err=True)
            return
        
        base_url, api_key = ctx.get_api_config()
        
        if not ctx.has_valid_api_config():
            click.echo("❌ Invalid configuration", err=True)
            return
        
        if not click.confirm(f"Are you sure you want to delete OAuth authenticator '{authenticator_id}'?"):
            click.echo("Operation cancelled")
            return
        
        url = f"{base_url}/api/v1/oauth/authenticators/{authenticator_id}"
        headers = {'Authorization': f'Bearer api_{api_key}'}
        
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 200:
            click.echo(f"✅ OAuth authenticator '{authenticator_id}' deleted successfully")
        elif response.status_code == 404:
            click.echo(f"❌ OAuth authenticator '{authenticator_id}' not found", err=True)
        else:
            click.echo(f"❌ Error deleting authenticator: {response.status_code}", err=True)
    
    except click.ClickException:
        return
    except Exception as e:
        click.echo(f"❌ Error deleting authenticator: {e}", err=True)

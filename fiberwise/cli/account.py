import click
import json
import os
import shutil
import requests
import asyncio
import uuid
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add fiberwise-common to path for database integration


try:
    from fiberwise_common.services import AccountService, ProviderService
    from fiberwise_common.database import DatabaseManager
    from fiberwise_common.config import BaseWebSettings
    DATABASE_INTEGRATION = True
except ImportError as e:
    DATABASE_INTEGRATION = False

# Import app info utilities
# from .services.app_info import load_local_app_info  # Temporarily disabled
def load_local_app_info():
    """Temporary placeholder for app info loading"""
    return None

# Define the base directory for Fiberwise configurations and settings
FIBERWISE_DIR = Path.home() / ".fiberwise"
CONFIG_DIR = FIBERWISE_DIR / "configs"
DEFAULT_CONFIG_MARKER_FILE = FIBERWISE_DIR / "default_config.txt"
PROVIDERS_DIR = FIBERWISE_DIR / "providers"  # TODO: DEPRECATED - used by import-providers, should be removed

# Add this constant for default provider marker
DEFAULT_PROVIDER_FILE = FIBERWISE_DIR / "default_provider.json"

def get_default_config_name():
    """Get the name of the default configuration."""
    if DEFAULT_CONFIG_MARKER_FILE.exists():
        try:
            with open(DEFAULT_CONFIG_MARKER_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def load_config(config_name):
    """Load configuration by name."""
    if not config_name:
        return None
    
    # Sanitize config name for filename
    safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in config_name)
    config_file = CONFIG_DIR / f"{safe_filename}.json"
    
    if not config_file.exists():
        return None
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def resolve_instance_config(to_instance):
    """Resolve instance configuration for routing commands."""
    if to_instance == 'local':
        return {'type': 'local'}
    
    # Load configuration for remote instance
    config_data = load_config(to_instance)
    if not config_data:
        # Try default config
        default_config_name = get_default_config_name()
        if default_config_name and to_instance == 'default':
            config_data = load_config(default_config_name)
    
    if not config_data:
        raise click.ClickException(f"Configuration '{to_instance}' not found. Use 'fiber account add-config' first.")
    
    return {
        'type': 'remote',
        'api_key': config_data.get('api_key') or config_data.get('fiberwise_api_key'),
        'base_url': config_data.get('base_url') or config_data.get('fiberwise_base_url'),
        'config_name': to_instance
    }

async def add_provider_via_api(base_url, api_key, provider_data):
    """Add provider via API call to FiberWise instance."""
    url = f"{base_url.rstrip('/')}/api/v1/llm-providers/"
    
    # The server expects the API key with 'api_' prefix
    formatted_api_key = f"api_{api_key}" if not api_key.startswith('api_') else api_key
    
    headers = {
        'Authorization': f'Bearer {formatted_api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(url, json=provider_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"API call failed: {e}")

def _list_providers_via_api(base_url, api_key, provider_id, format):
    """List providers via API call to remote FiberWise instance."""
    try:
        # API endpoint for getting LLM providers
        url = f"{base_url.rstrip('/')}/api/v1/llm-providers/"
        if provider_id:
            url += f"{provider_id}/"
            
        # Format API key for server (expects 'api_' prefix)
        formatted_api_key = f"api_{api_key}" if not api_key.startswith('api_') else api_key
        
        headers = {
            'Authorization': f'Bearer {formatted_api_key}',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        providers = response.json()
        
        if not providers:
            click.echo("No providers found on the remote instance.")
            return
            
        # Handle single provider vs list
        if not isinstance(providers, list):
            providers = [providers]
            
        click.echo(f"🌐 Remote Providers ({len(providers)} found):")
        click.echo("=" * 50)
        
        for i, provider in enumerate(providers):
            provider_name = provider.get('name', 'Unnamed Provider')
            provider_type = provider.get('provider_type', 'Unknown')
            provider_id_val = provider.get('provider_id') or provider.get('id', 'Unknown')
            
            if format == 'basic':
                click.echo(f"{i+1}. {provider_name} ({provider_type})")
                click.echo(f"   ID: {provider_id_val}")
                if provider.get('model'):
                    click.echo(f"   Model: {provider['model']}")
                if provider.get('is_active', True):
                    click.echo(f"   Status: Active")
                else:
                    click.echo(f"   Status: Inactive")
                    
            elif format == 'detailed':
                click.echo(f"{i+1}. {provider_name}")
                click.echo(f"   ID: {provider_id_val}")
                click.echo(f"   Type: {provider_type}")
                if provider.get('model'):
                    click.echo(f"   Model: {provider['model']}")
                if provider.get('api_endpoint'):
                    click.echo(f"   Endpoint: {provider['api_endpoint']}")
                if provider.get('max_tokens'):
                    click.echo(f"   Max Tokens: {provider['max_tokens']}")
                if provider.get('temperature') is not None:
                    click.echo(f"   Temperature: {provider['temperature']}")
                click.echo(f"   Active: {'Yes' if provider.get('is_active', True) else 'No'}")
                if provider.get('created_at'):
                    click.echo(f"   Created: {provider['created_at']}")
                    
            elif format == 'json':
                # Filter sensitive data for display
                safe_provider = {k: v for k, v in provider.items() 
                               if k not in ["api_key", "secret_key", "password"]}
                click.echo(f"{i+1}. {provider_name} (JSON):")
                click.echo(json.dumps(safe_provider, indent=2))
                
            if i < len(providers) - 1:  # Add separator between providers
                click.echo()
                
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            click.echo("❌ Provider API endpoint not found on remote instance.", err=True)
        elif e.response.status_code == 401:
            click.echo("❌ Authentication failed. Check your API key.", err=True)
        else:
            click.echo(f"❌ API request failed: {e.response.status_code}", err=True)
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Connection error: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Error listing remote providers: {e}", err=True)

@click.group()
def account():
    """Manage Fiberwise account configurations."""
    pass

@account.command()
@click.option(
    '--config',
    'config_path_str', # Use a different variable name to avoid shadowing the module
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
    help='Path to the JSON configuration file containing name (or config_name), api_key, and base_url.'
)
def login(config_path_str):
    """
    Logs in using a configuration file and saves it for future use.

    Reads the specified JSON configuration file, validates its content,
    and copies it to the ~/.fiberwise/configs/ directory, named after
    the 'config_name' within the JSON.
    """
    config_path = Path(config_path_str)
    required_keys = ["name", "api_key", "base_url"]  # Updated to use standard field names

    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
    except json.JSONDecodeError:
        click.echo(f"Error: Could not decode JSON from file: {config_path}", err=True)
        return
    except Exception as e:
        click.echo(f"Error: Could not read config file {config_path}: {e}", err=True)
        return

    # Validate required keys
    missing_keys = [key for key in required_keys if key not in config_data]
    if missing_keys:
        click.echo(f"Error: The configuration file {config_path} is missing required keys: {', '.join(missing_keys)}", err=True)
        return

    config_name = config_data.get("config_name")
    if not isinstance(config_name, str) or not config_name.strip():
         click.echo(f"Error: 'config_name' in {config_path} must be a non-empty string.", err=True)
         return

    # Sanitize config_name to be used as a filename (basic example)
    safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in config_name.strip())
    if not safe_filename:
        click.echo(f"Error: 'config_name' \"{config_name}\" resulted in an invalid filename.", err=True)
        return

    destination_filename = f"{safe_filename}.json"
    destination_path = CONFIG_DIR / destination_filename

    try:
        # Create the target directory if it doesn't exist
        os.makedirs(CONFIG_DIR, exist_ok=True)
        click.echo(f"Ensured configuration directory exists: {CONFIG_DIR}", err=True)

        # Copy the original file to the destination
        shutil.copy2(config_path, destination_path) # copy2 preserves metadata like modification time
        click.echo(f"Successfully validated and saved configuration '{config_name}' to: {destination_path}")

    except OSError as e:
        click.echo(f"Error: Could not create directory {CONFIG_DIR}: {e}", err=True)
    except Exception as e:
        click.echo(f"Error: Could not copy configuration file to {destination_path}: {e}", err=True)


@account.command('add-config')
@click.option('--name', required=True, help='The unique name for this configuration.')
@click.option('--api-key', required=True, help='The Fiberwise API key.')
@click.option('--base-url', required=True, help='The Fiberwise API base URL (e.g., https://api.fiberwise.ai).')
@click.option('--set-default', is_flag=True, default=False, help='Set this configuration as the default.')
def add_config(name, api_key, base_url, set_default):
    """
    Adds a new Fiberwise configuration directly from command-line options.

    Saves the provided details (name, api-key, base-url) as a JSON file
    in the ~/.fiberwise/configs/ directory, named after the provided name.
    Optionally sets this configuration as the default for commands like 'install'.
    """
    config_name = name.strip()
    if not config_name:
         click.echo(f"Error: --name cannot be empty.", err=True)
         return

    # Construct the configuration data  
    config_data = {
        "name": config_name,
        "api_key": api_key,
        "base_url": base_url,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Sanitize config_name for filename
    safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in config_name)
    if not safe_filename:
        click.echo(f"Error: --name \"{config_name}\" resulted in an invalid filename.", err=True)
        return

    destination_filename = f"{safe_filename}.json"
    destination_path = CONFIG_DIR / destination_filename

    try:
        # Ensure the base Fiberwise directory exists first
        os.makedirs(FIBERWISE_DIR, exist_ok=True)
        # Then ensure the configs subdirectory exists
        os.makedirs(CONFIG_DIR, exist_ok=True)
        click.echo(f"Ensured configuration directory exists: {CONFIG_DIR}", err=True)

        # Write the configuration data to the destination file
        with open(destination_path, 'w') as f:
            json.dump(config_data, f, indent=2) # Use indent for readability

        click.echo(f"Successfully saved configuration '{config_name}' to: {destination_path}")

        # If --set-default flag is used, update the default config marker file
        if set_default:
            try:
                with open(DEFAULT_CONFIG_MARKER_FILE, 'w') as f:
                    f.write(config_name)
                click.echo(f"Successfully set '{config_name}' as the default configuration.")
            except Exception as e:
                click.echo(f"Warning: Could not set '{config_name}' as default. Error writing to {DEFAULT_CONFIG_MARKER_FILE}: {e}", err=True)

    except OSError as e:
        click.echo(f"Error: Could not create directory {CONFIG_DIR} or write file {destination_path}: {e}", err=True)
    except Exception as e:
        click.echo(f"Error: Could not save configuration file to {destination_path}: {e}", err=True)

def _load_config(config_name: str) -> Optional[Dict[str, Any]]:
    """Loads configuration data from the specified config name."""
    config_filename = f"{config_name}.json"
    config_path = CONFIG_DIR / config_filename

    if not config_path.exists():
        click.echo(f"Error: Configuration profile '{config_name}' not found.", err=True)
        click.echo(f"Expected location: {config_path}", err=True)
        click.echo("Use 'fw-util account login' or 'fw-util account add-config' to create it.", err=True)
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError:
        click.echo(f"Error: Could not decode JSON from config file: {config_path}", err=True)
        return None
    except Exception as e:
        click.echo(f"Error: Could not read config file {config_path}: {e}", err=True)
        return None

    # Extract required information - support both new and legacy field names
    api_key = config_data.get("api_key", config_data.get("fiberwise_api_key"))
    api_endpoint = config_data.get("base_url", config_data.get("fiberwise_base_url"))

    # Validate required keys from the loaded config
    if not api_key or not api_endpoint:
        missing = []
        if not api_key: missing.append("'api_key' (or 'fiberwise_api_key')")
        if not api_endpoint: missing.append("'base_url' (or 'fiberwise_base_url')")
        click.echo(f"Error: Config file {config_path} is missing required keys: {', '.join(missing)}", err=True)
        return None

    # Clean up endpoint URL (remove trailing slash if present)
    config_data["base_url"] = api_endpoint.rstrip('/')
    # Keep legacy field for backward compatibility
    config_data["fiberwise_base_url"] = api_endpoint.rstrip('/')
    return config_data

@account.command('list-configs')
def list_configs():
    """List all saved configurations and show their basic status."""
    try:
        # Check if configs directory exists
        if not CONFIG_DIR.exists():
            click.echo("No configurations found.")
            click.echo(f"Use 'fiber account add-config' to create a configuration.")
            return
        
        # Get all config files
        config_files = list(CONFIG_DIR.glob("*.json"))
        
        if not config_files:
            click.echo("No configurations found.")
            click.echo(f"Use 'fiber account add-config' to create a configuration.")
            return
        
        # Get default configuration
        default_config = get_default_config_name()
        
        click.echo("Available configurations:")
        click.echo("=" * 50)
        
        for config_file in sorted(config_files):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Get configuration details
                name = config_data.get('name', config_data.get('config_name', config_file.stem))
                base_url = config_data.get('base_url', config_data.get('fiberwise_base_url', 'N/A'))
                api_key = config_data.get('api_key', config_data.get('fiberwise_api_key', ''))
                
                # Create API key preview
                api_key_preview = f"{api_key[:8]}..." if len(api_key) > 8 else api_key
                
                # Check if this is the default
                is_default = (name == default_config)
                default_marker = " (default)" if is_default else ""
                
                # Test connection status (basic check)
                status = "Unknown"
                if base_url and base_url != 'N/A':
                    try:
                        import requests
                        response = requests.get(f"{base_url}/api/v1/health", timeout=3)
                        if response.status_code == 200:
                            status = "Connected"
                        else:
                            status = "Server Error"
                    except requests.exceptions.RequestException:
                        status = "Connection Failed"
                    except Exception:
                        status = " Unknown"
                
                click.echo(f" {name}{default_marker}")
                click.echo(f"   URL: {base_url}")
                click.echo(f"   API Key: {api_key_preview}")
                click.echo(f"   Status: {status}")
                click.echo()
                
            except Exception as e:
                click.echo(f"ERROR: Error reading {config_file.name}: {e}")
        
        if default_config:
            click.echo(f"Default configuration: {default_config}")
        else:
            click.echo("No default configuration set.")
            click.echo("Use 'fiber account add-config --set-default' to set one.")
        
    except Exception as e:
        click.echo(f"ERROR: Failed to list configurations: {e}", err=True)

def get_default_config_name() -> Optional[str]:
    """Reads the default configuration name from the marker file."""
    if DEFAULT_CONFIG_MARKER_FILE.exists():
        try:
            content = DEFAULT_CONFIG_MARKER_FILE.read_text().strip()
            if content:
                return content
        except Exception as e:
            click.echo(f"Warning: Could not read default config file {DEFAULT_CONFIG_MARKER_FILE}: {e}", err=True)
    return None

@account.command()
@click.option(
    '--app-id',
    required=False,  # Changed from required=True to optional
    help='The app ID to import model providers from. If not provided, tries to use the app ID from the current directory.'
)
@click.option(
    '--app-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True),
    default='.', 
    show_default=True,
    help='Path to the application directory containing .fw-data with app info (used when --app-id is not provided).'
)
@click.option(
    '--config-name',
    required=False,
    default=None,
    help='The configuration profile to use for API credentials.'
)
@click.option(
    '--save-to-file',
    is_flag=True,
    default=False,
    help='Save the provider information to a file in addition to displaying it.'
)
@click.option(
    '--format',
    type=click.Choice(['basic', 'detailed', 'json'], case_sensitive=False),
    default='basic',
    help='Output format: basic (default), detailed (more info), or json (full JSON output).'
)
@click.option(
    '--verbose',
    is_flag=True,
    default=False,
    help='Enable verbose output.'
)
@click.option(
    '--default',
    is_flag=True,
    default=False,
    help='Set the first provider found as the default provider.'
)
def import_providers(app_id, app_dir, config_name, save_to_file, format, verbose, default):
    """
    Import model providers information from the specified app ID.
    
    Makes an API call to retrieve model provider details and updates
    the local configuration with the provider IDs and basic information.
    
    If --app-id is not provided, attempts to read from local app info in --app-dir.
    If --default is provided, sets the first provider found as the default.
    
    Example:
        fw-util account import-providers --app-id app-123xyz --save-to-file
        fw-util account import-providers --save-to-file  # Uses app ID from local app info
        fw-util account import-providers --format detailed  # Show more provider details
        fw-util account import-providers --default  # Sets first provider as default
    """
    # If app_id is not provided, try to get it from local app info
    if not app_id:
        app_path = Path(app_dir)
        click.echo(f"No app ID provided, attempting to read from local app info in: {app_path}")
        
        local_app_info = load_local_app_info(app_path)
        if not local_app_info or not local_app_info.get("app_id"):
            click.echo(click.style("Error: No app ID provided and could not find app ID in local app info.", fg="red"), err=True)
            click.echo("Please provide --app-id parameter or run this command from an installed app directory.", err=True)
            return
        
        app_id = local_app_info.get("app_id")
        click.echo(f"Using app ID from local app info: {app_id}")
    
    # Get configuration
    effective_config_name = config_name or get_default_config_name()
    
    if not effective_config_name:
        click.echo(click.style("Error: No configuration name specified or found.", fg="red"), err=True)
        click.echo("Please specify --config-name or set a default configuration.", err=True)
        return
    
    config_data = _load_config(effective_config_name)
    if not config_data:
        return  # Error already reported by _load_config
    
    # Echo information about what we're doing
    click.echo(f"Using Configuration: {effective_config_name}")
    click.echo(f"Fetching model providers for App ID: {app_id}")
    
    # Prepare API call
    api_key = config_data.get("api_key", config_data.get("fiberwise_api_key"))
    api_endpoint = config_data.get("base_url", config_data.get("fiberwise_base_url"))
    providers_url = f"{api_endpoint}/api/v1/apps/{app_id}/model-providers"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # Make API request
        if verbose:
            click.echo(f"Making API request to: {providers_url}")
        
        response = requests.get(
            providers_url,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        # Process response
        providers_data = response.json()
        
        if not providers_data:
            click.echo(click.style("No model providers found for this app ID.", fg="yellow"))
            return
        
        # Display provider information
        provider_count = len(providers_data)
        click.echo(click.style(f"\nSuccessfully retrieved {provider_count} model providers:", fg="green"))
        
        # Store first provider if --default flag is used
        if default and providers_data:
            default_provider = providers_data[0]
            provider_id = default_provider.get("provider_id") or default_provider.get("id", "Unknown")
            provider_name = default_provider.get("name", "Unnamed Provider")
            provider_type = default_provider.get("provider_type") or default_provider.get("type", "Unknown")
            
            # Save default provider info
            os.makedirs(FIBERWISE_DIR, exist_ok=True)
            with open(DEFAULT_PROVIDER_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "id": provider_id,
                    "name": provider_name,
                    "type": provider_type,
                    "set_at": datetime.now().isoformat()
                }, f, indent=2)
            
            click.echo(click.style(f"\nSet {provider_name} ({provider_id}) as the default provider.", fg="green"))
        
        for i, provider in enumerate(providers_data):
            # Extract provider details with better fallbacks
            provider_id = provider.get("provider_id") or provider.get("id", "Unknown")
            provider_name = provider.get("name", "Unnamed Provider")
            provider_type = provider.get("provider_type") or provider.get("type", "Unknown")
            
            # Add a divider between providers
            if i > 0:
                click.echo("\n" + "-" * 50)
            
            # Display based on selected format
            if format == 'basic':
                click.echo(f"\n{i+1}. {provider_name} ({provider_type})")
                click.echo(f"   ID: {provider_id}")
                
                # Show available models if present
                if "configuration" in provider and provider["configuration"].get("models"):
                    models = provider["configuration"]["models"]
                    if len(models) <= 3:
                        click.echo(f"   Models: {', '.join(models)}")
                    else:
                        click.echo(f"   Models: {', '.join(models[:3])}... ({len(models)} total)")
                
                # Show default model if present
                if "configuration" in provider and provider["configuration"].get("default_model"):
                    click.echo(f"   Default model: {provider['configuration']['default_model']}")
                
            elif format == 'detailed':
                click.echo(f"\n{i+1}. {provider_name}")
                click.echo(f"   ID: {provider_id}")
                click.echo(f"   Type: {provider_type}")
                
                if provider.get("api_endpoint"):
                    click.echo(f"   API Endpoint: {provider['api_endpoint']}")
                    
                if provider.get("is_system"):
                    is_system = "Yes" if provider['is_system'] else "No"
                    click.echo(f"   System Provider: {is_system}")
                
                if provider.get("is_active"):
                    is_active = "Yes" if provider['is_active'] else "No"
                    click.echo(f"   Active: {is_active}")
                
                # Show API key (masked) if present
                if provider.get("api_key_masked"):
                    click.echo(f"   API Key: {provider['api_key_masked']}")
                    
                # Show configuration details if present
                if "configuration" in provider:
                    config = provider["configuration"]
                    click.echo("   Configuration:")
                    
                    if config.get("models"):
                        models = config["models"]
                        click.echo(f"     Models ({len(models)}):")
                        for model in models:
                            click.echo(f"       - {model}")
                    
                    if config.get("default_model"):
                        click.echo(f"     Default Model: {config['default_model']}")
                    
                    if config.get("temperature") is not None:
                        click.echo(f"     Temperature: {config['temperature']}")
                    
                    if config.get("max_tokens") is not None:
                        click.echo(f"     Max Tokens: {config['max_tokens']}")
                    
                    if config.get("additional_params"):
                        params = config["additional_params"]
                        if params:
                            click.echo("     Additional Parameters:")
                            for key, value in params.items():
                                click.echo(f"       {key}: {value}")
                
            elif format == 'json':
                # For JSON format, just dump the entire provider object
                safe_provider = {k: v for k, v in provider.items() 
                               if k not in ["api_key", "secret_key", "password"]}
                click.echo(f"\n{i+1}. {provider_name} (JSON):")
                click.echo(json.dumps(safe_provider, indent=2))
            
            # Always show verbose details if requested
            if verbose and format != 'json':
                # Filter out sensitive information
                safe_provider = {k: v for k, v in provider.items() 
                               if k not in ["api_key", "secret_key", "password"]}
                click.echo(f"\n   Full Details:")
                click.echo(json.dumps(safe_provider, indent=4))
        
        # Always save provider information, ensure it's not duplicated
        try:
            # Ensure providers directory exists
            os.makedirs(PROVIDERS_DIR, exist_ok=True)
            
            # Check for existing providers with same ID to avoid duplicates
            existing_providers = {}
            for file_path in PROVIDERS_DIR.glob('*.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                        
                    # Check if this is an app providers file
                    if isinstance(file_data, dict) and "providers" in file_data and isinstance(file_data["providers"], list):
                        for provider in file_data["providers"]:
                            provider_id = provider.get("provider_id") or provider.get("id")
                            if provider_id:
                                existing_providers[provider_id] = file_path.name
                                
                    # Check if this is an individual provider file
                    elif isinstance(file_data, dict):
                        provider_id = file_data.get("provider_id") or file_data.get("id")
                        if provider_id:
                            existing_providers[provider_id] = file_path.name
                except Exception:
                    continue
                    
            # Save to app-specific file
            provider_file = PROVIDERS_DIR / f"{app_id}-providers.json"
            
            # Add timestamp and source to the data
            output_data = {
                "app_id": app_id,
                "timestamp": datetime.now().isoformat(),
                "providers": providers_data
            }
            
            with open(provider_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
            
            if save_to_file:
                click.echo(click.style(f"\nProvider information saved to: {provider_file}", fg="green"))
            
            # Create separate files for providers to replace existing ones
            for provider in providers_data:
                provider_id = provider.get("provider_id") or provider.get("id")
                if provider_id:
                    provider_name = provider.get("name", "unnamed").lower().replace(" ", "_")
                    
                    # Check if provider already exists
                    if provider_id in existing_providers:
                        if verbose:
                            click.echo(f"Updating existing provider '{provider_name}' ({provider_id})")
                    
                    individual_file = PROVIDERS_DIR / f"{provider_name}_{provider_id}.json"
                    
                    with open(individual_file, 'w', encoding='utf-8') as f:
                        json.dump(provider, f, indent=2)
                    
                    if verbose and save_to_file:
                        click.echo(f"Provider '{provider_name}' saved to: {individual_file}")
            
        except Exception as e:
            click.echo(click.style(f"Error saving provider information: {e}", fg="red"), err=True)
            # Don't return here - we want to continue even if save fails
            
    except requests.exceptions.RequestException as e:
        click.echo(click.style(f"Error making API request: {e}", fg="red"), err=True)
        if hasattr(e, 'response') and e.response:
            try:
                error_detail = e.response.json().get('detail', e.response.text)
                click.echo(f"API response: {error_detail}", err=True)
            except:
                click.echo(f"API response status: {e.response.status_code}", err=True)
        return
    except Exception as e:
        click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
        return

@account.command()
@click.option(
    '--provider-id',
    required=False,
    help='ID of a specific provider to display. If not provided, lists all saved providers.'
)
@click.option(
    '--format',
    type=click.Choice(['basic', 'detailed', 'json'], case_sensitive=False),
    default='basic',
    help='Output format: basic (default), detailed (more info), or json (full JSON output).'
)
@click.option(
    '--to-instance', 
    default='local', 
    help="Target FiberWise instance: 'local' for direct access, or config name for remote API"
)
def list_providers(provider_id, format, to_instance):
    """
    List saved model providers.
    
    Displays information about model providers that have been previously imported
    and saved using the import-providers command, or added directly to the database.
    
    Example:
        fiber account list-providers
        fiber account list-providers --provider-id 5b9ef5b5-150b-46a2-a7bd-627c9a4cf9e4  
        fiber account list-providers --format detailed
        fiber account list-providers --to-instance "code fiber"
    """
    # Route based on to_instance
    try:
        instance_config = resolve_instance_config(to_instance)
        
        if instance_config['type'] == 'remote':
            # Use API to list providers from remote instance
            _list_providers_via_api(
                instance_config['base_url'], 
                instance_config['api_key'],
                provider_id, 
                format
            )
            return
        
        # Continue with local logic for 'local' instance
    except click.ClickException:
        raise
    except Exception as e:
        click.echo(f"Error resolving instance config: {e}", err=True)
        return
    
    providers_found = 0
    
    # First, try to get providers from database
    db_providers = []
    if DATABASE_INTEGRATION:
        try:
            db_providers = asyncio.run(_get_providers_from_database())
            if db_providers:
                click.echo(click.style("📊 Database Providers:", fg="green"))
                for provider in db_providers:
                    providers_found += 1
                    if format == 'basic':
                        click.echo(f"  {provider['name']} ({provider['provider_type']})")
                        click.echo(f"     Model: {provider.get('model', 'N/A')}")
                        click.echo(f"     Base URL: {provider.get('base_url', 'N/A')}")
                    elif format == 'detailed':
                        click.echo(f"\n  Provider: {provider['name']}")
                        click.echo(f"  Type: {provider['provider_type']}")
                        click.echo(f"  Model: {provider.get('model', 'N/A')}")
                        click.echo(f"  Base URL: {provider.get('base_url', 'N/A')}")
                        click.echo(f"  Max Tokens: {provider.get('max_tokens', 'N/A')}")
                        click.echo(f"  Temperature: {provider.get('temperature', 'N/A')}")
                        click.echo(f"  Created: {provider.get('created_at', 'N/A')}")
                        if provider.get('is_default'):
                            click.echo(f"  🌟 Default Provider")
                    elif format == 'json':
                        safe_provider = {k: v for k, v in provider.items() 
                                       if k not in ["api_key", "secret_key", "password"]}
                        click.echo(json.dumps(safe_provider, indent=2))
        except Exception as e:
            click.echo(click.style(f"WARNING: Could not load database providers: {e}", fg="yellow"))
    
    # Then check file-based providers
    file_providers_found = 0
    if PROVIDERS_DIR.exists():
        provider_files = list(PROVIDERS_DIR.glob('*.json'))
        if provider_files:
            if providers_found > 0:
                click.echo()  # Add spacing between database and file providers
            click.echo(click.style("📁 File-based Providers:", fg="blue"))
            
            # Process each file that might contain providers
            for file_path in provider_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Handle different file structures
                    if "providers" in data and isinstance(data["providers"], list):
                        # App-specific file with providers list
                        app_id = data.get("app_id", "Unknown")
                        click.echo(f"\n  From app {app_id} ({file_path.name}):")
                        
                        for i, provider in enumerate(data["providers"]):
                            file_providers_found += 1
                            provider_id_file = provider.get("provider_id") or provider.get("id", "Unknown")
                            provider_name = provider.get("name", "Unnamed Provider")
                            provider_type = provider.get("provider_type") or provider.get("type", "Unknown")
                            
                            if format == 'basic':
                                click.echo(f"    {i+1}. {provider_name} ({provider_type})")
                                click.echo(f"       ID: {provider_id_file}")
                            elif format == 'detailed':
                                click.echo(f"    {i+1}. {provider_name}")
                                click.echo(f"       ID: {provider_id_file}")
                                click.echo(f"       Type: {provider_type}")
                            elif format == 'json':
                                safe_provider = {k: v for k, v in provider.items() 
                                               if k not in ["api_key", "secret_key", "password"]}
                                click.echo(f"    {i+1}. {provider_name} (JSON):")
                                click.echo(json.dumps(safe_provider, indent=6))
                    
                    elif "name" in data and ("provider_id" in data or "id" in data):
                        # Individual provider file
                        file_providers_found += 1
                        provider_id_file = data.get("provider_id") or data.get("id", "Unknown")
                        provider_name = data.get("name", "Unnamed Provider")
                        provider_type = data.get("provider_type") or data.get("type", "Unknown")
                        
                        if format == 'basic':
                            click.echo(f"  {provider_name} ({provider_type})")
                            click.echo(f"    ID: {provider_id_file}")
                            click.echo(f"    Source: {file_path.name}")
                        elif format == 'detailed':
                            click.echo(f"  {provider_name}")
                            click.echo(f"    ID: {provider_id_file}")
                            click.echo(f"    Type: {provider_type}")
                            click.echo(f"    Source: {file_path.name}")
                        elif format == 'json':
                            safe_provider = {k: v for k, v in data.items() 
                                           if k not in ["api_key", "secret_key", "password"]}
                            click.echo(f"  {provider_name} (JSON):")
                            click.echo(json.dumps(safe_provider, indent=4))
                
                except Exception as e:
                    click.echo(f"  Error reading {file_path.name}: {e}", err=True)
            
            providers_found += file_providers_found
    
    # Summary
    if providers_found == 0:
        click.echo(click.style("No saved provider information found.", fg="yellow"))
        if DATABASE_INTEGRATION:
            click.echo("Try adding providers with: fiber account add-provider --help")
        else:
            click.echo("Run import-providers first or install database integration.")
    else:
        click.echo(f"\n📈 Total providers found: {providers_found}")
        if DATABASE_INTEGRATION and db_providers:
            click.echo(f"   Database: {len(db_providers)}")
        if file_providers_found > 0:
            click.echo(f"   Files: {file_providers_found}")

# Add a new provider command group
@account.group('provider')
def provider():
    """
    Manage model providers.
    
    This command group provides tools for working with model providers,
    including listing available providers and setting defaults.
    """
    pass

@provider.command('list')
@click.option(
    '--type',
    'provider_type',
    type=click.Choice(['all', 'llm', 'storage', 'embedding', 'reranker'], case_sensitive=False),
    default='all',
    help='Filter providers by type.'
)
@click.option(
    '--format',
    type=click.Choice(['basic', 'detailed', 'json'], case_sensitive=False),
    default='basic',
    help='Output format: basic (default), detailed (more info), or json (full JSON output).'
)
def list_providers_by_type(provider_type, format):
    """
    List saved model providers grouped by type.
    
    Displays information about model providers that have been previously imported
    and saved using the import-providers command, grouped by their type.
    
    Example:
        fw-util account provider list
        fw-util account provider list --type llm
        fw-util account provider list --format detailed
    """
    # Ensure providers directory exists
    if not PROVIDERS_DIR.exists():
        click.echo(click.style("No providers directory found. Run import-providers first.", fg="yellow"))
        return
    
    # Look for provider files
    provider_files = list(PROVIDERS_DIR.glob('*.json'))
    if not provider_files:
        click.echo(click.style("No saved provider information found.", fg="yellow"))
        return
    
    # Get the default provider for marking in the list
    default_provider_id = None
    if DEFAULT_PROVIDER_FILE.exists():
        try:
            with open(DEFAULT_PROVIDER_FILE, 'r', encoding='utf-8') as f:
                default_data = json.load(f)
                default_provider_id = default_data.get("id")
        except Exception:
            pass
    
    # Extract and organize providers by type
    providers_by_type = {}
    total_providers = 0
    
    # Track provider IDs to avoid duplicates
    seen_provider_ids = set()
    
    for file_path in provider_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Handle both individual provider files and app provider files
            if "providers" in data and isinstance(data["providers"], list):
                # App-specific file with providers list
                for provider in data["providers"]:
                    provider_id = provider.get("provider_id") or provider.get("id", "Unknown")
                    
                    # Skip if we've already seen this provider
                    if provider_id in seen_provider_ids:
                        continue
                    
                    seen_provider_ids.add(provider_id)
                    
                    provider_name = provider.get("name", "Unnamed Provider")
                    provider_type_str = provider.get("provider_type") or provider.get("type", "Unknown")
                    
                    # Normalize provider type for grouping
                    normalized_type = _normalize_provider_type(provider_type_str)
                    
                    # Skip if we're filtering by type and this doesn't match
                    if provider_type != 'all' and normalized_type != provider_type.lower():
                        continue
                    
                    # Add to the appropriate group
                    if normalized_type not in providers_by_type:
                        providers_by_type[normalized_type] = []
                    
                    # Add source file info to provider data
                    provider["_source_file"] = str(file_path)
                    
                    # Add to the providers list for this type
                    providers_by_type[normalized_type].append(provider)
                    total_providers += 1
                    
            elif "name" in data and ("provider_id" in data or "id" in data):
                # Individual provider file
                provider_id = data.get("provider_id") or data.get("id", "Unknown")
                
                # Skip if we've already seen this provider
                if provider_id in seen_provider_ids:
                    continue
                
                seen_provider_ids.add(provider_id)
                
                provider_name = data.get("name", "Unnamed Provider")
                provider_type_str = data.get("provider_type") or data.get("type", "Unknown")
                
                # Normalize provider type for grouping
                normalized_type = _normalize_provider_type(provider_type_str)
                
                # Skip if we're filtering by type and this doesn't match
                if provider_type != 'all' and normalized_type != provider_type.lower():
                    continue
                
                # Add to the appropriate group
                if normalized_type not in providers_by_type:
                    providers_by_type[normalized_type] = []
                
                # Add source file info to provider data
                data["_source_file"] = str(file_path)
                
                # Add to the providers list for this type
                providers_by_type[normalized_type].append(data)
                total_providers += 1
                
        except Exception as e:
            click.echo(f"Error reading {file_path.name}: {e}", err=True)
    
    if total_providers == 0:
        click.echo("No providers found matching the specified criteria.")
        return
    
    # Display providers grouped by type
    click.echo(click.style(f"\nFound {total_providers} providers across {len(providers_by_type)} types:", fg="green"))
    
    # Sort provider types for consistent output
    sorted_types = sorted(providers_by_type.keys())
    
    for provider_type_key in sorted_types:
        providers_list = providers_by_type[provider_type_key]
        click.echo(click.style(f"\n{provider_type_key.upper()} Providers ({len(providers_list)}):", fg="cyan", bold=True))
        
        # Sort providers by name within each type
        sorted_providers = sorted(providers_list, key=lambda x: x.get("name", "").lower())
        
        for i, provider in enumerate(sorted_providers):
            provider_id = provider.get("provider_id") or provider.get("id", "Unknown")
            provider_name = provider.get("name", "Unnamed Provider")
            
            # Mark the default provider with an asterisk
            is_default = (provider_id == default_provider_id)
            default_marker = " [DEFAULT]" if is_default else ""
            
            if format == 'basic':
                click.echo(f"  {i+1}. {provider_name}{default_marker}")
                click.echo(f"     ID: {provider_id}")
                
                # Show models if available
                if "configuration" in provider and provider["configuration"].get("models"):
                    models = provider["configuration"]["models"]
                    if len(models) <= 3:
                        click.echo(f"     Models: {', '.join(models)}")
                    else:
                        click.echo(f"     Models: {', '.join(models[:3])}... ({len(models)} total)")
                
            elif format == 'detailed':
                click.echo(f"  {i+1}. {provider_name}{default_marker}")
                click.echo(f"     ID: {provider_id}")
                
                # Show API endpoint if available
                if provider.get("api_endpoint"):
                    click.echo(f"     API Endpoint: {provider['api_endpoint']}")
                
                # Show system and active flags if available
                if provider.get("is_system") is not None:
                    click.echo(f"     System Provider: {'Yes' if provider['is_system'] else 'No'}")
                if provider.get("is_active") is not None:
                    click.echo(f"     Active: {'Yes' if provider['is_active'] else 'No'}")
                
                # Show API key (masked) if available
                if provider.get("api_key_masked"):
                    click.echo(f"     API Key: {provider['api_key_masked']}")
                
                # Show configuration details if available
                if "configuration" in provider:
                    config = provider["configuration"]
                    click.echo("     Configuration:")
                    
                    if config.get("models"):
                        models = config["models"]
                        click.echo(f"       Models ({len(models)}):")
                        for model in models:
                            click.echo(f"         - {model}")
                    
                    if config.get("default_model"):
                        click.echo(f"       Default Model: {config['default_model']}")
                    
                    if config.get("temperature") is not None:
                        click.echo(f"       Temperature: {config['temperature']}")
                    
                    if config.get("max_tokens") is not None:
                        click.echo(f"       Max Tokens: {config['max_tokens']}")
                
            elif format == 'json':
                # Filter out sensitive information
                safe_provider = {k: v for k, v in provider.items() 
                               if k not in ["api_key", "secret_key", "password"]}
                
                # Add default indicator
                safe_provider["is_default"] = is_default
                
                click.echo(f"  {i+1}. {provider_name}")
                click.echo(json.dumps(safe_provider, indent=2))
    
    click.echo(f"\nTotal providers: {total_providers}")
    
    # Show default provider info
    if default_provider_id:
        click.echo(click.style("\nDefault provider is set.", fg="green"))
    else:
        click.echo(click.style("\nNo default provider set. Use 'fw-util account provider default NAME' to set one.", fg="yellow"))

def _normalize_provider_type(provider_type_str):
    """Normalize provider type string for consistent grouping."""
    provider_type_lower = provider_type_str.lower()
    
    # Map various type strings to standard categories
    if any(term in provider_type_lower for term in ['llm', 'language', 'chat', 'openai', 'google', 'anthropic', 'gemini', 'claude']):
        return 'llm'
    elif any(term in provider_type_lower for term in ['storage', 'file', 's3', 'blob']):
        return 'storage'
    elif any(term in provider_type_lower for term in ['embed', 'embedding', 'text-embedding']):
        return 'embedding'
    elif any(term in provider_type_lower for term in ['rerank', 'reranker']):
        return 'reranker'
    else:
        return 'other'

@provider.command('default')
@click.argument('provider_name', required=True)
def set_default_provider(provider_name):
    """
    Set a provider as the default by name.
    
    Sets the specified provider as the default for use in applications.
    The provider must have been previously imported.
    
    Example:
        fw-util account provider default "OpenAI"
        fw-util account provider default "Google Gemini"
    """
    # Ensure providers directory exists
    if not PROVIDERS_DIR.exists():
        click.echo(click.style("No providers directory found. Run import-providers first.", fg="yellow"))
        return
    
    # Look for provider files
    provider_files = list(PROVIDERS_DIR.glob('*.json'))
    if not provider_files:
        click.echo(click.style("No saved provider information found.", fg="yellow"))
        return
    
    # Search for the provider by name (case-insensitive)
    provider_name_lower = provider_name.lower()
    matching_provider = None
    
    for file_path in provider_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Handle both individual provider files and app provider files
            if "providers" in data and isinstance(data["providers"], list):
                # App-specific file with providers list
                for provider in data["providers"]:
                    if provider.get("name", "").lower() == provider_name_lower:
                        matching_provider = provider
                        break
                        
            elif "name" in data and data.get("name", "").lower() == provider_name_lower:
                # Individual provider file
                matching_provider = data
                
            if matching_provider:
                break
                
        except Exception as e:
            click.echo(f"Error reading {file_path.name}: {e}", err=True)
    
    if not matching_provider:
        click.echo(click.style(f"Error: No provider found with name '{provider_name}'.", fg="red"))
        click.echo("Use 'fw-util account provider list' to see available providers.")
        return
    
    # Extract provider details
    provider_id = matching_provider.get("provider_id") or matching_provider.get("id", "Unknown")
    provider_type = matching_provider.get("provider_type") or matching_provider.get("type", "Unknown")
    
    # Save as default provider
    try:
        os.makedirs(FIBERWISE_DIR, exist_ok=True)
        with open(DEFAULT_PROVIDER_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "id": provider_id,
                "name": provider_name,
                "type": provider_type,
                "set_at": datetime.now().isoformat()
            }, f, indent=2)
            
        click.echo(click.style(f"Successfully set '{provider_name}' (ID: {provider_id}) as the default provider.", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Error setting default provider: {e}", fg="red"))


@account.command('add-provider')
@click.option('--provider', required=True, type=click.Choice(['openai', 'anthropic', 'google', 'local', 'mock']), help='The provider type to add.')
@click.option('--api-key', required=True, help='The API key for the provider.')
@click.option('--model', help='The model to use (uses provider default if not specified).')
@click.option('--base-url', help='The base URL for the API (uses provider default if not specified).')
@click.option('--name', help='Custom name for the provider (auto-generated if not specified).')
@click.option('--set-default', is_flag=True, default=False, help='Set this provider as the default.')
@click.option('--to-instance', help='Target FiberWise instance config name (uses default if not specified).')
def add_provider(provider, api_key, model, base_url, name, set_default, to_instance):
    """
    Add a new LLM provider with API key to a FiberWise instance via API.
    
    This command uses a smart configuration chain to determine the target FiberWise instance:
    1. Specified --to-instance configuration
    2. Default configuration (if available)
    
    A FiberWise instance configuration is required. Use 'fiber account add-config' first.
    
    Example:
        fiber account add-config --name myinstance --api-key API_KEY --base-url https://api.example.com
        fiber account add-provider --provider google --api-key GOOGLE_KEY --to-instance myinstance
    """
    # Default configurations for common providers
    provider_defaults = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo"
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com",
            "model": "claude-3-sonnet-20240229"
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com",
            "model": "gemini-pro"
        },
        "local": {
            "base_url": "http://localhost:1234/v1",
            "model": "local-model"
        },
        "mock": {
            "base_url": "https://mock.api.com",
            "model": "mock-model"
        }
    }
    
    # Get defaults for this provider type
    defaults = provider_defaults.get(provider, {})
    
    # Generate provider name
    provider_name = name or f"{provider.title()} Provider"
    
    # Use provided values or defaults for LLM provider settings
    final_model = model or defaults.get("model", "default-model")
    final_base_url = base_url or defaults.get("base_url", "https://api.example.com")
    
    # SMART FALLBACK CHAIN: Determine target FiberWise instance
    target_config = None
    method_used = "unknown"
    
    # Option 1: Specific instance config
    if to_instance:
        target_config = load_config(to_instance)
        if target_config:
            method_used = f"config '{to_instance}'"
        else:
            click.echo(click.style(f"ERROR: Config '{to_instance}' not found.", fg="red"))
            return
            
    # Option 2: Default config
    else:
        default_config_name = get_default_config_name()
        if default_config_name:
            target_config = load_config(default_config_name)
            if target_config:
                method_used = f"default config '{default_config_name}'"
    
    # Try API approach if we have FiberWise config
    if target_config:
        try:
            # Validate required config keys
            if 'base_url' not in target_config:
                click.echo(click.style("ERROR: Configuration missing 'base_url' key", fg="red"))
                return
            if 'api_key' not in target_config:
                click.echo(click.style("ERROR: Configuration missing 'api_key' key", fg="red"))
                return
                
            click.echo(f"Using {method_used}")
            click.echo(f"   URL: {target_config['base_url']}")
            
            # Prepare API payload
            provider_data = {
                "name": provider_name,
                "provider_type": provider,
                "api_key": api_key,
                "api_endpoint": final_base_url,
                "model": final_model,
                "is_active": True
            }
            
            # Make API call
            result = asyncio.run(add_provider_via_api(
                base_url=target_config['base_url'],
                api_key=target_config['api_key'],
                provider_data=provider_data
            ))
            
            click.echo(click.style(f"Successfully added {provider} provider via API: {provider_name}", fg="green"))
            if set_default:
                click.echo(click.style("Set as default provider", fg="green"))
            return
            
        except Exception as e:
            click.echo(click.style(f"API call failed: {e}", fg="red"))
            click.echo(click.style("Falling back to local database...", fg="yellow"))
            
            # Fallback: Save to local database directly
            try:
                import uuid
                provider_id = str(uuid.uuid4())
                
                db_provider_name = asyncio.run(_save_provider_to_database(
                    provider_type=provider,
                    provider_id=provider_id,
                    provider_name=provider_name,
                    api_key=api_key,
                    model=final_model,
                    base_url=final_base_url,
                    set_default=set_default
                ))
                
                click.echo(click.style(f"Successfully added {provider} provider to local database: {db_provider_name}", fg="green"))
                if set_default:
                    click.echo(click.style("Set as default provider", fg="green"))
                return
                
            except Exception as db_error:
                click.echo(click.style(f"Local database save also failed: {db_error}", fg="red"))
                return
    
    # No FiberWise config available - use local database directly
    click.echo(click.style("No FiberWise configuration available. Using local database...", fg="yellow"))
    
    try:
        import uuid
        provider_id = str(uuid.uuid4())
        
        db_provider_name = asyncio.run(_save_provider_to_database(
            provider_type=provider,
            provider_id=provider_id,
            provider_name=provider_name,
            api_key=api_key,
            model=final_model,
            base_url=final_base_url,
            set_default=set_default
        ))
        
        click.echo(click.style(f"Successfully added {provider} provider to local database: {db_provider_name}", fg="green"))
        if set_default:
            click.echo(click.style("Set as default provider", fg="green"))
        return
        
    except Exception as db_error:
        click.echo(click.style(f"Local database save failed: {db_error}", fg="red"))
        click.echo("Please check that the FiberWise database is accessible.")
        return


async def _get_providers_from_database():
    """Get all providers from the database using AccountService."""
    try:
        # Initialize database manager
        settings = BaseWebSettings()
        db_manager = DatabaseManager.create_from_settings(settings)
        await db_manager.initialize()
        
        # Create provider service
        provider_service = ProviderService(db_manager.provider)
        
        # Get all provider configurations
        configs = await provider_service.get_provider_configs()
        
        # Close database connection
        try:
            await db_manager.cleanup()
        except AttributeError:
            pass
        
        return configs
        
    except Exception as e:
        raise Exception(f"Database query failed: {e}")


async def _save_provider_to_database(provider_type, provider_id, provider_name, api_key, model, base_url, set_default=False):
    """Save provider configuration to database using ProviderService."""
    try:
        # Initialize database manager
        settings = BaseWebSettings()
        db_manager = DatabaseManager.create_from_settings(settings)
        await db_manager.initialize()
        
        # Create provider service
        provider_service = ProviderService(db_manager.provider)
        
        # Save to database using the provided name
        db_config = await provider_service.add_provider_config(
            name=provider_name,  # Use the actual provider name
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=1000,
            temperature=0.7
        )
        
        # Set as default if specified
        if set_default:
            await provider_service.set_default_provider(provider_name)
        
        # Close database connection
        try:
            await db_manager.cleanup()
        except AttributeError:
            # DatabaseManager might not have cleanup method
            pass
        
        return db_config['name']
        
    except Exception as e:
        raise Exception(f"Database save failed: {e}")



import click
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

@click.group()
def config():
    """Manage FiberWise configuration profiles."""
    pass

@config.command()
@click.option('--name', required=True, help='The unique name for this configuration.')
@click.option('--api-key', required=True, help='The Fiberwise API key.')
@click.option('--base-url', required=True, help='The Fiberwise API base URL (e.g., https://api.fiberwise.ai).')
@click.option('--set-default', is_flag=True, help='Set this configuration as the default.')
def add(name: str, api_key: str, base_url: str, set_default: bool = False):
    """
    Saves the provided details (name, api-key, base-url) as a JSON file in the
    ~/.fiberwise/configs/ directory, named after the provided name. Optionally
    sets this configuration as the default for commands like 'install'.
    """
    try:
        # Create configs directory
        configs_dir = Path.home() / ".fiberwise" / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare configuration data
        config_data = {
            "name": name,
            "api_key": api_key,
            "base_url": base_url.rstrip('/'),  # Remove trailing slash
            "created_at": click.DateTime().convert(None, None, click.get_current_context()),
            "updated_at": click.DateTime().convert(None, None, click.get_current_context())
        }
        
        # Save configuration file
        config_file = configs_dir / f"{name}.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2, default=str)
        
        click.echo(f"✅ Configuration '{name}' saved to {config_file}")
        
        # Set as default if requested
        if set_default:
            _set_default_config(name)
            click.echo(f"✅ Configuration '{name}' set as default")
        
    except Exception as e:
        click.echo(f"❌ Failed to save configuration: {e}", err=True)
        return False
    
    return True

@config.command()
def list():
    """List all saved configurations."""
    try:
        configs_dir = Path.home() / ".fiberwise" / "configs"
        
        if not configs_dir.exists():
            click.echo("No configurations found. Use 'fiber config add' to create one.")
            return
        
        config_files = list(configs_dir.glob("*.json"))
        
        if not config_files:
            click.echo("No configurations found. Use 'fiber config add' to create one.")
            return
        
        # Get default config
        default_config = _get_default_config()
        
        click.echo("Available configurations:")
        click.echo("=" * 40)
        
        for config_file in sorted(config_files):
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                
                name = config_data.get('name', config_file.stem)
                base_url = config_data.get('base_url', 'N/A')
                api_key_preview = config_data.get('api_key', '')
                api_key_preview = f"{api_key_preview[:8]}..." if len(api_key_preview) > 8 else api_key_preview
                
                default_marker = " (default)" if name == default_config else ""
                
                click.echo(f"📋 {name}{default_marker}")
                click.echo(f"   URL: {base_url}")
                click.echo(f"   API Key: {api_key_preview}")
                click.echo()
                
            except Exception as e:
                click.echo(f"❌ Error reading {config_file.name}: {e}")
        
    except Exception as e:
        click.echo(f"❌ Failed to list configurations: {e}", err=True)

@config.command()
@click.argument('name')
def remove(name: str):
    """Remove a configuration."""
    try:
        configs_dir = Path.home() / ".fiberwise" / "configs"
        # Sanitize config name for filename
        safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
        config_file = configs_dir / f"{safe_filename}.json"
        
        if not config_file.exists():
            click.echo(f"❌ Configuration '{name}' not found.")
            return False
        
        config_file.unlink()
        click.echo(f"✅ Configuration '{name}' removed.")
        
        # If this was the default, clear the default
        if _get_default_config() == name:
            _clear_default_config()
            click.echo("ℹ️  Default configuration cleared.")
        
        return True
        
    except Exception as e:
        click.echo(f"❌ Failed to remove configuration: {e}", err=True)
        return False

@config.command()
@click.argument('name')
def set_default(name: str):
    """Set a configuration as the default."""
    try:
        configs_dir = Path.home() / ".fiberwise" / "configs"
        # Sanitize config name for filename
        safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
        config_file = configs_dir / f"{safe_filename}.json"
        
        if not config_file.exists():
            click.echo(f"❌ Configuration '{name}' not found.")
            return False
        
        _set_default_config(name)
        click.echo(f"✅ Configuration '{name}' set as default.")
        return True
        
    except Exception as e:
        click.echo(f"❌ Failed to set default configuration: {e}", err=True)
        return False

@config.command()
def get_default():
    """Show the current default configuration."""
    try:
        default_name = _get_default_config()
        
        if not default_name:
            click.echo("No default configuration set.")
            return
        
        # Load and display default config
        configs_dir = Path.home() / ".fiberwise" / "configs"
        # Sanitize config name for filename
        safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in default_name)
        config_file = configs_dir / f"{safe_filename}.json"
        
        if not config_file.exists():
            click.echo(f"❌ Default configuration '{default_name}' file not found.")
            _clear_default_config()
            return
        
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        click.echo(f"Default configuration: {default_name}")
        click.echo(f"URL: {config_data.get('base_url', 'N/A')}")
        api_key = config_data.get('api_key', '')
        api_key_preview = f"{api_key[:8]}..." if len(api_key) > 8 else api_key
        click.echo(f"API Key: {api_key_preview}")
        
    except Exception as e:
        click.echo(f"❌ Failed to get default configuration: {e}", err=True)

def _set_default_config(name: str):
    """Set a configuration as default."""
    fiberwise_dir = Path.home() / ".fiberwise"
    default_file = fiberwise_dir / "default_config.txt"
    
    with open(default_file, 'w') as f:
        f.write(name)

def _get_default_config() -> Optional[str]:
    """Get the default configuration name."""
    fiberwise_dir = Path.home() / ".fiberwise"
    default_file = fiberwise_dir / "default_config.txt"
    
    if default_file.exists():
        try:
            with open(default_file, 'r') as f:
                return f.read().strip()
        except:
            return None
    
    return None

def _clear_default_config():
    """Clear the default configuration."""
    fiberwise_dir = Path.home() / ".fiberwise"
    default_file = fiberwise_dir / "default_config.txt"
    
    if default_file.exists():
        default_file.unlink()

def load_config(name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load a configuration by name, or the default configuration.
    
    Args:
        name: Configuration name. If None, loads the default configuration.
        
    Returns:
        Configuration data dict or None if not found.
    """
    try:
        if name is None:
            name = _get_default_config()
            if name is None:
                return None
        
        configs_dir = Path.home() / ".fiberwise" / "configs"
        # Sanitize config name for filename (same logic as account.py)
        safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
        config_file = configs_dir / f"{safe_filename}.json"
        
        if not config_file.exists():
            return None
        
        with open(config_file, 'r') as f:
            return json.load(f)
            
    except Exception as e:
        # For debugging - show what's failing
        click.echo(f"DEBUG: Config loading failed for '{name}': {e}", err=True)
        return None

def get_api_credentials(config_name: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """
    Get API key and base URL from configuration.
    
    Args:
        config_name: Configuration name. If None, uses default.
        
    Returns:
        Tuple of (api_key, base_url) or (None, None) if not found.
    """
    # Try loading from named config
    config_data = load_config(config_name)
    if config_data:
        return config_data.get('api_key'), config_data.get('base_url')
    
    return None, None

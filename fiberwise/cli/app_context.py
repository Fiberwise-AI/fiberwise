"""
Centralized context for all app operations.
"""
import click
from pathlib import Path
from typing import Optional

from fiberwise_common.services.fiber_app_manager import (
    FiberAppManager, 
    validate_instance_config,
    get_default_instance_config,
    load_instance_config
)
from .app_utils import (
    find_manifest_file, 
    load_manifest,
    load_instance_app_info,
)


class AppOperationContext:
    """Centralized context for all app operations that handles instance resolution and configuration."""
    
    def __init__(self, app_path: Path, to_instance: Optional[str] = None, config: Optional[str] = None, verbose: bool = False):
        self.app_path = app_path
        self.verbose = verbose
        self.instance_name = None
        self.config_data = None
        self.app_manager = None
        self.app_info = None
        self.manifest_path = None
        self.manifest_data = None
        
        # Resolve instance name using the hierarchy: to_instance -> config -> last_instance -> default
        self._resolve_instance(to_instance, config)
        
        # Load and validate configuration
        self._load_configuration()
        
        # Load app info and manifest
        self._load_app_context()
    
    def _resolve_instance(self, to_instance: Optional[str], config: Optional[str]):
        """Resolve which instance to use with proper fallback hierarchy."""
        # Priority 1: Explicit --to-instance parameter
        if to_instance:
            self.instance_name = to_instance
            if self.verbose:
                click.echo(f"🎯 Using specified instance: {to_instance}")
            return
        
        # Priority 2: --config parameter  
        if config:
            self.instance_name = config
            if self.verbose:
                click.echo(f"🔧 Using config instance: {config}")
            return
        
        # Priority 3: Default instance configuration
        try:
            default_instance = get_default_instance_config()
            if default_instance:
                self.instance_name = default_instance
                if self.verbose:
                    click.echo(f"🏠 Using default instance: {default_instance}")
                return
        except Exception:
            pass
        
        # No instance could be resolved
        raise click.ClickException(
            "❌ No instance specified and no default configuration found.\n"
            "   Use --to-instance parameter or set a default with 'fiber account set-default'"
        )
    
    def _load_configuration(self):
        """Load and validate the instance configuration."""
        try:
            # Validate the instance name exists
            validated_instance = validate_instance_config(self.instance_name)
            self.instance_name = validated_instance
            
            # Load the actual configuration data
            self.config_data = load_instance_config(self.instance_name)
            
            if self.verbose:
                base_url = self.config_data.get('base_url', 'Unknown')
                click.echo(f"✅ Configuration loaded for instance: {self.instance_name}")
                click.echo(f"   Base URL: {base_url}")
            
        except ValueError as e:
            raise click.ClickException(f"❌ Configuration error: {e}")
        except Exception as e:
            raise click.ClickException(f"❌ Error loading configuration: {e}")
    
    def _load_app_context(self):
        """Load app-related context (manifest, app info)."""
        # Load manifest
        try:
            self.manifest_path = find_manifest_file(self.app_path)
            if self.manifest_path:
                self.manifest_data, _ = load_manifest(self.manifest_path, return_format=True)
                if self.verbose:
                    app_name = self.manifest_data.get('app', {}).get('name', 'Unknown')
                    app_version = self.manifest_data.get('app', {}).get('version', 'Unknown')
                    click.echo(f"📱 App: {app_name} v{app_version}")
        except Exception as e:
            if self.verbose:
                click.echo(f"⚠️  Could not load manifest: {e}")
        
        # Load app info for this instance
        try:
            self.app_info = load_instance_app_info(self.app_path, self.instance_name)
            if self.app_info and self.verbose:
                app_id = self.app_info.get('app_id', 'Unknown')
                click.echo(f"📋 App ID: {app_id}")
        except Exception as e:
            if self.verbose:
                click.echo(f"⚠️  Could not load app info: {e}")
    
    def get_app_manager(self) -> FiberAppManager:
        """Get a configured app manager instance."""
        if not self.app_manager:
            try:
                self.app_manager = FiberAppManager.from_instance_config(self.instance_name)
            except Exception as e:
                raise click.ClickException(f"❌ Error creating app manager: {e}")
        return self.app_manager
    
    def get_app_id(self) -> Optional[str]:
        """Get the app ID from loaded app info."""
        return self.app_info.get('app_id') if self.app_info else None
    
    def get_api_config(self) -> tuple[str, str]:
        """Get base URL and API key for API calls."""
        base_url = self.config_data.get('base_url', '').rstrip('/')
        api_key = self.config_data.get('api_key', '')
        return base_url, api_key
    
    def has_valid_api_config(self) -> bool:
        """Check if we have valid API configuration."""
        base_url, api_key = self.get_api_config()
        return bool(base_url and api_key)

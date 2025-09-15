"""
Utility functions for app manifest management and version handling.
"""

import re
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from packaging import version
from datetime import datetime

import yaml

from fiberwise_common.utils.file_utils import load_manifest

# Static configuration variables
FIBER_DATA_DIR = '.fiber'
APP_INFO_FILE = 'app.json'


def parse_version(version_string: str) -> version.Version:
    """Parse a version string into a Version object."""
    try:
        return version.parse(version_string)
    except version.InvalidVersion:
        # Fallback for invalid versions - treat as 0.0.0
        return version.parse("0.0.0")


def increment_version(current_version: str, increment_type: str = "patch") -> str:
    """
    Increment a semantic version string.
    
    Args:
        current_version: Current version string (e.g., "1.2.3")
        increment_type: Type of increment - "major", "minor", or "patch"
    
    Returns:
        New version string
    """
    try:
        v = parse_version(current_version)
        
        if increment_type == "major":
            return f"{v.major + 1}.0.0"
        elif increment_type == "minor":
            return f"{v.major}.{v.minor + 1}.0"
        else:  # patch
            return f"{v.major}.{v.minor}.{v.micro + 1}"
    except Exception:
        # Fallback if parsing fails
        return "0.0.1"




def save_manifest(manifest_path: Path, manifest_data: Dict[str, Any], file_format: str = 'yaml'):
    """
    Save app manifest to file.
    
    Args:
        manifest_path: Path to save the manifest
        manifest_data: Manifest data dictionary
        file_format: 'yaml' or 'json'
    """
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            if file_format == 'json':
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)
            else:
                yaml.dump(manifest_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        raise Exception(f"Failed to save manifest to {manifest_path}: {e}")


def find_manifest_file(app_dir: Path) -> Optional[Path]:
    """
    Find the app manifest file in the given directory.
    
    Returns:
        Path to the manifest file, or None if not found
    """
    # Try different manifest file names in order of preference
    manifest_candidates = [
        'app_manifest.yaml',
        'app_manifest.yml', 
        'app_manifest.json',
        'manifest.yaml',
        'manifest.yml',
        'manifest.json'
    ]
    
    for candidate in manifest_candidates:
        manifest_path = app_dir / candidate
        if manifest_path.exists():
            return manifest_path
    
    return None


def update_manifest_version(app_dir: Path, increment_type: str = "patch", verbose: bool = False) -> Optional[str]:
    """
    Update the version in the app manifest file.
    
    Args:
        app_dir: App directory containing the manifest
        increment_type: Type of version increment ("major", "minor", "patch")
        verbose: Enable verbose output
    
    Returns:
        New version string, or None if update failed
    """
    try:
        # Find manifest file
        manifest_path = find_manifest_file(app_dir)
        if not manifest_path:
            if verbose:
                print("❌ No manifest file found for version update")
            return None
        
        # Load current manifest to get version
        manifest_data, file_format = load_manifest(manifest_path, return_format=True)
        
        # Get current version
        current_version = manifest_data.get('app', {}).get('version', '0.0.0')
        if verbose:
            print(f"📦 Current version: {current_version}")
        
        # Increment version
        new_version = increment_version(current_version, increment_type)
        if verbose:
            print(f"📦 New version: {new_version}")
        
        # Update only the version line in the file, preserving original formatting
        update_version_in_file(manifest_path, current_version, new_version, file_format)
        
        if verbose:
            print(f"✅ Updated manifest version to {new_version}")
        
        return new_version
        
    except Exception as e:
        if verbose:
            print(f"❌ Error updating manifest version: {e}")
        return None


def update_version_in_file(manifest_path: Path, old_version: str, new_version: str, file_format: str):
    """
    Update only the version line in the manifest file, preserving formatting.
    
    Args:
        manifest_path: Path to the manifest file
        old_version: Current version string
        new_version: New version string
        file_format: 'yaml' or 'json'
    """
    try:
        # Read the file content
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if file_format == 'json':
            # For JSON, replace the version value
            import re
            pattern = rf'"version"\s*:\s*"{re.escape(old_version)}"'
            replacement = f'"version": "{new_version}"'
            updated_content = re.sub(pattern, replacement, content)
        else:
            # For YAML, replace the version value, handling various formatting
            import re
            # Match version: value patterns (with or without quotes, with various spacing)
            patterns = [
                rf'(\s*version\s*:\s*){re.escape(old_version)}(\s*)',
                rf'(\s*version\s*:\s*"){re.escape(old_version)}(")',
                rf"(\s*version\s*:\s*'){re.escape(old_version)}(')",
            ]
            
            updated_content = content
            for pattern in patterns:
                if re.search(pattern, content):
                    # Preserve the original formatting (quotes, spacing)
                    updated_content = re.sub(pattern, rf'\g<1>{new_version}\g<2>', content)
                    break
        
        # Write the updated content back
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
            
    except Exception as e:
        raise Exception(f"Failed to update version in {manifest_path}: {e}")


def save_instance_app_info(app_dir: Path, instance_name: str, app_info: Dict[str, Any]):
    """Save app info to instance-specific directory: .fiber/{instance}/app.json"""
    fw_data_dir = app_dir / FIBER_DATA_DIR
    instance_dir = fw_data_dir / instance_name
    instance_dir.mkdir(parents=True, exist_ok=True)
    
    app_info_path = instance_dir / APP_INFO_FILE
    
    try:
        with open(app_info_path, 'w', encoding='utf-8') as f:
            json.dump(app_info, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise Exception(f"Failed to save instance app info: {e}")


def load_instance_app_info(app_dir: Path, instance_name: str) -> Dict[str, Any]:
    """Load app info from instance-specific directory: .fiber/{instance}/app.json"""
    fw_data_dir = app_dir / FIBER_DATA_DIR
    instance_dir = fw_data_dir / instance_name
    app_info_path = instance_dir / APP_INFO_FILE
    
    if not app_info_path.exists():
        return {}
    
    try:
        with open(app_info_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
    """
    Update app info with new information.
    
    Args:
        app_dir: App directory
        updates: Dictionary of updates to apply
    
    Returns:
        Updated app info dictionary
    """
    # Load existing info
    app_info = load_fiber_app_info(app_dir)
    
    # Apply updates
    app_info.update(updates)
    
    # Save updated info
    save_fiber_app_info(app_dir, app_info)
    
    return app_info


def verify_deployed_files(app_path: Path, ctx, result: Any, verbose: bool = False):
    """
    Verify deployed files exist by checking all possible locations
    """
    import click
    from pathlib import Path
    import os
    
    try:
        app_info = load_instance_app_info(app_path, ctx.instance_name)
        app_id = app_info.get("app_id")
        app_version_id = result.data.get("app_version_id") if hasattr(result, 'data') and result.data else app_info.get("app_version_id")
        
        if not app_id or not app_version_id:
            click.echo("[ERROR] Missing app_id or app_version_id")
            return
        
        # Base path for entity bundles (note: entity_bundles not app_entity_bundles)
        base_path = Path.home() / ".fiberwise" / "entity_bundles" / "apps" / app_id
        
        verified = 0
        total = 0
        
        # Check functions - search all function directories
        functions = ctx.manifest_data.get('functions', [])
        if verbose:
            click.echo(f"Checking base path: {base_path}")
            click.echo(f"Looking for version: {app_version_id}")
            
        for func in functions:
            impl_path = func.get('implementation_path')
            if impl_path:
                total += 1
                func_name = func.get('name')
                filename = Path(impl_path).name
                
                # Search for the file in any function subdirectory
                function_base = base_path / "function"
                found = False
                
                if verbose:
                    click.echo(f"Searching function base: {function_base}")
                
                if function_base.exists():
                    for func_dir in function_base.iterdir():
                        if func_dir.is_dir():
                            version_dir = func_dir / app_version_id
                            deployed_file = version_dir / filename
                            
                            if verbose:
                                click.echo(f"  Checking: {deployed_file}")
                            
                            if deployed_file.exists():
                                local_file = app_path / impl_path
                                
                                if verbose:
                                    click.echo(f"Function {func_name}: FOUND {deployed_file}")
                                
                                if local_file.exists():
                                    if deployed_file.read_text() == local_file.read_text():
                                        verified += 1
                                        found = True
                                        if verbose:
                                            click.echo("  ✅ Match")
                                        break
                                    elif verbose:
                                        click.echo("  ❌ Content differs")
                                elif verbose:
                                    click.echo("  ❌ Local file missing")
                else:
                    if verbose:
                        click.echo(f"Function base doesn't exist: {function_base}")
                
                if not found and verbose:
                    click.echo(f"Function {func_name}: File not found in any function directory")
        
        # Check agents - search all agent directories
        agents = ctx.manifest_data.get('agents', [])
        for agent in agents:
            impl_path = agent.get('implementation_path')
            if impl_path:
                total += 1
                agent_name = agent.get('name')
                filename = Path(impl_path).name
                
                # Search for the file in any agent subdirectory
                agent_base = base_path / "agent"
                found = False
                
                if agent_base.exists():
                    for agent_dir in agent_base.iterdir():
                        if agent_dir.is_dir():
                            version_dir = agent_dir / app_version_id
                            deployed_file = version_dir / filename
                            
                            if deployed_file.exists():
                                local_file = app_path / impl_path
                                
                                if verbose:
                                    click.echo(f"Agent {agent_name}: {deployed_file}")
                                
                                if local_file.exists():
                                    if deployed_file.read_text() == local_file.read_text():
                                        verified += 1
                                        found = True
                                        if verbose:
                                            click.echo("  ✅ Match")
                                        break
                                    elif verbose:
                                        click.echo("  ❌ Content differs")
                                elif verbose:
                                    click.echo("  ❌ Local file missing")
                
                if not found and verbose:
                    click.echo(f"Agent {agent_name}: File not found in any agent directory")
        
        if verified == total:
            click.echo(f"✅ {verified}/{total} files verified")
        else:
            click.echo(f"❌ {verified}/{total} files verified")
            
    except Exception as e:
        click.echo(f"[ERROR] {e}")
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
